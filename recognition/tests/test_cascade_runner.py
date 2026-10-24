import csv
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from recognition import cascade_runner as runner
from recognition import yolo_runner


CONFIG = yolo_runner.load_config(runner.DEFAULT_CONFIG)


def row(name, class_id, confidence, box):
    x1, y1, x2, y2 = box
    return {"name": name, "class": class_id, "confidence": confidence,
            "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}


class FakePredictor:
    runtime_version = "test-only"
    weights_sha256 = "0" * 64

    def __init__(self, summary):
        self.summary = summary
        self.calls = []

    def predict(self, image_path, confidence, iou, device, agnostic_nms=False):
        self.calls.append(agnostic_nms)
        return {"raw_summary": self.summary, "image_size": (200, 300)}


def gemini_response(items):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}],
            "modelVersion": "test-model-001"}


def run(summary, transport):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        Image.new("RGB", (300, 200)).save(root / "definitely-a-speaker.png")
        manifest = root / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.DictWriter(destination, fieldnames=("image_id", "path", "expected_outcome"))
            writer.writeheader()
            writer.writerow({"image_id": "neutral-id", "path": "definitely-a-speaker.png",
                             "expected_outcome": "GROUND_TRUTH_SENTINEL"})
        output = root / "predictions.jsonl"
        predictor = FakePredictor(summary)
        runner.run_manifest(manifest, output, Path("unused.pt"), CONFIG, "test-model", "unit test",
                            transport=transport, predictor=predictor)
        return json.loads(output.read_text(encoding="utf-8")), predictor


class CascadeRunnerTests(unittest.TestCase):
    def test_no_proposals_skips_gemini(self):
        record, _ = run([], lambda *_: self.fail("transport should not be called"))
        self.assertEqual(record["detections"], [])
        self.assertIsNone(record["error"])
        self.assertIsNone(record["usage"])

    def test_gemini_relabels_yolo_boxes_and_drops_none(self):
        summary = [
            row("smartphone", 1, 0.9, (30, 20, 150, 100)),
            row("smartphone", 1, 0.4, (200, 100, 290, 190)),
        ]

        def transport(payload, model, timeout):
            sent = json.dumps(payload)
            self.assertNotIn("definitely-a-speaker", sent)
            self.assertNotIn("GROUND_TRUTH_SENTINEL", sent)
            self.assertIn("0: [100, 100, 500, 500]", sent)
            self.assertIn("none", json.dumps(payload["generationConfig"]["responseSchema"]))
            return gemini_response([{"index": 0, "label": "speaker"}, {"index": 1, "label": "none"}])

        record, predictor = run(summary, transport)

        self.assertEqual(predictor.calls, [True])
        self.assertIsNone(record["error"])
        self.assertEqual(record["runtime"], "ultralytics+gemini-api")
        self.assertEqual([d["project_class"] for d in record["detections"]], ["speaker"])
        self.assertEqual(record["detections"][0]["box_xyxy_pixels"], [30.0, 20.0, 150.0, 100.0])
        self.assertEqual([e["gemini_label"] for e in record["raw_predictions"]], ["speaker", "none"])
        self.assertEqual(record["raw_predictions"][0]["proposal"]["raw_class_name"], "smartphone")

    def test_missing_label_is_an_explicit_error(self):
        summary = [row("speaker", 4, 0.9, (30, 20, 150, 100)), row("speaker", 4, 0.8, (200, 100, 290, 190))]
        record, _ = run(summary, lambda *_: gemini_response([{"index": 0, "label": "speaker"}]))
        self.assertEqual(record["detections"], [])
        self.assertIn("expected 2 labels", record["error"])
        self.assertIsNotNone(record["raw_response"])

    def test_parse_labels_rejects_bad_entries(self):
        cases = (
            ([{"index": 0, "label": "speaker"}, {"index": 0, "label": "none"}], 2),
            ([{"index": 5, "label": "speaker"}], 1),
            ([{"index": 0, "label": "tv"}], 1),
            ({"index": 0, "label": "speaker"}, 1),
        )
        for raw, count in cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runner.parse_labels(raw, count)


if __name__ == "__main__":
    unittest.main()
