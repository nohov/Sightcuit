import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import cv2
import numpy as np

from recognition import live_runner as runner
from recognition import yolo_runner


CONFIG = yolo_runner.load_config(runner.DEFAULT_CONFIG)
A = (30, 20, 150, 100)
B = (200, 100, 290, 190)


def row(box, confidence=0.9, name="speaker"):
    x1, y1, x2, y2 = box
    return {"name": name, "class": CONFIG["expected_builtin_classes"].index(name), "confidence": confidence,
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
    """Labels every region it is sent as speaker and remembers each prompt's region lines."""

    def __init__(self, fail_first=False):
        self.calls = []
        self.fail_first = fail_first

    def __call__(self, payload, model, timeout):
        prompt = payload["contents"][0]["parts"][1]["text"]
        regions = [line for line in prompt.splitlines() if line[:1].isdigit() and ": [" in line]
        self.calls.append(regions)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("Gemini HTTP 503: overloaded")
        items = [{"index": i, "label": "speaker"} for i in range(len(regions))]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}]}


def run(summaries, transport, min_call_interval=0.0, times=None, size=(200, 300), min_box_side=0.0):
    frames = [np.zeros((*size, 3), dtype=np.uint8) for _ in summaries]
    clock = iter(times or range(0, 1000)).__next__
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "live.jsonl"
        runner.run_live(frames, output, FakePredictor(summaries), CONFIG, "test-model", "unit test",
                        transport=transport, min_call_interval=min_call_interval, clock=clock,
                        min_box_side=min_box_side)
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

    def test_large_part_box_is_suppressed_and_small_box_inside_gets_own_track(self):
        # Real one-laptop webcam run scaled by 0.4: a small "tower" box inside the laptop (6% of its area,
        # phone-sized, so Gemini judges it), then a screen-only box (54% of the area, IoU 0.54) that once
        # stole the laptop's track.
        transport = FakeTransport()
        records = run([
            [row((0, 76, 194, 192), 0.64)],
            [row((0, 69, 252, 192), 0.93), row((15, 111, 44, 179), 0.12)],
            [row((0, 0, 256, 192), 0.25), row((0, 0, 155, 172), 0.13)],
            [row((7, 34, 192, 160), 0.47)],
        ], transport)
        self.assertEqual([[d["track_id"] for d in r["detections"]] for r in records], [[0], [0, 1], [0], [0]])
        self.assertEqual([len(r["suppressed_duplicate_proposals"]) for r in records], [0, 0, 1, 0])

    def test_phone_lying_on_laptop_gets_its_own_track(self):
        # Real glasses frame: YOLO-World named both boxes "laptop"; the phone box is 9% of the laptop's area.
        laptop, phone = (123, 371, 504, 770), (391, 381, 504, 500)
        transport = FakeTransport()
        records = run([[row(laptop, name="laptop")], [row(laptop, name="laptop"), row(phone, 0.55, "laptop")]],
                      transport, size=(896, 504))
        self.assertEqual([d["track_id"] for d in records[1]["detections"]], [0, 1])
        self.assertEqual(records[1]["suppressed_duplicate_proposals"], [])
        self.assertEqual(len(transport.calls[1]), 1)

    def test_boxes_under_min_side_are_recorded_but_never_tracked_or_sent(self):
        # Real false "smartwatch" box from a glasses frame: 21 px wide.
        transport = FakeTransport()
        records = run([[row((271, 334, 292, 373), 0.44, "smartwatch")]], transport, size=(896, 504),
                      min_box_side=runner.DEFAULT_MIN_BOX_SIDE)
        self.assertEqual(transport.calls, [])
        self.assertEqual(records[0]["detections"], [])
        self.assertEqual(records[0]["too_small_proposals"][0]["box_xyxy_pixels"], [271.0, 334.0, 292.0, 373.0])

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


class LatestFrameTests(unittest.TestCase):
    def test_yields_only_newest_frame_and_stops(self):
        latest = runner.LatestFrame()
        frames = iter(latest)
        latest.put("old")
        latest.put("new")
        self.assertEqual(next(frames), "new")
        latest.stop()
        self.assertEqual(list(frames), [])


