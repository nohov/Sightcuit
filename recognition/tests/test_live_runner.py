import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from recognition import live_runner as runner
from recognition import yolo_runner


CONFIG = yolo_runner.load_config(runner.DEFAULT_CONFIG)
A = (30, 20, 150, 100)
B = (200, 100, 290, 190)


def row(box, confidence=0.9):
    x1, y1, x2, y2 = box
    return {"name": "printer", "class": 3, "confidence": confidence,
            "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}


class FakePredictor:
    runtime_version = "test-only"
    weights_sha256 = "0" * 64

    def __init__(self, summaries):
        self.summaries = iter(summaries)

    def predict(self, frame, confidence, iou, device, agnostic_nms=False):
        assert agnostic_nms
        return {"raw_summary": next(self.summaries), "image_size": frame.shape[:2]}


class FakeTransport:
    """Labels every region it is sent as printer and remembers each prompt's region lines."""

    def __init__(self, fail_first=False):
        self.calls = []
        self.fail_first = fail_first

    def __call__(self, payload, model, timeout):
        prompt = payload["contents"][0]["parts"][1]["text"]
        regions = [line for line in prompt.splitlines() if line[:1].isdigit() and ": [" in line]
        self.calls.append(regions)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("Gemini HTTP 503: overloaded")
        items = [{"index": i, "label": "printer"} for i in range(len(regions))]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}]}


def run(summaries, transport, min_call_interval=0.0, times=None):
    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in summaries]
    clock = iter(times or range(0, 1000)).__next__
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "live.jsonl"
        runner.run_live(frames, output, FakePredictor(summaries), CONFIG, "test-model", "unit test",
                        transport=transport, min_call_interval=min_call_interval, clock=clock)
        return [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]


class LiveRunnerTests(unittest.TestCase):
    def test_stable_object_is_labelled_once_then_cached(self):
        transport = FakeTransport()
        records = run([[row(A)], [row((32, 22, 152, 102))], [row(A)]], transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual([r["api_called"] for r in records], [True, False, False])
        self.assertEqual([r["detections"][0]["label_source"] for r in records],
                         ["gemini", "track_cache", "track_cache"])
        self.assertEqual({r["detections"][0]["track_id"] for r in records}, {0})
        self.assertIsNone(records[1]["detections"][0]["confidence"])

    def test_only_new_tracks_are_sent(self):
        transport = FakeTransport()
        records = run([[row(A)], [row(A), row(B, 0.8)]], transport)
        self.assertEqual([len(regions) for regions in transport.calls], [1, 1])
        self.assertEqual(transport.calls[1], ["0: [500, 667, 950, 967]"])
        self.assertEqual(sorted(d["label_source"] for d in records[1]["detections"]), ["gemini", "track_cache"])

    def test_duplicate_box_of_same_device_is_suppressed(self):
        # Real webcam boxes scaled by 0.4: a tight laptop box, then a wider low-confidence box around it (IoU 0.7).
        transport = FakeTransport()
        records = run([[row((36, 66, 168, 191), 0.36)],
                       [row((36, 66, 168, 191), 0.36), row((34, 66, 223, 192), 0.15)]], transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(len(records[1]["detections"]), 1)
        self.assertEqual(records[1]["suppressed_duplicate_proposals"][0]["box_xyxy_pixels"],
                         [34.0, 66.0, 223.0, 192.0])

    def test_lost_track_is_evicted_and_relabelled(self):
        transport = FakeTransport()
        gap = [[]] * (runner.MAX_MISSED + 1)
        records = run([[row(A)], *gap, [row(A)]], transport)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(records[-1]["detections"][0]["track_id"], 1)

    def test_short_gap_keeps_cached_label(self):
        transport = FakeTransport()
        records = run([[row(A)], [], [row(A)]], transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(records[-1]["detections"][0]["label_source"], "track_cache")

    def test_gemini_error_is_recorded_and_retried(self):
        transport = FakeTransport(fail_first=True)
        records = run([[row(A)], [row(A)]], transport)
        self.assertIn("503", records[0]["error"])
        self.assertEqual(records[0]["detections"], [])
        self.assertIsNone(records[1]["error"])
        self.assertEqual(records[1]["detections"][0]["label_source"], "gemini")

    def test_calls_are_spaced_by_min_interval(self):
        transport = FakeTransport()
        # clock is read on the first frame's check and on its call, then once per later check
        records = run([[row(A)], [row(A), row(B)], [row(A), row(B)]], transport,
                      min_call_interval=2.0, times=[0, 0, 1, 2, 2])
        self.assertEqual([r["api_called"] for r in records], [True, False, True])
        self.assertIsNone(records[1]["raw_predictions"][1]["label_source"])

    def test_no_proposals_makes_no_call(self):
        records = run([[], []], lambda *_: self.fail("transport should not be called"))
        self.assertEqual([r["api_called"] for r in records], [False, False])
        self.assertTrue(all(r["error"] is None for r in records))


if __name__ == "__main__":
    unittest.main()
