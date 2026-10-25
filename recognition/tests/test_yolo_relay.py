import unittest

import numpy as np

from recognition import yolo_relay


def row(name, x1, conf=0.8, cls=3):
    return {"name": name, "class": cls, "confidence": conf,
            "box": {"x1": float(x1), "y1": 0.0, "x2": float(x1 + 20), "y2": 40.0}}


class FakePredictor:
    def __init__(self, summaries):
        self.summaries = iter(summaries)
        self.calls = []

    def predict(self, frame, confidence, iou, device):
        self.calls.append((confidence, iou, device))
        return {"raw_summary": next(self.summaries)}


class TrackerTests(unittest.TestCase):
    def test_raw_class_is_kept_unmapped_and_shown_after_two_frames(self):
        tracker = yolo_relay.Tracker()
        self.assertEqual(tracker.update([row("resistor", 0)]), [])  # one frame could be a false positive
        [track] = tracker.update([row("resistor", 2)])
        self.assertEqual(track["label"], "resistor")
        self.assertEqual(track["proposal"]["box_xyxy_pixels"], [2.0, 0.0, 22.0, 40.0])
        self.assertEqual(track["proposal"]["raw_class_id"], 3)
        self.assertIsNone(track["proposal"]["project_class"])

    def test_id_is_stable_and_box_is_held_through_short_misses(self):
        tracker = yolo_relay.Tracker()
        tracker.update([row("red_led", 0)])
        first = tracker.update([row("red_led", 3)])[0]["track_id"]
        for _ in range(yolo_relay.HOLD):
            self.assertEqual([t["track_id"] for t in tracker.update([])], [first])
        self.assertEqual(tracker.update([]), [])
        self.assertEqual(tracker.update([row("red_led", 3)]), [])  # gone too long: a new track starts over

    def test_part_inside_another_class_box_is_not_suppressed(self):
        tracker = yolo_relay.Tracker()
        board = {"name": "board", "class": 0, "confidence": 0.9,
                 "box": {"x1": 0.0, "y1": 0.0, "x2": 400.0, "y2": 400.0}}
        for _ in range(2):
            shown = tracker.update([board, row("resistor", 100)])
        self.assertEqual(sorted(t["label"] for t in shown), ["board", "resistor"])


class DetectTests(unittest.TestCase):
    def test_detect_passes_thresholds_and_stops_when_keep_says_so(self):
        predictor = FakePredictor([[row("resistor", 0)]] * 3)
        kept = []
        frames = [np.zeros((4, 4, 3), np.uint8)] * 3
        yolo_relay.yolo_detect(predictor, 0.25, 0.5, "mps")(frames, lambda f, t: kept.append(t) or len(kept) < 2)
        self.assertEqual(predictor.calls, [(0.25, 0.5, "mps")] * 2)
        self.assertEqual(kept[1][0]["label"], "resistor")


if __name__ == "__main__":
    unittest.main()
