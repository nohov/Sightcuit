#!/usr/bin/env python3
"""Run five-class object detection through the Gemini API (images leave this machine)."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import math
import os
from pathlib import Path
import platform
import shlex
import sys
import tempfile
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from recognition.yolo_runner import TARGET_CLASSES, manifest_entries


PROMPT_VERSION = "gemini-detect-v1"
DEFAULT_MODEL = "gemini-3.8-flash"
API_VERSION = "v1beta"
ENDPOINT = "https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent"
HERE = Path(__file__).resolve().parent
# Fixed order gives each label a stable raw_class_id, like a detector's class index.
LABELS = ("laptop", "desktop_computer_tower", "monitor", "printer", "projector")
RETRY_STATUSES = {429, 500, 503}
Transport = Callable[[dict[str, Any], str, float], dict[str, Any]]

assert set(LABELS) == TARGET_CLASSES

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "label": {"type": "STRING", "enum": list(LABELS)},
            "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        },
        "required": ["label", "box_2d"],
    },
}


def gemini_transport(payload: dict[str, Any], model: str, timeout: float) -> dict[str, Any]:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    request = Request(
        ENDPOINT.format(version=API_VERSION, model=model),
        data=json.dumps(payload).encode("utf-8"),
        # Header, not query string, so the key never appears in URLs or error text.
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    # shortcut: fixed 3 retries with backoff on rate limit/overload; add a client-side rate limiter if runs still fail.
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in RETRY_STATUSES and attempt < 3:
                time.sleep(2 ** (attempt + 2))
                continue
            raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Gemini connection failed: {exc.reason}") from exc
    raise AssertionError("unreachable")


def read_image(path: Path) -> tuple[bytes, str, tuple[int, int]]:
    """Return bytes, MIME type, and (height, width) exactly as stored on disk."""
    with Image.open(path) as image:
        # Gemini and annotators may disagree about EXIF rotation; refuse instead of guessing.
        if image.getexif().get(0x0112, 1) != 1:
            raise ValueError("image has EXIF rotation; save it upright without rotation metadata")
        mime = Image.MIME.get(image.format or "")
        width, height = image.size
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"unsupported image format: {mime}")
    return path.read_bytes(), mime, (height, width)


def build_payload(image_bytes: bytes, mime: str, prompt: str, thinking_level: str | None = None,
                  response_schema: dict[str, Any] = RESPONSE_SCHEMA) -> dict[str, Any]:
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
                {"text": prompt},
            ],
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }
    if thinking_level:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level}
    return payload


def response_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"no candidates (promptFeedback={response.get('promptFeedback')})")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text:
        raise ValueError(f"empty response (finishReason={candidates[0].get('finishReason')})")
    return text


def normalize_response(raw: Any, image_size: tuple[int, int]) -> list[dict[str, Any]]:
    """Validate Gemini's [ymin, xmin, ymax, xmax] 0-1000 boxes and convert to xyxy pixels."""
    if not isinstance(raw, list):
        raise ValueError("response must be a JSON list")
    height, width = image_size
    detections = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) != {"label", "box_2d"}:
            raise ValueError(f"detection {index} must contain only label and box_2d")
        label, box = item["label"], item["box_2d"]
        if label not in LABELS:
            raise ValueError(f"detection {index} has invalid label {label!r}")
        if not isinstance(box, list) or len(box) != 4 or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in box
        ):
            raise ValueError(f"detection {index} box_2d must be four numbers")
        ymin, xmin, ymax, xmax = box
        if not (0 <= xmin < xmax <= 1000 and 0 <= ymin < ymax <= 1000):
            raise ValueError(f"detection {index} box is outside 0-1000 or has no area")
        detections.append({
            "raw_class_id": LABELS.index(label),
            "raw_class_name": label,
            "confidence": None,
            "box_xyxy_pixels": [
                xmin / 1000 * width, ymin / 1000 * height, xmax / 1000 * width, ymax / 1000 * height,
            ],
            "project_class": label,
            "mapping_status": "mapped",
        })
    return detections


def run_manifest(
    manifest: Path,
    output: Path,
    model: str,
    command: str,
    timeout: float = 120.0,
    transport: Transport = gemini_transport,
    thinking_level: str | None = None,
) -> None:
    manifest, output = manifest.resolve(), output.resolve()
    if manifest == output:
        raise ValueError("manifest and output paths must differ")
    rows = manifest_entries(manifest)
    prompt = (HERE / "prompt-gemini-v1.txt").read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as destination:
            temporary_path = Path(destination.name)
            for row in rows:
                started = time.perf_counter()
                raw: Any = None
                response: dict[str, Any] = {}
                detections: list[dict[str, Any]] = []
                image_size = None
                error = None
                try:
                    image_bytes, mime, size = read_image(manifest.parent / row["path"])
                    image_size = list(size)
                    response = transport(build_payload(image_bytes, mime, prompt, thinking_level), model, timeout)
                    raw = response_text(response)
                    detections = normalize_response(json.loads(raw), size)
                    logging.info("Detection completed image_id=%s detections=%d", row["image_id"], len(detections))
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    logging.exception("Detection failed for image_id=%s", row["image_id"])

                record = {
                    "schema_version": "1.0.0",
                    "image_id": row["image_id"],
                    "task": "object_detection",
                    "model_identifier": (
                        f"Gemini {model} via generateContent ({PROMPT_VERSION}, "
                        f"thinking={thinking_level or 'model default'})"
                    ),
                    "weights_filename": model,
                    "weights_sha256": None,
                    "runtime": "gemini-api",
                    "runtime_version": API_VERSION,
                    "model_version": response.get("modelVersion"),
                    "prompt_version": PROMPT_VERSION,
                    "usage": response.get("usageMetadata"),
                    "device": "remote",
                    "hardware": {"system": platform.system(), "machine": platform.machine()},
                    "command": command,
                    "thresholds": {"confidence": None, "iou": None},
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "image_size_hw_pixels": image_size,
                    "box_format": "xyxy pixels: [left, top, right, bottom] in the original image",
                    "raw_predictions": raw,
                    "detections": detections,
                    "error": error,
                }
                destination.write(json.dumps(record, separators=(",", ":")) + "\n")
        os.replace(temporary_path, output)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="CSV containing image_id and path")
    parser.add_argument("output", type=Path, help="detection JSONL output")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="pinned Gemini model ID")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--thinking-level", choices=("minimal", "low", "medium", "high"),
                        help="omit for the model default; allowed levels vary by model")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        parser.error("GEMINI_API_KEY must be set in the environment")

    log_path = args.log or args.output.with_suffix(args.output.suffix + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    command = shlex.join([sys.executable, *sys.argv])
    logging.info("Starting command: %s", command)
    run_manifest(args.manifest, args.output, args.model, command, args.timeout,
                 thinking_level=args.thinking_level)


if __name__ == "__main__":
    main()
