#!/usr/bin/env python3
"""Run the cascade on a live camera, labelling each tracked box with Gemini once and caching the label."""

from __future__ import annotations

import argparse
from contextlib import closing
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import math
import os
from pathlib import Path
import platform
import re
import secrets
import threading
import time
from typing import Any, Callable, Iterable, Iterator
from urllib.parse import parse_qs, urlsplit

import cv2
import numpy as np

from recognition.cascade_runner import (
    DEFAULT_CONFIG, DEFAULT_MODEL, DEFAULT_PROPOSAL_CONFIDENCE, HERE, LABELS, MAX_PROPOSALS, PROMPT_VERSION,
    RESPONSE_SCHEMA, parse_labels, region_text,
)
from recognition.gemini_runner import API_VERSION, Transport, build_payload, gemini_transport, response_text
from recognition.runio import start_logging
from recognition.yolo_runner import UltralyticsPredictor, load_config, normalize_summary


# shortcut: greedy IoU matching with no motion model; switch to Ultralytics ByteTrack if the owner installs `lap`.
TRACK_IOU = 0.3
# A new box this close to a box already matched this frame, or mostly inside a same-class one and at least
# PART_MIN_AREA of its size, is YOLO re-boxing that device or a large part of it (a screen). Smaller boxes
# inside it get their own track and a Gemini label: on real glasses frames YOLO-World called a phone lying
# on a laptop "laptop", at 4-10% of the laptop box's area.
DUPLICATE_IOU = 0.6
CONTAINED_FRACTION = 0.8
PART_MIN_AREA = 0.2
MAX_MISSED = 15
# On 504x896 glasses frames, boxes under 32 px on their short side were mostly false smartwatches that Gemini
# confirmed anyway (5 of 8), and only 2 of 216 phone hits; too few pixels to judge.
DEFAULT_MIN_BOX_SIDE = 32.0
DEFAULT_MIN_CALL_INTERVAL = 2.0


