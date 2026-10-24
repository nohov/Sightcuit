import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

from recognition import gemini_runner as runner


def gemini_response(items):
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}],
        "modelVersion": "test-model-001",
        "usageMetadata": {"totalTokenCount": 7},
    }


def write_manifest(root: Path, filename: str, image: Image.Image | None = None) -> Path:
    if image is not None:
        image.save(root / filename)
    manifest = root / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=(
            "image_id", "path", "expected_outcome", "permission_provenance_notes"
        ))
        writer.writeheader()
        writer.writerow({
            "image_id": "neutral-id",
            "path": filename,
            "expected_outcome": "laptop",
            "permission_provenance_notes": "GROUND_TRUTH_SENTINEL",
        })
    return manifest


def run(root: Path, manifest: Path, transport) -> dict:
    output = root / "predictions.jsonl"
    runner.run_manifest(manifest, output, "test-model", "unit test", transport=transport)
    return json.loads(output.read_text(encoding="utf-8"))


class GeminiRunnerTests(unittest.TestCase):
    def test_box_2d_converts_to_xyxy_pixels(self):
        parsed = runner.normalize_response(
            [{"label": "monitor", "box_2d": [100, 250, 500, 750]}], (200, 400)
        )
        self.assertEqual(parsed, [{
            "raw_class_id": 2,
            "raw_class_name": "monitor",
            "confidence": None,
            "box_xyxy_pixels": [100.0, 20.0, 300.0, 100.0],
            "project_class": "monitor",
            "mapping_status": "mapped",
        }])

    def test_thinking_level_is_sent_only_when_requested(self):
        default = runner.build_payload(b"x", "image/png", "prompt")
        low = runner.build_payload(b"x", "image/png", "prompt", "low")
        self.assertNotIn("thinkingConfig", default["generationConfig"])
        self.assertEqual(low["generationConfig"]["thinkingConfig"], {"thinkingLevel": "low"})

    def test_invalid_responses_are_rejected(self):
        cases = (
            {"not": "a list"},
            [{"label": "tv", "box_2d": [0, 0, 10, 10]}],
            [{"label": "laptop", "box_2d": [0, 0, 10]}],
            [{"label": "laptop", "box_2d": [10, 0, 5, 10]}],
            [{"label": "laptop", "box_2d": [0, 0, 10, 1001]}],
            [{"label": "laptop", "box_2d": [0, 0, 10, 10], "confidence": 0.9}],
        )
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runner.normalize_response(raw, (100, 100))

    def test_filename_and_ground_truth_never_reach_the_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_manifest(root, "definitely-a-laptop.png", Image.new("RGB", (40, 20)))

            def mock_transport(payload, model, timeout):
                sent = json.dumps(payload)
                self.assertNotIn("definitely-a-laptop", sent)
                self.assertNotIn("GROUND_TRUTH_SENTINEL", sent)
                self.assertEqual(payload["contents"][0]["parts"][0]["inline_data"]["mime_type"], "image/png")
                return gemini_response([])

            record = run(root, manifest, mock_transport)

        self.assertEqual(record["detections"], [])
        self.assertIsNone(record["error"])
        self.assertEqual(record["image_size_hw_pixels"], [20, 40])
        self.assertEqual(record["runtime"], "gemini-api")
        self.assertEqual(record["model_version"], "test-model-001")
        self.assertNotIn("expected_outcome", json.dumps(record))

    def test_invalid_model_output_is_kept_as_explicit_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_manifest(root, "photo.png", Image.new("RGB", (10, 10)))
            record = run(root, manifest, lambda *_: gemini_response([{"label": "tv", "box_2d": [0, 0, 5, 5]}]))

        self.assertEqual(record["detections"], [])
        self.assertIn("invalid label", record["error"])
        self.assertIn('"tv"', record["raw_predictions"])

    def test_exif_rotated_image_is_refused_without_calling_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.new("RGB", (10, 10))
            exif = image.getexif()
            exif[0x0112] = 6
            image.save(root / "rotated.jpg", exif=exif)
            manifest = write_manifest(root, "rotated.jpg")
            record = run(root, manifest, lambda *_: self.fail("transport should not be called"))

        self.assertIn("EXIF rotation", record["error"])

    def test_api_key_goes_in_header_not_url_or_record(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["key"] = request.get_header("X-goog-api-key")
            return io.BytesIO(json.dumps(gemini_response([])).encode())

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "SECRET_KEY"}), \
                mock.patch.object(runner, "urlopen", fake_urlopen):
            response = runner.gemini_transport({"contents": []}, "test-model", 5)

        self.assertEqual(captured["key"], "SECRET_KEY")
        self.assertNotIn("SECRET_KEY", captured["url"])
        self.assertNotIn("SECRET_KEY", json.dumps(response))

    def test_missing_api_key_fails(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
            runner.gemini_transport({}, "test-model", 5)


if __name__ == "__main__":
    unittest.main()
