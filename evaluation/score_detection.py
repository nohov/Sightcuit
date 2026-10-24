#!/usr/bin/env python3
"""Score detection JSONL (YOLO or Gemini) against reviewed ground-truth boxes."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from evaluation.score import TARGET_CLASSES, latency_summary, load_manifest, safe_rate


IOU_THRESHOLD = 0.5
MIN_CLASS_RECALL = 0.6


def _box(value: Any, where: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 4 or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value
    ):
        raise ValueError(f"{where}: box must be four finite numbers")
    x1, y1, x2, y2 = value
    if not (x1 < x2 and y1 < y2):
        raise ValueError(f"{where}: box has no area")
    return [float(v) for v in value]


def load_annotation(path: Path, image_id: str) -> list[tuple[str, list[float]]]:
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("image_id") != image_id:
        raise ValueError(f"{path}: image_id does not match manifest row {image_id!r}")
    boxes = record.get("boxes")
    if not isinstance(boxes, list):
        raise ValueError(f"{path}: boxes must be a list")
    parsed = []
    for index, item in enumerate(boxes):
        if not isinstance(item, dict) or item.get("class") not in TARGET_CLASSES:
            raise ValueError(f"{path}: box {index} has invalid class")
        parsed.append((item["class"], _box(item.get("box_xyxy_pixels"), f"{path} box {index}")))
    return parsed


def load_ground_truth(manifest: Path) -> dict[str, list[tuple[str, list[float]]]]:
    rows = load_manifest(manifest)
    missing = [row["image_id"] for row in rows if not (row.get("annotation_path") or "").strip()]
    if missing:
        raise ValueError(f"rows without annotation_path cannot be scored: {', '.join(missing[:10])}")
    return {
        row["image_id"]: load_annotation(manifest.parent / row["annotation_path"].strip(), row["image_id"])
        for row in rows
    }


def load_detections(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            image_id = record.get("image_id")
            if not isinstance(image_id, str) or image_id in records:
                raise ValueError(f"{path}:{line_number}: missing or duplicate image_id")
            records[image_id] = record
    return records


def iou(a: list[float], b: list[float]) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return 0.0
    overlap = width * height
    area = lambda box: (box[2] - box[0]) * (box[3] - box[1])
    return overlap / (area(a) + area(b) - overlap)


def match(predicted: list[list[float]], truth: list[list[float]]) -> tuple[int, int, int]:
    """Greedy one-to-one matching in given order; returns TP, FP, FN."""
    unmatched = list(truth)
    tp = 0
    for box in predicted:
        best = max(unmatched, key=lambda gt: iou(box, gt), default=None)
        if best is not None and iou(box, best) >= IOU_THRESHOLD:
            unmatched.remove(best)
            tp += 1
    return tp, len(predicted) - tp, len(unmatched)


def score_run(ground_truth: dict[str, list[tuple[str, list[float]]]],
              records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in TARGET_CLASSES}
    errors = missing = distractor_false_alarms = distractor_images = 0
    latencies = []
    for image_id, truth in ground_truth.items():
        record = records.get(image_id)
        detections = []
        if record is None:
            missing += 1
        elif record.get("error"):
            errors += 1
        else:
            latencies.append(record["elapsed_ms"])
            # Unmapped raw classes (for example COCO tv) are neither hits nor false alarms.
            detections = [d for d in record["detections"] if d.get("mapping_status") == "mapped"]
            # Highest confidence claims a box first; Gemini (no confidence) keeps response order.
            detections.sort(key=lambda d: -(d["confidence"] if d["confidence"] is not None else 0))
        if not truth:
            distractor_images += 1
            distractor_false_alarms += bool(detections)
        for name in TARGET_CLASSES:
            tp, fp, fn = match(
                [d["box_xyxy_pixels"] for d in detections if d["project_class"] == name],
                [box for cls, box in truth if cls == name],
            )
            counts[name]["tp"] += tp
            counts[name]["fp"] += fp
            counts[name]["fn"] += fn

    per_class = {}
    for name, c in counts.items():
        precision = safe_rate(c["tp"], c["tp"] + c["fp"])
        recall = safe_rate(c["tp"], c["tp"] + c["fn"])
        f1 = (2 * precision * recall / (precision + recall)
              if precision is not None and recall is not None and precision + recall else 0.0)
        per_class[name] = {**c, "precision": precision, "recall": recall, "f1": f1}
    recalls = [v["recall"] or 0.0 for v in per_class.values()]
    identifiers = {r.get("model_identifier") for r in records.values()}
    return {
        "model_identifier": identifiers.pop() if len(identifiers) == 1 else sorted(map(str, identifiers)),
        "per_class": per_class,
        "mean_f1": sum(v["f1"] for v in per_class.values()) / len(per_class),
        "min_recall": min(recalls),
        "disqualified": min(recalls) < MIN_CLASS_RECALL,
        "images": len(ground_truth),
        "errors": errors,
        "missing_records": missing,
        "distractor_images": distractor_images,
        "distractor_false_alarm_images": distractor_false_alarms,
        "latency": latency_summary(latencies),
    }


def markdown(results: dict[str, dict[str, Any]]) -> str:
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}"
    lines = [
        "| Run | Class | TP | FP | FN | Precision | Recall | F1 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run, result in results.items():
        for name, v in result["per_class"].items():
            lines.append(f"| {run} | {name} | {v['tp']} | {v['fp']} | {v['fn']} | "
                         f"{fmt(v['precision'])} | {fmt(v['recall'])} | {fmt(v['f1'])} |")
    lines += [
        "",
        "| Run | Mean F1 | Min recall | Disqualified | Errors | Missing | Distractor false alarms | Median ms | p95 ms |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run, r in results.items():
        lines.append(
            f"| {run} | {fmt(r['mean_f1'])} | {fmt(r['min_recall'])} | {'yes' if r['disqualified'] else 'no'} | "
            f"{r['errors']} | {r['missing_records']} | "
            f"{r['distractor_false_alarm_images']}/{r['distractor_images']} | "
            f"{fmt(r['latency']['median_ms'])} | {fmt(r['latency']['p95_ms'])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="reviewed CSV manifest with annotation_path")
    parser.add_argument("predictions", type=Path, nargs="+", help="detection JSONL file(s), one per run")
    parser.add_argument("--json", type=Path, help="also write full results as JSON")
    args = parser.parse_args()
    ground_truth = load_ground_truth(args.manifest)
    results = {path.stem: score_run(ground_truth, load_detections(path)) for path in args.predictions}
    print(markdown(results), end="")
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