def box_area(box: list[float]) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def intersection(a: list[float], b: list[float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def box_iou(a: list[float], b: list[float]) -> float:
    inter = intersection(a, b)
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def is_duplicate(proposal: dict[str, Any], other: dict[str, Any]) -> bool:
    box, other_box = proposal["box_xyxy_pixels"], other["box_xyxy_pixels"]
    return (box_iou(box, other_box) >= DUPLICATE_IOU
            or (proposal["raw_class_name"] == other["raw_class_name"]
                and intersection(box, other_box) >= CONTAINED_FRACTION * box_area(box)
                and box_area(box) >= PART_MIN_AREA * box_area(other_box)))


class TrackCache:
    """In-memory, per-session map from track ID to its proposal and cached Gemini label."""

    def __init__(self) -> None:
        self.tracks: dict[int, dict[str, Any]] = {}
        self.next_id = 0

    def update(self, proposals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (current tracks, suppressed duplicate proposals)."""
        unmatched = set(self.tracks)
        current: list[dict[str, Any]] = []
        suppressed = []
        for proposal in sorted(proposals, key=lambda p: -p["confidence"]):
            box = proposal["box_xyxy_pixels"]
            best = max(unmatched, default=None,
                       key=lambda i: box_iou(box, self.tracks[i]["proposal"]["box_xyxy_pixels"]))
            if best is not None and box_iou(box, self.tracks[best]["proposal"]["box_xyxy_pixels"]) >= TRACK_IOU:
                unmatched.discard(best)
                track = self.tracks[best]
            elif any(is_duplicate(proposal, t["proposal"]) for t in current):
                suppressed.append(proposal)
                continue
            else:
                track = self.tracks[self.next_id] = {"track_id": self.next_id, "label": None, "labelled_frame": None}
                self.next_id += 1
            track.update(proposal=proposal, missed=0)
            current.append(track)
        for track_id in unmatched:
            self.tracks[track_id]["missed"] += 1
            if self.tracks[track_id]["missed"] > MAX_MISSED:
                del self.tracks[track_id]
        return current, suppressed


def run_live(
    frames: Iterable[Any],
    output: Path,
    predictor: Any,
    config: dict[str, Any],
    model: str,
    command: str,
    proposal_confidence: float = DEFAULT_PROPOSAL_CONFIDENCE,
    iou: float | None = None,
    device: str = "cpu",
    timeout: float = 120.0,
    transport: Transport = gemini_transport,
    min_call_interval: float = DEFAULT_MIN_CALL_INTERVAL,
    clock: Callable[[], float] = time.monotonic,
    show: Callable[[Any, list[dict[str, Any]]], bool] | None = None,
    thinking_level: str | None = None,
    min_box_side: float = DEFAULT_MIN_BOX_SIDE,
) -> None:
    iou = config["thresholds"]["iou"] if iou is None else iou
    if not 0 <= proposal_confidence <= 1 or not 0 <= iou <= 1:
        raise ValueError("confidence and IoU thresholds must be between 0 and 1")
    if min_box_side < 0:
        raise ValueError("minimum box side must not be negative")
    template = (HERE / "prompt-cascade-v2.txt").read_text(encoding="utf-8")
    cache = TrackCache()
    last_call = -math.inf
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("a", encoding="utf-8") as destination:
        for frame_index, frame in enumerate(frames):
            started = time.perf_counter()
            tracks: list[dict[str, Any]] = []
            suppressed: list[dict[str, Any]] = []
            too_small: list[dict[str, Any]] = []
            api_called = False
            response: dict[str, Any] = {}
            raw_response = None
            error = None
            image_size = None
            try:
                size = tuple(frame.shape[:2])
                image_size = list(size)
                result = predictor.predict(frame, proposal_confidence, iou, device, agnostic_nms=True)
                if tuple(result["image_size"]) != size:
                    raise ValueError("YOLO and camera frame disagree on image size")
                proposals = []
                for proposal in normalize_summary(result["raw_summary"], size, proposal_confidence, config):
                    x1, y1, x2, y2 = proposal["box_xyxy_pixels"]
                    (too_small if min(x2 - x1, y2 - y1) < min_box_side else proposals).append(proposal)
                tracks, suppressed = cache.update(sorted(proposals, key=lambda p: -p["confidence"])[:MAX_PROPOSALS])
                pending = [track for track in tracks if track["label"] is None]
                # Only unlabelled tracks go to Gemini; cached labels cost no API call.
                if pending and clock() - last_call >= min_call_interval:
                    last_call = clock()
                    encoded, jpeg = cv2.imencode(".jpg", frame)
                    if not encoded:
                        raise RuntimeError("could not JPEG-encode camera frame")
                    prompt = template.replace("{regions}", region_text([t["proposal"] for t in pending], size))
                    api_called = True
                    response = transport(
                        build_payload(jpeg.tobytes(), "image/jpeg", prompt, thinking_level, RESPONSE_SCHEMA),
                        model, timeout,
                    )
                    raw_response = response_text(response)
                    for track, label in zip(pending, parse_labels(json.loads(raw_response), len(pending))):
                        track["label"], track["labelled_frame"] = label, frame_index
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                logging.exception("Live frame failed frame=%d", frame_index)

            entries = [{
                "track_id": track["track_id"],
                "proposal": track["proposal"],
                "gemini_label": track["label"],
                "labelled_frame": track["labelled_frame"],
                "label_source": None if track["label"] is None
                else "gemini" if track["labelled_frame"] == frame_index else "track_cache",
            } for track in tracks]
            record = {
                "schema_version": "1.0.0",
                "frame_index": frame_index,
                "timestamp": time.time(),
                "task": "object_detection",
                "model_identifier": (
                    f"{config['model_identifier']} proposals -> Gemini {model} labels "
                    f"({PROMPT_VERSION}, thinking={thinking_level or 'model default'}, live track cache)"
                ),
                "weights_sha256": getattr(predictor, "weights_sha256", None),
                "runtime": "ultralytics+gemini-api",
                "runtime_version": f"ultralytics {getattr(predictor, 'runtime_version', None)}; gemini {API_VERSION}",
                "model_version": response.get("modelVersion"),
                "prompt_version": PROMPT_VERSION,
                "usage": response.get("usageMetadata"),
                "api_called": api_called,
                "device": device,
                "hardware": {"system": platform.system(), "machine": platform.machine()},
                "command": command,
                "thresholds": {"confidence": proposal_confidence, "iou": iou, "min_box_side_pixels": min_box_side},
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "image_size_hw_pixels": image_size,
                "box_format": "xyxy pixels: [left, top, right, bottom] in the original frame",
                "raw_predictions": entries,
                "suppressed_duplicate_proposals": suppressed,
                "too_small_proposals": too_small,
                "raw_response": raw_response,
                "detections": [{
                    "track_id": entry["track_id"],
                    "raw_class_id": LABELS.index(entry["gemini_label"]),
                    "raw_class_name": entry["gemini_label"],
                    "confidence": None,
                    "box_xyxy_pixels": entry["proposal"]["box_xyxy_pixels"],
                    "project_class": entry["gemini_label"],
                    "mapping_status": "mapped",
                    "label_source": entry["label_source"],
                } for entry in entries if entry["gemini_label"] in LABELS],
                "error": error,
            }
            destination.write(json.dumps(record, separators=(",", ":")) + "\n")
            destination.flush()
            if show and not show(frame, tracks):
                break


def camera_frames(index: int) -> Iterator[Any]:
    capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        raise RuntimeError(f"cannot open camera {index}")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"camera {index} stopped returning frames")
            yield frame
    finally:
        capture.release()


class LatestFrame:
    """Hand the detector only the newest camera frame; frames it was too slow for are dropped."""

    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.frame: Any = None
        self.stopped = False

    def put(self, frame: Any) -> None:
        with self.condition:
            self.frame = frame
            self.condition.notify()

    def stop(self) -> None:
        with self.condition:
            self.stopped = True
            self.condition.notify()

    def __iter__(self) -> Iterator[Any]:
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.frame is not None or self.stopped)
                if self.stopped:
                    return
                frame, self.frame = self.frame, None
            yield frame


def draw_tracks(frame: Any, tracks: list[dict[str, Any]]) -> None:
    for track in tracks:
        x1, y1, x2, y2 = (int(v) for v in track["proposal"]["box_xyxy_pixels"])
        label = track["label"] or "..."
        color = (128, 128, 128) if label in ("none", "...") else (0, 200, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"#{track['track_id']} {label}", (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def run_with_display(camera: int, detect: Callable[[Iterable[Any], Callable[..., bool]], None]) -> None:
    """Show every camera frame at camera speed while detection runs on the newest frame in a worker thread.

    Boxes are the last finished detection, so they trail a moving device by up to one inference.
    """
    latest = LatestFrame()
    shown: dict[str, list[dict[str, Any]]] = {"tracks": []}
    failure: list[BaseException] = []

    def keep(frame: Any, tracks: list[dict[str, Any]]) -> bool:
        shown["tracks"] = [dict(track) for track in tracks]  # snapshot: the worker keeps mutating the cache
        return not latest.stopped

    def work() -> None:
        try:
            detect(latest, keep)
        except BaseException as exc:
            failure.append(exc)

    worker = threading.Thread(target=work, name="live-detector")
    with closing(camera_frames(camera)) as frames:
        worker.start()
        try:
            for frame in frames:
                if not worker.is_alive():
                    break
                latest.put(frame.copy())
                draw_tracks(frame, shown["tracks"])
                cv2.imshow("scavscrap live (q quits)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            latest.stop()
            worker.join()  # may wait for an in-flight inference or Gemini call to finish
    if failure:
        raise failure[0]


MAX_RELAY_FRAME_BYTES = 5 * 1024 * 1024
STREAM_POLL_SECONDS = 0.03
EVENTS_KEEPALIVE_SECONDS = 15.0
STREAM_JPEG_QUALITY = 80


def dashboard_record(shown: dict[str, Any]) -> dict[str, Any]:
    """The last finished detection, shaped like the frames the dashboard reads (see frontend/src/feed.js)."""
    frame_index = shown.get("seq", 0) - 1
    return {
        "frame_index": frame_index,
        "timestamp": time.time(),
        "image_size_hw_pixels": shown.get("image_size"),
        "tracks": [{
            "track_id": track["track_id"],
            "proposal": {
                "box_xyxy_pixels": track["proposal"]["box_xyxy_pixels"],
                "confidence": track["proposal"].get("confidence"),
            },
            "gemini_label": track.get("label"),
            "label_source": None if track.get("label") is None
            else "gemini" if track.get("labelled_frame") == frame_index else "track_cache",
        } for track in shown.get("tracks", [])],
    }


def make_relay_server(
    address: tuple[str, int], token: str, latest: LatestFrame,
    shown: dict[str, Any], detector_alive: Callable[[], bool],
) -> ThreadingHTTPServer:
    """HTTP endpoint for the iOS glasses relay: POST /frame with a JPEG, get the last finished tracks back.

    The dashboard reads two GET endpoints, authorized with ?token= because browsers cannot set headers on
    <img> or EventSource requests:
      /stream.mjpg  newest relayed frame as an MJPEG stream (no boxes drawn; the dashboard draws them)
      /events       Server-Sent Events, one dashboard_record() per finished detection

    shortcut: plain HTTP on the LAN behind a bearer token; add TLS or a tunnel before using shared networks.
    """
    expected = f"Bearer {token}".encode()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def start_stream(self, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            supplied = (parse_qs(url.query).get("token") or [""])[0]
            if url.path not in ("/stream.mjpg", "/events"):
                return self.reply(404, {"error": "not found"})
            if not hmac.compare_digest(f"Bearer {supplied}".encode(), expected):
                return self.reply(401, {"error": "bad token"})
            try:
                if url.path == "/stream.mjpg":
                    self.stream_frames()
                else:
                    self.stream_events()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser closed the tab or reconnected

        def stream_frames(self) -> None:
            self.start_stream("multipart/x-mixed-replace; boundary=frame")
            last = None
            while detector_alive():
                frame = shown.get("frame")
                if frame is None or frame is last:
                    time.sleep(STREAM_POLL_SECONDS)
                    continue
                last = frame
                encoded, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY])
                if not encoded:
                    continue
                data = jpeg.tobytes()
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
                self.wfile.flush()

        def stream_events(self) -> None:
            self.start_stream("text/event-stream")
            last_seq = None
            last_write = time.monotonic()
            while detector_alive():
                seq = shown.get("seq", 0)
                if seq and seq != last_seq:
                    last_seq = seq
                    payload = json.dumps(dashboard_record(shown), separators=(",", ":"))
                    self.wfile.write(f"data: {payload}\n\n".encode())
                elif time.monotonic() - last_write >= EVENTS_KEEPALIVE_SECONDS:
                    self.wfile.write(b": keepalive\n\n")
                else:
                    time.sleep(STREAM_POLL_SECONDS)
                    continue
                self.wfile.flush()
                last_write = time.monotonic()

        def do_POST(self) -> None:
            if self.path != "/frame":
                return self.reply(404, {"error": "not found"})
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return self.reply(401, {"error": "bad token"})
            if not detector_alive():
                return self.reply(503, {"error": "detector stopped"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_RELAY_FRAME_BYTES:
                return self.reply(400, {"error": "JPEG body missing or too large"})
            frame = cv2.imdecode(np.frombuffer(self.rfile.read(length), np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                return self.reply(400, {"error": "body is not a decodable image"})
            latest.put(frame)
            shown["frame"] = frame  # newest received frame for the laptop preview
            self.reply(200, {
                "tracks": [{"track_id": t["track_id"], "box_xyxy_pixels": t["proposal"]["box_xyxy_pixels"],
                            "label": t["label"]} for t in shown["tracks"]],
                "image_size_hw_pixels": shown["image_size"],
            })

        def log_message(self, format: str, *args: Any) -> None:
            logging.info("relay %s " + format, self.address_string(), *args)

    return ThreadingHTTPServer(address, Handler)


def show_relay_frames(shown: dict[str, Any], running: Callable[[], bool]) -> None:
    """Show the newest relayed frame with the last finished boxes until q or the detector stops."""
    last = None
    while running():
        frame = shown["frame"]
        if frame is None:
            time.sleep(0.03)  # no window yet, so waitKey would return at once
            continue
        if frame is not last:
            last = frame
            view = frame.copy()
            draw_tracks(view, shown["tracks"])
            cv2.imshow("scavscrap relay (q quits)", view)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()


def serve_relay(
    host: str, port: int, token: str, detect: Callable[[Iterable[Any], Callable[..., bool]], None],
    display: bool = False,
) -> None:
    """Run detection on frames POSTed by the iOS glasses relay until Ctrl-C, q, or the detector fails."""
    latest = LatestFrame()
    shown: dict[str, Any] = {"tracks": [], "image_size": None, "frame": None, "seq": 0}
    failure: list[BaseException] = []

    def keep(frame: Any, tracks: list[dict[str, Any]]) -> bool:
        shown["tracks"] = [dict(track) for track in tracks]  # snapshot: the worker keeps mutating the cache
        shown["image_size"] = list(frame.shape[:2])
        shown["seq"] += 1  # one per finished detection; tells /events there is a new record
        return not latest.stopped

    def work() -> None:
        try:
            detect(latest, keep)
        except BaseException as exc:
            failure.append(exc)

    worker = threading.Thread(target=work, name="live-detector")
    server = make_relay_server((host, port), token, latest, shown, worker.is_alive)
    worker.start()
    # Token goes to the terminal only, never the log file.
    print(f"relay listening on {host}:{server.server_address[1]}; token {token}", flush=True)
    print(f"dashboard: open http://localhost:5173/?relay=http://localhost:{server.server_address[1]}"
          f"&token={token}", flush=True)
    # macOS only allows OpenCV windows on the main thread, so the server moves off it when displaying.
    server_thread = threading.Thread(target=server.serve_forever, name="relay-server")
    try:
        if display:
            server_thread.start()
            show_relay_frames(shown, worker.is_alive)
        else:
            server.serve_forever()
    finally:
        if server_thread.is_alive():
            server.shutdown()
        server.server_close()
        latest.stop()
        worker.join()
    if failure:
        raise failure[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="per-frame JSONL output (appended)")
    parser.add_argument("--weights", required=True, type=Path, help="existing local YOLO-World weights")
    parser.add_argument("--allow-upload", action="store_true",
                        help="confirm camera frames may be uploaded to Google")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--listen", metavar="HOST:PORT",
                        help="take frames from the iOS glasses relay over HTTP instead of --camera")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="pinned Gemini model ID")
    parser.add_argument("--proposal-confidence", type=float, default=DEFAULT_PROPOSAL_CONFIDENCE)
    parser.add_argument("--iou", type=float)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--min-call-interval", type=float, default=DEFAULT_MIN_CALL_INTERVAL,
                        help="minimum seconds between Gemini calls")
    parser.add_argument("--thinking-level", choices=("minimal", "low", "medium", "high"))
    parser.add_argument("--min-box-side", type=float, default=DEFAULT_MIN_BOX_SIDE,
                        help="ignore proposals whose shorter side is under this many pixels")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not args.allow_upload:
        parser.error("--allow-upload is required: camera frames with new tracks are sent to Google")
    if not os.environ.get("GEMINI_API_KEY"):
        parser.error("GEMINI_API_KEY must be set in the environment")
    # A fixed token keeps the phone app and dashboard connected across relay restarts.
    # Hex, not urlsafe: Terminal's double-click selection stops at "-", truncating pasted tokens.
    token = os.environ.get("SCAVSCRAP_RELAY_TOKEN") or secrets.token_hex(16)
    if not re.fullmatch(r"[0-9a-f]{32,}", token):
        parser.error("SCAVSCRAP_RELAY_TOKEN must be at least 32 lowercase hex characters")

    config = load_config(args.config)
    command = start_logging(args.output, args.log)
    predictor = UltralyticsPredictor(args.weights, config)

    def detect(frames: Iterable[Any], show: Callable[..., bool] | None = None) -> None:
        run_live(
            frames, args.output, predictor, config, args.model, command,
            args.proposal_confidence, args.iou, args.device, args.timeout,
            min_call_interval=args.min_call_interval, show=show, thinking_level=args.thinking_level,
            min_box_side=args.min_box_side,
        )

    try:
        if args.listen:
            host, _, port = args.listen.rpartition(":")
            serve_relay(host, int(port), token, detect, display=not args.no_display)
        elif args.no_display:
            with closing(camera_frames(args.camera)) as frames:
                detect(frames)
        else:
            run_with_display(args.camera, detect)
    except KeyboardInterrupt:
        pass
    finally:
        if not args.no_display and not args.listen:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
