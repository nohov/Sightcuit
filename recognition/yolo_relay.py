#!/usr/bin/env python3
"""Detector-only glasses relay: raw YOLO boxes for any class list, no Gemini, for live-testing a detector."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any, Callable, Iterable

from recognition.live_runner import MIN_TRACK_FRAMES, box_iou, continues, serve_relay
from recognition.yolo_runner import UltralyticsPredictor

SHOW_AFTER = 2  # frames a box must persist before it is shown, so one-frame false positives stay hidden
HOLD = 3  # frames a lost box stays on screen (~0.4 s at 7 fps), so a missed frame does not blink it out


class Tracker:
    """Same-class IoU matching for stable IDs. Unlike live_runner.TrackCache it suppresses nothing across
    classes: a resistor inside the board's box is its own detection, not a duplicate of the board."""

    def __init__(self) -> None:
        self.tracks: dict[int, dict[str, Any]] = {}
        self.next_id = 0

    def update(self, summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ultralytics summary rows in, relay tracks out; the raw class name is the label, nothing is mapped."""
        unmatched = set(self.tracks)
        for row in sorted(summary, key=lambda r: -r["confidence"]):
            proposal = {
                "box_xyxy_pixels": [row["box"][key] for key in ("x1", "y1", "x2", "y2")],
                "confidence": row["confidence"],
                "raw_class_id": row["class"],
                "raw_class_name": row["name"],
                "project_class": None,
            }
            box = proposal["box_xyxy_pixels"]
            match = max((i for i in unmatched if continues(proposal, self.tracks[i]["proposal"])), default=None,
                        key=lambda i: box_iou(box, self.tracks[i]["proposal"]["box_xyxy_pixels"]))
            if match is None:
                match, self.next_id = self.next_id, self.next_id + 1
                self.tracks[match] = {"hits": 0}
            unmatched.discard(match)
            track = self.tracks[match]
            track.update(proposal=proposal, hits=track["hits"] + 1, missed=0)
        for track_id in unmatched:
            self.tracks[track_id]["missed"] += 1
            if self.tracks[track_id]["missed"] > HOLD:
                del self.tracks[track_id]
        return [{
            "track_id": track_id,
            "label": track["proposal"]["raw_class_name"],
            "hint": None,
            "seen": MIN_TRACK_FRAMES,  # SHOW_AFTER already gated it; live_runner's preview wants this many
            "proposal": track["proposal"],
        } for track_id, track in self.tracks.items() if track["hits"] >= SHOW_AFTER]


def yolo_detect(predictor: Any, confidence: float, iou: float, device: str
                ) -> Callable[[Iterable[Any], Callable[..., bool]], None]:
    def detect(frames: Iterable[Any], keep: Callable[..., bool]) -> None:
        tracker = Tracker()
        for frame in frames:
            result = predictor.predict(frame, confidence, iou, device)
            if not keep(frame, tracker.update(result["raw_summary"])):
                return
    return detect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True,
                        help="model JSON; only weights_filename, expected_builtin_classes and thresholds are used")
    parser.add_argument("--listen", metavar="HOST:PORT", default="0.0.0.0:8765")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-display", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("SCAVSCRAP_RELAY_TOKEN") or secrets.token_hex(16)
    if not re.fullmatch(r"[0-9a-f]{32,}", token):
        parser.error("SCAVSCRAP_RELAY_TOKEN must be at least 32 lowercase hex characters")
    # Not validated against labels/classes.json on purpose: this tests detectors with other class lists.
    config = json.loads(args.config.read_text(encoding="utf-8"))
    predictor = UltralyticsPredictor(args.weights, config)  # checks filename and class list against the config
    thresholds = config["thresholds"]
    host, _, port = args.listen.rpartition(":")
    try:
        serve_relay(host, int(port), token, yolo_detect(predictor, thresholds["confidence"], thresholds["iou"],
                                                        args.device), display=not args.no_display)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
