from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.score import load_manifest, load_predictions, score


FIELDS = (
    "image_id",
    "path",
    "expected_outcome",
    "physical_device_id",
    "location_session_id",
    "source",
    "permission_provenance_notes",
)


def manifest_row(image_id: str, expected: str) -> dict[str, str]:
    return {
        "image_id": image_id,
        "path": f"images/{image_id}.jpg",
        "expected_outcome": expected,
        "physical_device_id": f"device-{image_id}",
        "location_session_id": "session-1",
        "source": "synthetic-test-record",
        "permission_provenance_notes": "unit test only; no image exists",
    }


def prediction(image_id: str, outcome: str, latency: float = 10.0,
               error: str | None = None) -> dict[str, object]:
    return {
        "image_id": image_id,
        "outcome": outcome,
        "evidence": None,
        "model_identifier": "mock-model",
        "prompt_version": "electronics-pokedex-v1",
        "latency_ms": latency,
        "error": error,
        "raw_response": None,
    }


class ScoreTests(unittest.TestCase):
    def test_failures_and_false_acceptance_remain_visible(self) -> None:
        rows = [
            manifest_row("a", "laptop"),
            manifest_row("b", "unsupported"),
            manifest_row("c", "monitor"),
            manifest_row("d", "projector"),
        ]
        predictions = {
            "a": prediction("a", "laptop", 10),
            "b": prediction("b", "printer", 20),
            "c": prediction("c", "unsupported", 30, "inference_error: timeout"),
            "extra": prediction("extra", "monitor", 40),
        }

        report = score(rows, predictions)

        self.assertEqual(report["request_failures"]["count"], 2)
        self.assertEqual(report["confusion"]["monitor"]["request_failure"], 1)
        self.assertEqual(report["confusion"]["projector"]["request_failure"], 1)
        self.assertEqual(report["unsupported_false_acceptance"]["rate"], 1.0)
        self.assertEqual(report["per_class"]["laptop"]["precision"], 1.0)
        self.assertEqual(report["per_class"]["monitor"]["recall"], 0.0)
        self.assertEqual(report["unexpected_predictions"], ["extra"])
        self.assertEqual(len(report["records"]), 4)

    def test_abstention_and_latency(self) -> None:
        rows = [manifest_row("a", "printer"), manifest_row("b", "projector")]
        predictions = {
            "a": prediction("a", "ambiguous", 10),
            "b": prediction("b", "unreadable", 30),
        }

        report = score(rows, predictions)

        self.assertEqual(report["abstention"]["rate"], 1.0)
        self.assertEqual(report["latency"]["mean_ms"], 20.0)
        self.assertEqual(report["latency"]["p95_ms"], 30.0)

    def test_manifest_and_prediction_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.csv"
            predictions = root / "predictions.jsonl"
            with manifest.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow(manifest_row("a", "laptop"))
            invalid = prediction("b", "monitor")
            del invalid["prompt_version"]
            predictions.write_text(
                json.dumps(prediction("a", "laptop")) + "\nnot-json\n" +
                json.dumps(invalid) + "\n",
                encoding="utf-8",
            )

            loaded_manifest = load_manifest(manifest)
            loaded_predictions, errors = load_predictions(predictions)

        self.assertEqual(loaded_manifest[0]["image_id"], "a")
        self.assertIn("a", loaded_predictions)
        self.assertEqual([error["line"] for error in errors], [2, 3])
        self.assertNotIn("b", loaded_predictions)

    def test_duplicate_manifest_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow(manifest_row("same", "laptop"))
                writer.writerow(manifest_row("same", "monitor"))

            with self.assertRaisesRegex(ValueError, "duplicate image_id"):
                load_manifest(manifest)

    def test_manifest_preflight_checks_image_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow(manifest_row("missing", "laptop"))

            with self.assertRaisesRegex(ValueError, "missing image"):
                load_manifest(manifest, check_files=True)


if __name__ == "__main__":
    unittest.main()
