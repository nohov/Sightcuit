#!/usr/bin/env python3
"""Run local Ultralytics YOLO detection without downloading models or data."""

from __future__ import annotations

import argparse
import csv
import hashlib
from importlib.metadata import version
import json
import logging
import math
import os
from pathlib import Path
import platform
import shlex
import sys
import tempfile
import time
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "yolo_model.json"
TARGET_CLASSES = {
    "laptop",
    "desktop_computer_tower",
    "monitor",
    "printer",
    "projector",
}


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    classes = config.get("expected_builtin_classes")
    support = config.get("target_support")
    mapping = config.get("raw_to_project_mapping")
    if not isinstance(classes, list) or not classes or not all(isinstance(name, str) for name in classes):
        raise ValueError("expected_builtin_classes must be a non-empty string list")
    if not isinstance(support, dict) or set(support) != TARGET_CLASSES:
        raise ValueError("target_support must describe exactly the five project classes")
    if not isinstance(mapping, dict):
        raise ValueError("raw_to_project_mapping must be an object")
    for raw_name, project_class in mapping.items():
        if raw_name not in classes:
            raise ValueError(f"mapped raw class is not built in: {raw_name!r}")
        if project_class not in TARGET_CLASSES:
            raise ValueError(f"invalid project class mapping: {project_class!r}")
        if support[project_class].get("status") != "supported_exact":
            raise ValueError(f"refusing mapping to unsupported target: {project_class}")
        if raw_name not in support[project_class].get("raw_class_names", []):
            raise ValueError(f"mapping is not declared by target_support: {raw_name!r}")


