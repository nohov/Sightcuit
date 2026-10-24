#!/usr/bin/env python3
"""Validate a manifest or score the separate whole-image VLM predictions.

This does not score YOLO boxes and must not be used to claim detection quality.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from typing import Any


TARGET_CLASSES = (
    "laptop",
    "desktop_computer_tower",
    "monitor",
    "printer",
    "projector",
)
SPECIAL_OUTCOMES = ("ambiguous", "unsupported", "unreadable")
ALLOWED_OUTCOMES = TARGET_CLASSES + SPECIAL_OUTCOMES
REQUIRED_MANIFEST_FIELDS = (
    "image_id",
    "path",
    "expected_outcome",
    "physical_device_id",
    "location_session_id",
    "source",
    "permission_provenance_notes",
)
REQUIRED_PREDICTION_FIELDS = {
    "image_id",
    "outcome",
    "evidence",
    "model_identifier",
    "prompt_version",
    "latency_ms",
    "error",
    "raw_response",
}
PROMPT_VERSION = "electronics-pokedex-v1"


def load_manifest(path: Path, check_files: bool = False) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"manifest missing fields: {', '.join(missing)}")
        rows = list(reader)

    seen: set[str] = set()
    for line_number, row in enumerate(rows, 2):
        for field in REQUIRED_MANIFEST_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"manifest line {line_number}: empty {field}")
            row[field] = value.strip()
        image_id = row["image_id"]
        if image_id in seen:
            raise ValueError(f"manifest line {line_number}: duplicate image_id {image_id!r}")
        seen.add(image_id)
        if row["expected_outcome"] not in ALLOWED_OUTCOMES:
            raise ValueError(
                f"manifest line {line_number}: invalid expected_outcome {row['expected_outcome']!r}"
            )
        if check_files and not (path.parent / row["path"]).is_file():
            raise ValueError(f"manifest line {line_number}: missing image {row['path']!r}")
    return rows


def load_predictions(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    predictions: dict[str, dict[str, Any]] = {}
    parse_errors: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record is not an object")
                image_id = record.get("image_id")
                if not isinstance(image_id, str) or not image_id:
                    raise ValueError("image_id must be a non-empty string")
                if image_id in predictions:
                    raise ValueError(f"duplicate image_id {image_id!r}")
                fields = set(record)
                if fields != REQUIRED_PREDICTION_FIELDS:
                    missing = sorted(REQUIRED_PREDICTION_FIELDS - fields)
                    extra = sorted(fields - REQUIRED_PREDICTION_FIELDS)
                    raise ValueError(f"prediction fields mismatch; missing={missing}, extra={extra}")
                if record["outcome"] not in ALLOWED_OUTCOMES:
                    raise ValueError(f"invalid outcome {record['outcome']!r}")
                if record["prompt_version"] != PROMPT_VERSION:
                    raise ValueError(f"invalid prompt_version {record['prompt_version']!r}")
                if not isinstance(record["model_identifier"], str) or not record["model_identifier"]:
                    raise ValueError("model_identifier must be a non-empty string")
                latency = record["latency_ms"]
                if not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0:
                    raise ValueError("latency_ms must be a non-negative number")
                if record["error"] is not None and not isinstance(record["error"], str):
                    raise ValueError("error must be a string or null")
                if record["evidence"] is not None and not isinstance(record["evidence"], str):
                    raise ValueError("evidence must be a string or null")
                if record["raw_response"] is not None and not isinstance(record["raw_response"], str):
                    raise ValueError("raw_response must be a string or null")
                predictions[image_id] = record
            except (json.JSONDecodeError, ValueError) as error:
                parse_errors.append({"line": line_number, "error": str(error)})
    return predictions, parse_errors


def safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def latency_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "mean_ms": statistics.fmean(ordered),
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[p95_index],
    }


def score(manifest_rows: list[dict[str, str]], predictions: dict[str, dict[str, Any]],
          parse_errors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    parse_errors = parse_errors or []
    manifest_ids = {row["image_id"] for row in manifest_rows}
    confusion: dict[str, dict[str, int]] = {}
    records: list[dict[str, Any]] = []
    latencies: list[float] = []
    request_failures = 0
    abstentions = 0

    for row in manifest_rows:
        image_id = row["image_id"]
        expected = row["expected_outcome"]
        prediction = predictions.get(image_id)
        error: str | None = None
        latency: float | None = None

        if prediction is None:
            actual = "request_failure"
            error = "missing prediction record"
        else:
            raw_latency = prediction.get("latency_ms")
            if isinstance(raw_latency, (int, float)) and not isinstance(raw_latency, bool) and raw_latency >= 0:
                latency = float(raw_latency)
                latencies.append(latency)
            raw_error = prediction.get("error")
            outcome = prediction.get("outcome")
            if raw_error is not None:
                actual = "request_failure"
                error = str(raw_error)
            elif outcome not in ALLOWED_OUTCOMES:
                actual = "request_failure"
                error = f"invalid or missing outcome: {outcome!r}"
            else:
                actual = str(outcome)

        if actual == "request_failure":
            request_failures += 1
        elif actual in ("ambiguous", "unreadable"):
            abstentions += 1

        confusion.setdefault(expected, {})[actual] = confusion.setdefault(expected, {}).get(actual, 0) + 1
        records.append({
            "image_id": image_id,
            "expected_outcome": expected,
            "scored_outcome": actual,
            "latency_ms": latency,
            "error": error,
        })

    per_class: dict[str, dict[str, float | int | None]] = {}
    for class_id in TARGET_CLASSES:
        true_positive = sum(
            record["expected_outcome"] == class_id and record["scored_outcome"] == class_id
            for record in records
        )
        false_positive = sum(
            record["expected_outcome"] != class_id and record["scored_outcome"] == class_id
            for record in records
        )
        false_negative = sum(
            record["expected_outcome"] == class_id and record["scored_outcome"] != class_id
            for record in records
        )
        per_class[class_id] = {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": safe_rate(true_positive, true_positive + false_positive),
            "recall": safe_rate(true_positive, true_positive + false_negative),
        }

    unsupported_records = [record for record in records if record["expected_outcome"] == "unsupported"]
    unsupported_false_accepts = sum(
        record["scored_outcome"] in TARGET_CLASSES for record in unsupported_records
    )
    total = len(records)
    return {
        "schema_version": "1.0.0",
        "record_count": total,
        "per_class": per_class,
        "confusion": confusion,
        "abstention": {
            "count": abstentions,
            "rate": safe_rate(abstentions, total),
            "outcomes": ["ambiguous", "unreadable"],
        },
        "unsupported_false_acceptance": {
            "count": unsupported_false_accepts,
            "eligible_count": len(unsupported_records),
            "rate": safe_rate(unsupported_false_accepts, len(unsupported_records)),
        },
        "request_failures": {
            "count": request_failures,
            "rate": safe_rate(request_failures, total),
        },
        "latency": latency_summary(latencies),
        "records": records,
        "unexpected_predictions": sorted(set(predictions) - manifest_ids),
        "prediction_parse_errors": parse_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="reviewed evaluation CSV")
    parser.add_argument("predictions", type=Path, nargs="?", help="Recognition JSONL predictions")
    parser.add_argument("--output", type=Path, help="write JSON report instead of stdout")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest, check_files=args.predictions is None)
    if args.predictions is None:
        result: dict[str, Any] = {"valid": True, "manifest_records": len(manifest)}
    else:
        predictions, parse_errors = load_predictions(args.predictions)
        result = score(manifest, predictions, parse_errors)

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
