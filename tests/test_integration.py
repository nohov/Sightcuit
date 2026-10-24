from __future__ import annotations

import json
import csv
from pathlib import Path
import unittest

from recognition import yolo_runner


ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_frozen_yolo_support_covers_exact_project_contract(self) -> None:
        labels = json.loads((ROOT / "labels/classes.json").read_text(encoding="utf-8"))
        config = yolo_runner.load_config(ROOT / "recognition/yolo_model.json")
        target_ids = {entry["id"] for entry in labels["classes"]}

        self.assertEqual(target_ids, set(yolo_runner.TARGET_CLASSES))
        self.assertEqual(target_ids, set(config["target_support"]))
        self.assertEqual(config["raw_to_project_mapping"], {"laptop": "laptop", "cell phone": "phone"})
        self.assertEqual(config["target_support"]["smartwatch"]["status"], "unsupported")
        self.assertIn("clock", config["target_support"]["smartwatch"]["rejected_raw_class_names"])

    def test_detection_schema_requires_raw_and_reproducibility_fields(self) -> None:
        schema = json.loads(
            (ROOT / "recognition/prediction.schema.json").read_text(encoding="utf-8")
        )
        required = set(schema["required"])

        self.assertTrue({
            "weights_sha256", "runtime_version", "command", "thresholds",
            "elapsed_ms", "raw_predictions", "detections", "error",
        }.issubset(required))
        self.assertEqual(schema["properties"]["task"]["const"], "object_detection")
        self.assertIn("xyxy pixels", schema["properties"]["box_format"]["const"])

        with (ROOT / "evaluation/manifest_template.csv").open(newline="", encoding="utf-8") as source:
            fields = next(csv.reader(source))
        self.assertIn("annotation_path", fields)


if __name__ == "__main__":
    unittest.main()
