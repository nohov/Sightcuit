#!/usr/bin/env python3
"""Propose boxes with local YOLO-World, then label them with one Gemini call per image."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import platform
import shlex
import sys
import tempfile
import time
from typing import Any

from recognition.gemini_runner import (
    API_VERSION, LABELS, Transport, build_payload, gemini_transport, read_image, response_text,
)
from recognition.yolo_runner import UltralyticsPredictor, load_config, manifest_entries, normalize_summary


PROMPT_VERSION = "cascade-v1"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "yolo_world_l_model.json"
# Low on purpose: Gemini rejects junk boxes, but it cannot recover boxes YOLO never proposed.
DEFAULT_PROPOSAL_CONFIDENCE = 0.1
# shortcut: keeps the prompt bounded on cluttered scenes; raise it if crowded scenes lose recall.
MAX_PROPOSALS = 20
CASCADE_LABELS = (*LABELS, "none")
MAX_FREE_LABEL_CHARS = 60
RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "index": {"type": "INTEGER"},
            "label": {"type": "STRING", "enum": list(CASCADE_LABELS)},
        },
        "required": ["index", "label"],
    },
}


def region_text(proposals: list[dict[str, Any]], image_size: tuple[int, int]) -> str:
    """Number each proposal and convert its xyxy pixel box to Gemini's [ymin, xmin, ymax, xmax] 0-1000."""
    height, width = image_size
    lines = []
    for index, proposal in enumerate(proposals):
        x1, y1, x2, y2 = proposal["box_xyxy_pixels"]
        box = [round(y1 / height * 1000), round(x1 / width * 1000),
               round(y2 / height * 1000), round(x2 / width * 1000)]
        lines.append(f"{index}: {box}")
    return "\n".join(lines)


def parse_labels(raw: Any, count: int, allowed: tuple[str, ...] | None = CASCADE_LABELS) -> list[str]:
    """Require exactly one valid label per proposal index; allowed=None accepts any short free-text label."""
    if not isinstance(raw, list):
        raise ValueError("response must be a JSON list")
    labels: dict[int, str] = {}
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"index", "label"}:
            raise ValueError("each entry must contain only index and label")
        index, label = item["index"], item["label"]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < count:
            raise ValueError(f"invalid region index {index!r}")
        if index in labels:
            raise ValueError(f"region {index} labelled twice")
        if allowed is None:
            if not isinstance(label, str) or not 0 < len(label.strip()) <= MAX_FREE_LABEL_CHARS:
                raise ValueError(f"region {index} has invalid label {label!r}")
            label = label.strip()
        elif label not in allowed:
            raise ValueError(f"region {index} has invalid label {label!r}")
        labels[index] = label
    if len(labels) != count:
        raise ValueError(f"expected {count} labels, received {len(labels)}")
    return [labels[index] for index in range(count)]


