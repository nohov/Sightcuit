#!/usr/bin/env python3
"""Run the cascade on a live camera, labelling each tracked box with Gemini once and caching the label."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import logging
import math
import os
from pathlib import Path
import platform
import shlex
import sys
import threading
import time
from typing import Any, Callable, Iterable, Iterator

import cv2

from recognition.cascade_runner import (
    DEFAULT_CONFIG, DEFAULT_MODEL, DEFAULT_PROPOSAL_CONFIDENCE, HERE, LABELS, MAX_PROPOSALS, PROMPT_VERSION,
    RESPONSE_SCHEMA, parse_labels, region_text,
)
from recognition.gemini_runner import API_VERSION, Transport, build_payload, gemini_transport, response_text
from recognition.yolo_runner import UltralyticsPredictor, load_config, normalize_summary


# shortcut: greedy IoU matching with no motion model; switch to Ultralytics ByteTrack if the owner installs `lap`.
TRACK_IOU = 0.3
# A new box this close to a box already matched this frame is YOLO re-boxing the same device, not a new one.
DUPLICATE_IOU = 0.6
MAX_MISSED = 15
DEFAULT_MIN_CALL_INTERVAL = 2.0


def box_iou(a: list[float], b: list[float]) -> float:
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = width * height
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


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
            elif any(box_iou(box, t["proposal"]["box_xyxy_pixels"]) >= DUPLICATE_IOU for t in current):
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
) -> None:
    iou = config["thresholds"]["iou"] if iou is None else iou
    if not 0 <= proposal_confidence <= 1 or not 0 <= iou <= 1:
        raise ValueError("confidence and IoU thresholds must be between 0 and 1")
    template = (HERE / "prompt-cascade-v1.txt").read_text(encoding="utf-8")
    cache = TrackCache()
    last_call = -math.inf
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("a", encoding="utf-8") as destination:
        for frame_index, frame in enumerate(frames):
            started = time.perf_counter()
            tracks: list[dict[str, Any]] = []
            suppressed: list[dict[str, Any]] = []
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
                proposals = normalize_summary(result["raw_summary"], size, proposal_confidence, config)
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
                "thresholds": {"confidence": proposal_confidence, "iou": iou},
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "image_size_hw_pixels": image_size,
                "box_format": "xyxy pixels: [left, top, right, bottom] in the original frame",
                "raw_predictions": entries,
                "suppressed_duplicate_proposals": suppressed,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="per-frame JSONL output (appended)")
    parser.add_argument("--weights", required=True, type=Path, help="existing local YOLO-World weights")
    parser.add_argument("--allow-upload", action="store_true",
                        help="confirm camera frames may be uploaded to Google")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="pinned Gemini model ID")
    parser.add_argument("--proposal-confidence", type=float, default=DEFAULT_PROPOSAL_CONFIDENCE)
    parser.add_argument("--iou", type=float)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--min-call-interval", type=float, default=DEFAULT_MIN_CALL_INTERVAL,
                        help="minimum seconds between Gemini calls")
    parser.add_argument("--thinking-level", choices=("minimal", "low", "medium", "high"))
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not args.allow_upload:
        parser.error("--allow-upload is required: camera frames with new tracks are sent to Google")
    if not os.environ.get("GEMINI_API_KEY"):
        parser.error("GEMINI_API_KEY must be set in the environment")

    config = load_config(args.config)
    log_path = args.log or args.output.with_suffix(args.output.suffix + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    command = shlex.join([sys.executable, *sys.argv])
    logging.info("Starting command: %s", command)
    predictor = UltralyticsPredictor(args.weights, config)

    def detect(frames: Iterable[Any], show: Callable[..., bool] | None = None) -> None:
        run_live(
            frames, args.output, predictor, config, args.model, command,
            args.proposal_confidence, args.iou, args.device, args.timeout,
            min_call_interval=args.min_call_interval, show=show, thinking_level=args.thinking_level,
        )

    try:
        if args.no_display:
            with closing(camera_frames(args.camera)) as frames:
                detect(frames)
        else:
            run_with_display(args.camera, detect)
    except KeyboardInterrupt:
        pass
    finally:
        if not args.no_display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
