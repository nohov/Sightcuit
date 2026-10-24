import base64
from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
import unittest

import cv2
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

    def __init__(self, fail_first=False, label="printer", identified=True, hint="ok"):
        self.calls = []
        self.payloads = []
        self.fail_first = fail_first
        self.label, self.identified, self.hint = label, identified, hint

    def __call__(self, payload, model, timeout):
        prompt = payload["contents"][0]["parts"][1]["text"]
        regions = [line for line in prompt.splitlines() if line[:1].isdigit() and ": [" in line]
        self.calls.append(regions)
        self.payloads.append(payload)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("Gemini HTTP 503: overloaded")
        items = [{"index": i, "label": self.label, "identified": self.identified, "hint": self.hint}
                 for i in range(len(regions))]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}]}


class SyncExecutor:
    """Finishes every Gemini call before submit returns, so a frame's label lands on that same frame."""

    def submit(self, fn, *args):
        future = Future()
        try:
            future.set_result(fn(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future


class HeldExecutor:
    """Keeps every Gemini call unfinished until the test releases it, like a slow API."""

    def __init__(self):
        self.held = []

    def submit(self, fn, *args):
        future = Future()
        self.held.append((future, fn, args))
        return future

    def release(self):
        for future, fn, args in self.held:
            future.set_result(fn(*args))


def run(summaries, transport, min_call_interval=0.0, times=None, executor=None, between=None, min_track_frames=1):
    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in summaries]
    if between:
        frames = (between(index) or frame for index, frame in enumerate(frames))
    clock = iter(times or range(0, 1000)).__next__
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "live.jsonl"
        runner.run_live(frames, output, FakePredictor(summaries), CONFIG, "test-model", "unit test",
                        transport=transport, min_call_interval=min_call_interval, clock=clock,
                        executor=executor or SyncExecutor(), min_track_frames=min_track_frames)
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

    def test_part_boxes_inside_device_are_suppressed_and_keep_its_track(self):
        # Real one-laptop webcam run scaled by 0.4: a small "tower" box inside the laptop, then a
        # screen-only box (IoU 0.54 with the full laptop box) that previously stole the laptop's track.
        transport = FakeTransport()
        records = run([
            [row((0, 76, 194, 192), 0.64)],
            [row((0, 69, 252, 192), 0.93), row((15, 111, 44, 179), 0.12)],
            [row((0, 0, 256, 192), 0.25), row((0, 0, 155, 172), 0.13)],
            [row((7, 34, 192, 160), 0.47)],
        ], transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual([[d["track_id"] for d in r["detections"]] for r in records], [[0], [0], [0], [0]])
        self.assertEqual([len(r["suppressed_duplicate_proposals"]) for r in records], [0, 1, 1, 0])

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
        # clock is read once per frame
        records = run([[row(A)], [row(A), row(B)], [row(A), row(B)]], transport,
                      min_call_interval=2.0, times=[0, 1, 2])
        self.assertEqual([r["api_called"] for r in records], [True, False, True])
        self.assertIsNone(records[1]["raw_predictions"][1]["label_source"])

    def test_free_text_label_is_kept_with_detector_class(self):
        records = run([[row(A)]], FakeTransport(label="  Apple MacBook "))
        detection = records[0]["detections"][0]
        self.assertEqual(detection["label"], "Apple MacBook")
        self.assertEqual(detection["raw_class_name"], "printer")

    def test_none_label_is_not_a_detection(self):
        records = run([[row(A)]], FakeTransport(label="none"))
        self.assertEqual(records[0]["detections"], [])
        self.assertEqual(records[0]["raw_predictions"][0]["gemini_label"], "none")

    def test_empty_or_overlong_label_is_an_error(self):
        for label in ("  ", "x" * 61):
            records = run([[row(A)]], FakeTransport(label=label))
            self.assertIn("invalid label", records[0]["error"])

    def test_slow_gemini_does_not_block_detection(self):
        transport, executor = FakeTransport(), HeldExecutor()
        # Release the held call just before frame 3 is detected.
        records = run([[row(A)], [row(A), row(B)], [row(A), row(B)], [row(A), row(B)]], transport,
                      executor=executor, between=lambda i: executor.release() if i == 3 else None)
        # One call at a time: B is sent on the frame after A's answer lands.
        self.assertEqual([r["api_called"] for r in records], [True, False, False, False])
        self.assertEqual([len(r["detections"]) for r in records], [0, 0, 0, 1])
        self.assertEqual([len(r["raw_predictions"]) for r in records], [1, 2, 2, 2])
        self.assertEqual(records[3]["detections"][0]["label_source"], "gemini")

    def test_flicker_is_never_sent_and_stable_box_waits_for_min_frames(self):
        transport = FakeTransport()
        # B flickers for one frame; A stays for three.
        records = run([[row(A), row(B)], [row(A)], [row(A)]], transport, min_track_frames=3)
        self.assertEqual([r["api_called"] for r in records], [False, False, True])
        self.assertEqual(transport.calls, [["0: [100, 100, 500, 500]"]])

    def test_hidden_boxes_are_not_drawn(self):
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        proposal = {"box_xyxy_pixels": [30.0, 20.0, 150.0, 100.0]}
        stable = runner.MIN_TRACK_FRAMES
        runner.draw_tracks(frame, [
            {"track_id": 0, "label": "none", "hint": None, "seen": stable, "proposal": proposal},
            {"track_id": 1, "label": None, "hint": None, "seen": 1, "proposal": proposal},
        ])
        self.assertEqual(frame.sum(), 0)

    def test_detector_box_shows_before_gemini_answers(self):
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        proposal = {"box_xyxy_pixels": [30.0, 20.0, 150.0, 100.0], "raw_class_name": "phone"}
        runner.draw_tracks(frame, [{"track_id": 1, "label": None, "hint": None,
                                    "seen": runner.MIN_TRACK_FRAMES, "proposal": proposal}])
        self.assertGreater(frame[:, :, 2].sum(), 0)  # yellow has red; Gemini's green does not
        labelled = np.zeros_like(frame)
        runner.draw_tracks(labelled, [{"track_id": 1, "label": "Apple iPhone", "hint": None,
                                       "seen": runner.MIN_TRACK_FRAMES, "proposal": proposal}])
        self.assertEqual(labelled[:, :, 2].sum(), 0)
        self.assertGreater(labelled[:, :, 1].sum(), 0)

    def test_each_region_gets_a_full_resolution_close_up(self):
        transport = FakeTransport()
        run([[row(A), row(B, 0.8)]], transport)
        parts = transport.payloads[0]["contents"][0]["parts"]
        self.assertEqual([p.get("text") for p in parts[2::2]], ["Close-up of region 0:", "Close-up of region 1:"])
        crop = cv2.imdecode(np.frombuffer(base64.b64decode(parts[3]["inline_data"]["data"]), np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(crop.shape[:2], (104, 156))  # box A 120x80 plus 15% padding, clipped at the top edge

    def test_generic_label_shows_hint_and_is_reasked_after_interval(self):
        transport = FakeTransport(label="smartphone", identified=False, hint="move closer")
        records = run([[row(A)]] * 4, transport, times=[0, 5, 10, 11])
        self.assertEqual([r["api_called"] for r in records], [True, False, True, False])
        self.assertEqual(records[1]["detections"][0]["hint"], "move closer")
        self.assertFalse(records[1]["detections"][0]["identified"])

    def test_identified_label_is_never_reasked(self):
        transport = FakeTransport(label="Apple iPhone")
        records = run([[row(A)]] * 3, transport, times=[0, 50, 100])
        self.assertEqual(len(transport.calls), 1)
        self.assertIsNone(records[2]["detections"][0]["hint"])

    def test_answer_missing_hint_is_an_error(self):
        transport = FakeTransport(hint="try harder")
        records = run([[row(A)]], transport)
        self.assertIn("invalid identified or hint", records[0]["error"])

    def test_moved_phone_keeps_its_track_and_label(self):
        # Real session scaled down: the phone jumps with IoU 0.00-0.26 between detections.
        transport = FakeTransport(label="Apple iPhone")
        records = run([[row((100, 50, 160, 150))], [], [row((150, 60, 210, 160))], [row((95, 40, 155, 140))]], transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual([r["detections"][0]["track_id"] for r in records if r["detections"]], [0, 0, 0])

    def test_far_box_of_other_class_starts_new_track(self):
        transport = FakeTransport()
        far = {**row((150, 60, 210, 160)), "name": "laptop", "class": 0}
        records = run([[row((100, 50, 160, 150))], [far]], transport)
        self.assertEqual(len(transport.calls), 2)

    def test_no_proposals_makes_no_call(self):
        records = run([[], []], lambda *_: self.fail("transport should not be called"))
        self.assertEqual([r["api_called"] for r in records], [False, False])
        self.assertTrue(all(r["error"] is None for r in records))


class LatestFrameTests(unittest.TestCase):
    def test_yields_only_newest_frame_and_stops(self):
        latest = runner.LatestFrame()
        frames = iter(latest)
        latest.put("old")
        latest.put("new")
        self.assertEqual(next(frames), "new")
        latest.stop()
        self.assertEqual(list(frames), [])


if __name__ == "__main__":
    unittest.main()
