from __future__ import annotations

import csv
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from recognition import yolo_runner


CONFIG = yolo_runner.load_config()


def detection(name: str, class_id: int, confidence: float, box=None):
    return {
        "name": name,
        "class": class_id,
        "confidence": confidence,
        "box": box or {"x1": 10, "y1": 20, "x2": 110, "y2": 120},
    }


class FakePredictor:
    runtime_version = "test-only"
    weights_sha256 = "0" * 64

    def __init__(self, summary):
        self.summary = summary
        self.paths = []

    def predict(self, image_path, confidence, iou, device):
        self.paths.append(image_path)
        return {"raw_summary": self.summary, "image_size": (200, 300)}


class YoloRunnerTests(unittest.TestCase):
    def test_missing_weights_stop_before_runtime_or_download(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "yolo26n.pt"
            with self.assertRaisesRegex(RuntimeError, "automatic downloads are disabled"):
                yolo_runner.UltralyticsPredictor(missing, CONFIG)

    def test_parses_real_style_summary_and_preserves_detection_fields(self):
        raw = [detection("laptop", 63, 0.912345)]
        parsed = yolo_runner.normalize_summary(raw, (200, 300), 0.25, CONFIG)

        self.assertEqual(parsed, [{
            "raw_class_id": 63,
            "raw_class_name": "laptop",
            "confidence": 0.912345,
            "box_xyxy_pixels": [10.0, 20.0, 110.0, 120.0],
            "project_class": "laptop",
            "mapping_status": "mapped",
        }])
        self.assertEqual(raw[0]["box"]["x1"], 10)

    def test_coco_cell_phone_maps_to_phone_and_clock_stays_unsupported(self):
        raw = [detection("cell phone", 67, 0.8), detection("clock", 74, 0.8)]
        parsed = yolo_runner.normalize_summary(raw, (200, 300), 0.25, CONFIG)
        self.assertEqual([(d["project_class"], d["mapping_status"]) for d in parsed],
                         [("phone", "mapped"), (None, "unsupported")])

    def test_threshold_filtering(self):
        raw = [
            detection("laptop", 63, 0.249),
            detection("laptop", 63, 0.25),
        ]
        parsed = yolo_runner.normalize_summary(raw, (200, 300), 0.25, CONFIG)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["confidence"], 0.25)

    def test_invalid_boxes_are_rejected(self):
        cases = (
            {"x1": 30, "y1": 20, "x2": 10, "y2": 120},
            {"x1": -1, "y1": 20, "x2": 10, "y2": 120},
            {"x1": 10, "y1": 20, "x2": 301, "y2": 120},
        )
        for box in cases:
            with self.subTest(box=box), self.assertRaisesRegex(ValueError, "box"):
                yolo_runner.normalize_summary(
                    [detection("laptop", 63, 0.9, box)], (200, 300), 0.25, CONFIG
                )

    def test_filename_cannot_create_a_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "definitely-a-laptop.jpg").write_bytes(b"test bytes")
            manifest = root / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=("image_id", "path", "expected_outcome"))
                writer.writeheader()
                writer.writerow({
                    "image_id": "neutral-id",
                    "path": "definitely-a-laptop.jpg",
                    "expected_outcome": "laptop",
                })
            output = root / "predictions.jsonl"
            predictor = FakePredictor([detection("tv", 62, 0.9)])

            yolo_runner.run_manifest(
                manifest, output, Path("unused.pt"), CONFIG, 0.25, 0.7, "cpu",
                "unit test", predictor=predictor,
            )
            record = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(record["raw_predictions"][0]["name"], "tv")
        self.assertIsNone(record["detections"][0]["project_class"])
        self.assertEqual(record["detections"][0]["mapping_status"], "unsupported")
        self.assertNotIn("expected_outcome", json.dumps(record))

    def test_unsupported_target_mapping_is_refused(self):
        config = copy.deepcopy(CONFIG)
        config["raw_to_project_mapping"]["clock"] = "smartwatch"
        config["target_support"]["smartwatch"]["raw_class_names"] = ["clock"]
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            yolo_runner.validate_config(config)

    def test_open_vocabulary_config_sets_prompts_as_classes(self):
        world = yolo_runner.load_config(yolo_runner.HERE / "yolo_world_model.json")
        self.assertEqual(set(world["raw_to_project_mapping"].values()), set(yolo_runner.TARGET_CLASSES))

        class FakeWorldModel:
            def __init__(self, path, task):
                self.names = {0: "person"}

            def set_classes(self, prompts):
                self.names = dict(enumerate(prompts))

        fake_module = types.SimpleNamespace(YOLO=FakeWorldModel)
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / world["weights_filename"]
            weights.write_bytes(b"fake weights")
            with mock.patch.dict(sys.modules, {"ultralytics": fake_module}), \
                    mock.patch.object(yolo_runner, "version", lambda _: "test-only"):
                predictor = yolo_runner.UltralyticsPredictor(weights, world)

        self.assertEqual(list(predictor.model.names.values()), world["expected_builtin_classes"])

    def test_class_name_must_match_frozen_model_list(self):
        with self.assertRaisesRegex(ValueError, "class name"):
            yolo_runner.normalize_summary(
                [detection("smartwatch", 74, 0.9)], (200, 300), 0.25, CONFIG
            )


if __name__ == "__main__":
    unittest.main()
