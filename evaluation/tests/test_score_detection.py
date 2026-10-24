import csv
import json
from pathlib import Path
import tempfile
import unittest

from evaluation import score_detection as scorer


def det(cls, box, confidence=None):
    return {"project_class": cls, "mapping_status": "mapped", "confidence": confidence, "box_xyxy_pixels": box}


def record(image_id, detections, error=None):
    return {"image_id": image_id, "model_identifier": "test", "elapsed_ms": 5.0,
            "detections": detections, "error": error}


class DetectionScoreTests(unittest.TestCase):
    def test_iou_edge_cases(self):
        self.assertEqual(scorer.iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(scorer.iou([0, 0, 10, 10], [10, 0, 20, 10]), 0.0)
        self.assertAlmostEqual(scorer.iou([0, 0, 10, 10], [5, 0, 15, 10]), 1 / 3)

    def test_duplicate_detection_counts_one_hit_and_one_false_positive(self):
        self.assertEqual(scorer.match([[0, 0, 10, 10], [0, 0, 10, 10]], [[0, 0, 10, 10]]), (1, 1, 0))

    def test_low_overlap_is_a_miss_and_a_false_positive(self):
        self.assertEqual(scorer.match([[0, 0, 10, 10]], [[6, 0, 16, 10]]), (0, 1, 1))

    def test_run_scoring_with_errors_distractors_and_unsupported_classes(self):
        truth = {
            "a": [("laptop", [0, 0, 10, 10])],
            "b": [("monitor", [0, 0, 10, 10])],
            "empty": [],
        }
        records = {
            "a": record("a", [det("laptop", [0, 0, 10, 10], 0.9)]),
            "b": record("b", [], error="RuntimeError: boom"),
            "empty": record("empty", [
                det("printer", [0, 0, 5, 5]),
                {"project_class": None, "mapping_status": "unsupported", "confidence": 0.9,
                 "box_xyxy_pixels": [0, 0, 5, 5]},
            ]),
        }
        result = scorer.score_run(truth, records)

        self.assertEqual(result["per_class"]["laptop"]["tp"], 1)
        self.assertEqual(result["per_class"]["monitor"]["fn"], 1)
        self.assertEqual(result["per_class"]["printer"]["fp"], 1)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["distractor_false_alarm_images"], 1)
        self.assertTrue(result["disqualified"])
        self.assertEqual(result["latency"]["count"], 2)

    def test_missing_annotation_path_refuses_to_score(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.csv"
            fields = ("image_id", "path", "expected_outcome", "annotation_path", "physical_device_id",
                      "location_session_id", "source", "permission_provenance_notes")
            with manifest.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=fields)
                writer.writeheader()
                writer.writerow({field: "x" for field in fields} | {
                    "expected_outcome": "laptop", "annotation_path": "",
                })
            with self.assertRaisesRegex(ValueError, "annotation_path"):
                scorer.load_ground_truth(manifest)

    def test_annotation_must_match_image_and_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.json"
            path.write_text(json.dumps({"image_id": "a", "boxes": [
                {"class": "tv", "box_xyxy_pixels": [0, 0, 1, 1]}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid class"):
                scorer.load_annotation(path, "a")
            with self.assertRaisesRegex(ValueError, "image_id"):
                scorer.load_annotation(path, "b")


if __name__ == "__main__":
    unittest.main()