class RelayServerTests(unittest.TestCase):
    """Mocked HTTP relay checks; no model inference runs."""

    def setUp(self):
        self.latest = runner.LatestFrame()
        self.shown = {"tracks": [{"track_id": 0, "proposal": {"box_xyxy_pixels": [1.0, 2.0, 3.0, 4.0]},
                                  "label": "speaker"}], "image_size": [200, 300]}
        self.server = runner.make_relay_server(("127.0.0.1", 0), "secret", self.latest, self.shown, lambda: True)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, body, token="secret"):
        request = urllib.request.Request(f"http://127.0.0.1:{self.server.server_address[1]}/frame", data=body,
                                         headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_wrong_token_is_rejected(self):
        status, _ = self.post(b"x", token="wrong")
        self.assertEqual(status, 401)
        self.assertIsNone(self.latest.frame)

    def test_undecodable_body_is_rejected(self):
        status, _ = self.post(b"not a jpeg")
        self.assertEqual(status, 400)
        self.assertIsNone(self.latest.frame)

    def test_jpeg_reaches_detector_and_returns_last_tracks(self):
        _, jpeg = cv2.imencode(".jpg", np.zeros((200, 300, 3), dtype=np.uint8))
        status, body = self.post(jpeg.tobytes())
        self.assertEqual(status, 200)
        self.assertEqual(self.latest.frame.shape, (200, 300, 3))
        self.assertIs(self.shown["frame"], self.latest.frame)
        self.assertEqual(body, {"tracks": [{"track_id": 0, "box_xyxy_pixels": [1.0, 2.0, 3.0, 4.0],
                                            "label": "speaker"}], "image_size_hw_pixels": [200, 300]})

    def get(self, path):
        return urllib.request.urlopen(f"http://127.0.0.1:{self.server.server_address[1]}{path}", timeout=5)

    def test_dashboard_streams_need_the_token(self):
        for path in ("/events?token=wrong", "/stream.mjpg"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.get(path)
            self.assertEqual(caught.exception.code, 401)

    def test_events_send_the_last_detection_as_a_dashboard_record(self):
        self.shown.update(seq=3, tracks=[{"track_id": 4, "label": "laptop", "labelled_frame": 2,
                                          "proposal": {"box_xyxy_pixels": [1.0, 2.0, 3.0, 4.0], "confidence": 0.5}}])
        with self.get("/events?token=secret") as response:
            self.assertEqual(response.headers["Content-Type"], "text/event-stream")
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
            line = response.readline().decode()
        record = json.loads(line.removeprefix("data: "))
        self.assertEqual(record["frame_index"], 2)
        self.assertEqual(record["image_size_hw_pixels"], [200, 300])
        self.assertEqual(record["tracks"], [{"track_id": 4, "gemini_label": "laptop", "label_source": "gemini",
                                             "proposal": {"box_xyxy_pixels": [1.0, 2.0, 3.0, 4.0],
                                                          "confidence": 0.5}}])

    def test_stream_sends_the_newest_relayed_frame_as_jpeg(self):
        self.shown["frame"] = np.zeros((20, 30, 3), dtype=np.uint8)
        with self.get("/stream.mjpg?token=secret") as response:
            self.assertTrue(response.headers["Content-Type"].startswith("multipart/x-mixed-replace"))
            self.assertEqual(response.readline(), b"--frame\r\n")
            self.assertEqual(response.readline(), b"Content-Type: image/jpeg\r\n")
            length = int(response.readline().split(b":")[1])
            response.readline()
            jpeg = response.read(length)
        self.assertEqual(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR).shape, (20, 30, 3))

    def test_record_marks_cached_and_pending_labels(self):
        record = runner.dashboard_record({"seq": 10, "image_size": [1, 1], "tracks": [
            {"track_id": 0, "label": "phone", "labelled_frame": 3, "proposal": {"box_xyxy_pixels": [0, 0, 1, 1]}},
            {"track_id": 1, "label": None, "labelled_frame": None, "proposal": {"box_xyxy_pixels": [0, 0, 1, 1]}},
        ]})
        self.assertEqual([t["label_source"] for t in record["tracks"]], ["track_cache", None])
        self.assertIsNone(record["tracks"][0]["proposal"]["confidence"])


if __name__ == "__main__":
    unittest.main()
