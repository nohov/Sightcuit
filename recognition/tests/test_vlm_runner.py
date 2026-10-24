import csv
import json
from pathlib import Path
import tempfile
import unittest

from recognition import vlm_runner as runner


class RunnerTests(unittest.TestCase):
    def test_csv_manifest_ground_truth_never_reaches_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "photo.jpg").write_bytes(b"fake image bytes")
            manifest = root / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=(
                    "image_id", "path", "expected_outcome", "permission_provenance_notes"
                ))
                writer.writeheader()
                writer.writerow({
                    "image_id": "img-csv",
                    "path": "photo.jpg",
                    "expected_outcome": "laptop",
                    "permission_provenance_notes": "GROUND_TRUTH_SENTINEL",
                })
            output = root / "predictions.jsonl"

            def mock_transport(payload, endpoint, timeout):
                self.assertNotIn("GROUND_TRUTH_SENTINEL", json.dumps(payload))
                return {"message": {"content": json.dumps({
                    "outcome": "laptop",
                    "evidence": "An integrated screen and keyboard are visible.",
                })}}

            runner.run_manifest(manifest, output, transport=mock_transport)

            prediction = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(prediction["image_id"], "img-csv")
            self.assertEqual(prediction["outcome"], "laptop")

    def test_prediction_ignores_ground_truth_and_keeps_required_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "photo.jpg").write_bytes(b"fake image bytes")
            manifest = root / "manifest.jsonl"
            manifest.write_text(
                json.dumps({
                    "image_id": "img-1",
                    "path": "photo.jpg",
                    "ground_truth": "SECRET_LABEL",
                }) + "\n",
                encoding="utf-8",
            )
            output = root / "predictions.jsonl"

            def mock_transport(payload, endpoint, timeout):
                self.assertNotIn("SECRET_LABEL", json.dumps(payload))
                self.assertEqual(payload["format"]["additionalProperties"], False)
                return {"message": {"content": json.dumps({
                    "outcome": "laptop",
                    "evidence": "An integrated screen and keyboard are visible.",
                })}}

            runner.run_manifest(manifest, output, transport=mock_transport)
            prediction = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(prediction["image_id"], "img-1")
            self.assertEqual(prediction["outcome"], "laptop")
            self.assertEqual(prediction["model_identifier"], runner.DEFAULT_MODEL)
            self.assertEqual(prediction["prompt_version"], runner.PROMPT_VERSION)
            self.assertIsNone(prediction["error"])
            self.assertGreaterEqual(prediction["latency_ms"], 0)

    def test_missing_image_writes_unreadable_without_calling_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.jsonl"
            manifest.write_text('{"image_id":"missing","path":"none.jpg"}\n', encoding="utf-8")

            def fail_if_called(*args):
                self.fail("transport should not be called")

            output = root / "predictions.jsonl"
            runner.run_manifest(manifest, output, transport=fail_if_called)
            prediction = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(prediction["outcome"], "unreadable")
            self.assertTrue(prediction["error"].startswith("image_error:"))

    def test_invalid_model_response_is_preserved_as_explicit_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "photo.jpg").write_bytes(b"fake image bytes")
            manifest = root / "manifest.jsonl"
            manifest.write_text('{"image_id":"img-2","path":"photo.jpg"}\n', encoding="utf-8")
            output = root / "predictions.jsonl"
            raw = '{"outcome":"television","evidence":"A screen is visible."}'

            runner.run_manifest(
                manifest,
                output,
                transport=lambda *_: {"message": {"content": raw}},
            )
            prediction = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(prediction["outcome"], "unsupported")
            self.assertIn("inference_error", prediction["error"])
            self.assertEqual(prediction["raw_response"], raw)


if __name__ == "__main__":
    unittest.main()