def _number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def normalize_summary(
    raw_summary: Any,
    image_size: tuple[int, int],
    confidence_threshold: float,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate Ultralytics Results.summary() rows and add explicit project mappings."""
    validate_config(config)
    if not isinstance(raw_summary, list):
        raise ValueError("YOLO summary must be a list")
    height, width = image_size
    if height <= 0 or width <= 0:
        raise ValueError("image dimensions must be positive")
    expected = config["expected_builtin_classes"]
    mapping = config["raw_to_project_mapping"]
    detections = []

    for index, item in enumerate(raw_summary):
        if not isinstance(item, dict):
            raise ValueError(f"detection {index} must be an object")
        class_id = item.get("class")
        if not isinstance(class_id, int) or isinstance(class_id, bool) or not 0 <= class_id < len(expected):
            raise ValueError(f"detection {index} has invalid class id")
        raw_name = item.get("name")
        if raw_name != expected[class_id]:
            raise ValueError(f"detection {index} class name does not match frozen model classes")
        confidence = _number(item.get("confidence"), f"detection {index} confidence")
        if not 0 <= confidence <= 1:
            raise ValueError(f"detection {index} confidence must be between 0 and 1")
        if confidence < confidence_threshold:
            continue

        box = item.get("box")
        if not isinstance(box, dict) or set(box) != {"x1", "y1", "x2", "y2"}:
            raise ValueError(f"detection {index} must contain an xyxy box")
        x1, y1, x2, y2 = (
            _number(box[key], f"detection {index} box.{key}")
            for key in ("x1", "y1", "x2", "y2")
        )
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError(f"detection {index} box is outside the image or has no area")

        project_class = mapping.get(raw_name)
        detections.append({
            "raw_class_id": class_id,
            "raw_class_name": raw_name,
            "confidence": confidence,
            "box_xyxy_pixels": [x1, y1, x2, y2],
            "project_class": project_class,
            "mapping_status": "mapped" if project_class else "unsupported",
        })
    return detections


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class UltralyticsPredictor:
    def __init__(self, weights: Path, config: dict[str, Any]):
        if not weights.is_file():
            raise RuntimeError(
                f"weights not found: {weights}; supply an existing local file (automatic downloads are disabled)"
            )
        if weights.name != config["weights_filename"]:
            raise RuntimeError(
                f"weights filename {weights.name!r} does not match frozen configuration "
                f"{config['weights_filename']!r}"
            )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics is not installed in this Python environment") from exc

        self.runtime_version = version("ultralytics")
        self.weights = weights.resolve()
        self.weights_sha256 = sha256_file(self.weights)
        self.model = YOLO(str(self.weights), task="detect")
        names = self.model.names
        actual_classes = [names[index] for index in range(len(names))]
        if actual_classes != config["expected_builtin_classes"]:
            raise RuntimeError("local weights class list does not match the frozen configuration")

    def predict(self, image_path: Path, confidence: float, iou: float, device: str) -> dict[str, Any]:
        results = self.model.predict(
            source=str(image_path),
            conf=confidence,
            iou=iou,
            device=device,
            save=False,
            verbose=False,
        )
        if len(results) != 1:
            raise RuntimeError(f"expected one YOLO result, received {len(results)}")
        result = results[0]
        if result.boxes is None:
            raise RuntimeError("loaded model did not produce object-detection boxes")
        return {
            "raw_summary": result.summary(normalize=False, decimals=6),
            "image_size": tuple(result.orig_shape),
            "runtime_version": self.runtime_version,
            "weights_sha256": self.weights_sha256,
        }


def manifest_entries(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = {"image_id", "path"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"manifest missing fields: {', '.join(sorted(missing))}")
        rows = list(reader)
    seen = set()
    for line, row in enumerate(rows, 2):
        image_id = row.get("image_id", "").strip()
        image_path = row.get("path", "").strip()
        if not image_id or not image_path:
            raise ValueError(f"manifest line {line}: image_id and path are required")
        if image_id in seen:
            raise ValueError(f"manifest line {line}: duplicate image_id {image_id!r}")
        seen.add(image_id)
        row["image_id"], row["path"] = image_id, image_path
    return rows


def run_manifest(
    manifest: Path,
    output: Path,
    weights: Path,
    config: dict[str, Any],
    confidence: float,
    iou: float,
    device: str,
    command: str,
    predictor: Any | None = None,
) -> None:
    if not 0 <= confidence <= 1 or not 0 <= iou <= 1:
        raise ValueError("confidence and IoU thresholds must be between 0 and 1")
    manifest = manifest.resolve()
    output = output.resolve()
    if manifest == output:
        raise ValueError("manifest and output paths must differ")
    rows = manifest_entries(manifest)
    predictor = predictor or UltralyticsPredictor(weights, config)
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as destination:
            temporary_path = Path(destination.name)
            for row in rows:
                image_path = (manifest.parent / row["path"]).resolve()
                started = time.perf_counter()
                raw_summary: Any = None
                error = None
                detections: list[dict[str, Any]] = []
                image_size = None
                try:
                    if not image_path.is_file():
                        raise FileNotFoundError(f"image not found: {row['path']}")
                    result = predictor.predict(image_path, confidence, iou, device)
                    raw_summary = result["raw_summary"]
                    image_size = list(result["image_size"])
                    detections = normalize_summary(
                        raw_summary, tuple(result["image_size"]), confidence, config
                    )
                    logging.info(
                        "Detection completed image_id=%s detections=%d",
                        row["image_id"], len(detections),
                    )
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    logging.exception("Detection failed for image_id=%s", row["image_id"])

                record = {
                    "schema_version": "1.0.0",
                    "image_id": row["image_id"],
                    "task": "object_detection",
                    "model_identifier": config["model_identifier"],
                    "weights_filename": weights.name,
                    "weights_sha256": getattr(predictor, "weights_sha256", None),
                    "runtime": "ultralytics",
                    "runtime_version": getattr(predictor, "runtime_version", None),
                    "device": device,
                    "hardware": {"system": platform.system(), "machine": platform.machine()},
                    "command": command,
                    "thresholds": {"confidence": confidence, "iou": iou},
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "image_size_hw_pixels": image_size,
                    "box_format": "xyxy pixels: [left, top, right, bottom] in the original image",
                    "raw_predictions": raw_summary,
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
    parser.add_argument("output", type=Path, help="raw detection JSONL output")
    parser.add_argument("--weights", required=True, type=Path, help="existing local YOLO .pt weights")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--confidence", type=float)
    parser.add_argument("--iou", type=float)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    confidence = args.confidence if args.confidence is not None else config["thresholds"]["confidence"]
    iou = args.iou if args.iou is not None else config["thresholds"]["iou"]
    log_path = args.log or args.output.with_suffix(args.output.suffix + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    command = shlex.join([sys.executable, *sys.argv])
    logging.info("Starting command: %s", command)
    try:
        run_manifest(
            args.manifest, args.output, args.weights, config, confidence, iou,
            args.device, command,
        )
    except Exception:
        logging.exception("YOLO run failed before completion")
        raise


if __name__ == "__main__":
    main()