def run_manifest(
    manifest: Path,
    output: Path,
    weights: Path,
    config: dict[str, Any],
    model: str,
    command: str,
    proposal_confidence: float = DEFAULT_PROPOSAL_CONFIDENCE,
    iou: float | None = None,
    device: str = "cpu",
    timeout: float = 120.0,
    transport: Transport = gemini_transport,
    predictor: Any | None = None,
    thinking_level: str | None = None,
) -> None:
    iou = config["thresholds"]["iou"] if iou is None else iou
    if not 0 <= proposal_confidence <= 1 or not 0 <= iou <= 1:
        raise ValueError("confidence and IoU thresholds must be between 0 and 1")
    manifest, output = manifest.resolve(), output.resolve()
    if manifest == output:
        raise ValueError("manifest and output paths must differ")
    rows = manifest_entries(manifest)
    template = (HERE / "prompt-cascade-v1.txt").read_text(encoding="utf-8")
    predictor = predictor or UltralyticsPredictor(weights, config)
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as destination:
            temporary_path = Path(destination.name)
            for row in rows:
                started = time.perf_counter()
                image_size = None
                raw: list[dict[str, Any]] = []
                raw_response = None
                response: dict[str, Any] = {}
                detections: list[dict[str, Any]] = []
                error = None
                try:
                    image_path = manifest.parent / row["path"]
                    image_bytes, mime, size = read_image(image_path)
                    image_size = list(size)
                    result = predictor.predict(image_path, proposal_confidence, iou, device, agnostic_nms=True)
                    if tuple(result["image_size"]) != size:
                        raise ValueError("YOLO and Pillow disagree on image size")
                    proposals = normalize_summary(result["raw_summary"], size, proposal_confidence, config)
                    proposals = sorted(proposals, key=lambda p: -p["confidence"])[:MAX_PROPOSALS]
                    raw = [{"proposal": proposal, "gemini_label": None} for proposal in proposals]
                    if proposals:  # empty scenes cost no API call
                        prompt = template.replace("{regions}", region_text(proposals, size))
                        response = transport(
                            build_payload(image_bytes, mime, prompt, thinking_level, RESPONSE_SCHEMA),
                            model, timeout,
                        )
                        raw_response = response_text(response)
                        labels = parse_labels(json.loads(raw_response), len(proposals))
                        for entry, label in zip(raw, labels):
                            entry["gemini_label"] = label
                        detections = [{
                            "raw_class_id": LABELS.index(label),
                            "raw_class_name": label,
                            "confidence": None,
                            "box_xyxy_pixels": entry["proposal"]["box_xyxy_pixels"],
                            "project_class": label,
                            "mapping_status": "mapped",
                        } for entry, label in zip(raw, labels) if label != "none"]
                    logging.info("Cascade completed image_id=%s proposals=%d detections=%d",
                                 row["image_id"], len(raw), len(detections))
                except Exception as exc:
                    detections = []
                    error = f"{type(exc).__name__}: {exc}"
                    logging.exception("Cascade failed for image_id=%s", row["image_id"])

                record = {
                    "schema_version": "1.0.0",
                    "image_id": row["image_id"],
                    "task": "object_detection",
                    "model_identifier": (
                        f"{config['model_identifier']} proposals -> Gemini {model} labels "
                        f"({PROMPT_VERSION}, thinking={thinking_level or 'model default'})"
                    ),
                    "weights_filename": weights.name,
                    "weights_sha256": getattr(predictor, "weights_sha256", None),
                    "runtime": "ultralytics+gemini-api",
                    "runtime_version": f"ultralytics {getattr(predictor, 'runtime_version', None)}; gemini {API_VERSION}",
                    "model_version": response.get("modelVersion"),
                    "prompt_version": PROMPT_VERSION,
                    "usage": response.get("usageMetadata"),
                    "device": device,
                    "hardware": {"system": platform.system(), "machine": platform.machine()},
                    "command": command,
                    "thresholds": {"confidence": proposal_confidence, "iou": iou},
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "image_size_hw_pixels": image_size,
                    "box_format": "xyxy pixels: [left, top, right, bottom] in the original image",
                    "raw_predictions": raw,
                    "raw_response": raw_response,
                    "detections": detections,
                    "error": error,
                }
                destination.write(json.dumps(record, separators=(",", ":")) + "\n")
        os.replace(temporary_path, output)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="CSV containing image_id and path")
    parser.add_argument("output", type=Path, help="detection JSONL output")
    parser.add_argument("--weights", required=True, type=Path, help="existing local YOLO-World weights")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="pinned Gemini model ID")
    parser.add_argument("--proposal-confidence", type=float, default=DEFAULT_PROPOSAL_CONFIDENCE)
    parser.add_argument("--iou", type=float)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--thinking-level", choices=("minimal", "low", "medium", "high"))
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        parser.error("GEMINI_API_KEY must be set in the environment")

    config = load_config(args.config)
    log_path = args.log or args.output.with_suffix(args.output.suffix + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    command = shlex.join([sys.executable, *sys.argv])
    logging.info("Starting command: %s", command)
    run_manifest(
        args.manifest, args.output, args.weights, config, args.model, command,
        args.proposal_confidence, args.iou, args.device, args.timeout,
        thinking_level=args.thinking_level,
    )


if __name__ == "__main__":
    main()
