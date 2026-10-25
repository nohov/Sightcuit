#!/usr/bin/env python3
"""Voice-guided circuit tutor: frames stream to the laptop for free; one frame goes to a cloud model per question."""

from __future__ import annotations

import argparse
import base64
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import platform
import re
import secrets
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np

from recognition.gemini_runner import RETRY_STATUSES, Transport, build_payload, gemini_transport, response_text
from recognition.live_runner import MAX_RELAY_FRAME_BYTES, camera_frames
from recognition.resistor import COLORS, readings, spoken_ohms
from recognition.runio import start_logging


PROMPT_VERSION = "tutor-v1"
HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "tutor_config.json"
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
MAX_ASK_BYTES = 4096
UNREADABLE = ("I can't tell reliably from this view. Hold it closer under good light and keep it still, "
              "or check it with the multimeter.")

GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "resistor_bands": {"type": "ARRAY", "items": {"type": "STRING", "enum": list(COLORS)}, "nullable": True},
        "step_done": {"type": "BOOLEAN", "nullable": True},
        "uncertain": {"type": "BOOLEAN"},
    },
    "required": ["answer", "resistor_bands", "step_done", "uncertain"],
}
OPENAI_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "resistor_bands": {"type": ["array", "null"], "items": {"type": "string", "enum": list(COLORS)}},
        "step_done": {"type": ["boolean", "null"]},
        "uncertain": {"type": "boolean"},
    },
    "required": ["answer", "resistor_bands", "step_done", "uncertain"],
    "additionalProperties": False,
}


def openai_transport(payload: dict[str, Any], model: str, timeout: float) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    request = Request(
        OPENAI_ENDPOINT,
        data=json.dumps({**payload, "model": model}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in RETRY_STATUSES and attempt < 3:
                time.sleep(2 ** (attempt + 2))
                continue
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenAI connection failed: {exc.reason}") from exc
    raise AssertionError("unreachable")


def openai_payload(jpeg: bytes, prompt: str) -> dict[str, Any]:
    image = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    return {
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image}},
        ]}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "tutor_reply", "strict": True, "schema": OPENAI_SCHEMA}},
    }


def openai_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("no choices in OpenAI response")
    text = choices[0].get("message", {}).get("content")
    if not text:
        raise ValueError(f"empty response (finish_reason={choices[0].get('finish_reason')})")
    return text


# provider -> (build payload, extract text, usage key, model version key)
PROVIDERS: dict[str, tuple[Callable[[bytes, str], dict[str, Any]], Callable[[dict[str, Any]], str], str, str]] = {
    "gemini": (lambda jpeg, prompt: build_payload(jpeg, "image/jpeg", prompt, response_schema=GEMINI_SCHEMA),
               response_text, "usageMetadata", "modelVersion"),
    "openai": (openai_payload, openai_text, "usage", "model"),
}
DEFAULT_TRANSPORTS: dict[str, Transport] = {"gemini": gemini_transport, "openai": openai_transport}


def parse_reply(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {"answer", "resistor_bands", "step_done", "uncertain"}:
        raise ValueError("reply must contain exactly answer, resistor_bands, step_done, uncertain")
    if not isinstance(raw["answer"], str) or not isinstance(raw["uncertain"], bool):
        raise ValueError("answer must be a string and uncertain a boolean")
    bands = raw["resistor_bands"]
    if bands is not None and not (isinstance(bands, list) and all(band in COLORS for band in bands)):
        raise ValueError(f"invalid resistor_bands {bands!r}")
    if raw["step_done"] is not None and not isinstance(raw["step_done"], bool):
        raise ValueError("step_done must be a boolean or null")
    return raw


def load_project(path: Path) -> dict[str, Any]:
    project = json.loads(path.read_text(encoding="utf-8"))
    if not project.get("steps") or not all({"say", "check"} <= set(step) for step in project["steps"]):
        raise ValueError(f"{path}: project needs steps with say and check")
    return project


def load_tiers(path: Path) -> list[dict[str, str]]:
    tiers = json.loads(path.read_text(encoding="utf-8"))["tiers"]
    for tier in tiers:
        if tier.get("provider") not in PROVIDERS or not tier.get("model"):
            raise ValueError(f"{path}: bad tier {tier!r}")
    return tiers


# Spoken commands that move through the steps without a model call.
COMMANDS = [
    ("next", re.compile(r"\b(next|skip)\b")),
    ("back", re.compile(r"\b(back|previous)\b")),
    ("repeat", re.compile(r"\b(repeat|again|what('s| is) the step|start)\b")),
    ("check", re.compile(r"\b(done|finished|check)\b")),
]


class Tutor:
    def __init__(self, project: dict[str, Any], tiers: list[dict[str, str]], prompt: str,
                 transports: dict[str, Transport] = DEFAULT_TRANSPORTS, timeout: float = 60.0) -> None:
        self.project, self.tiers, self.prompt, self.transports, self.timeout = project, tiers, prompt, transports, timeout
        self.step = 0
        self.resistors = [part for part in project.get("bom", []) if part.get("part") == "resistor"]

    def current(self) -> str:
        steps = self.project["steps"]
        return f"Step {self.step + 1} of {len(steps)}. {steps[self.step]['say']}"

    def advance(self, delta: int) -> str:
        last = len(self.project["steps"]) - 1
        if delta > 0 and self.step == last:
            return "That was the last step. The circuit is finished."
        self.step = min(max(self.step + delta, 0), last)
        return self.current()

    def handle(self, text: str, jpeg: bytes | None) -> tuple[str, dict[str, Any]]:
        """Return what to say and the record fields for one spoken request."""
        command = next((name for name, pattern in COMMANDS if pattern.search(text.lower())), None)
        if command == "next":
            return self.advance(1), {"command": command, "attempts": []}
        if command == "back":
            return self.advance(-1), {"command": command, "attempts": []}
        if command == "repeat":
            return self.current(), {"command": command, "attempts": []}
        if jpeg is None:
            return "I don't have a camera frame yet.", {"command": command, "attempts": []}
        say, attempts = self.consult(text, jpeg, checking=command == "check")
        return say, {"command": command, "attempts": attempts}

    def consult(self, question: str, jpeg: bytes, checking: bool) -> tuple[str, list[dict[str, Any]]]:
        step = self.project["steps"][self.step]
        prompt = (self.prompt.replace("{project}", json.dumps(self.project))
                  .replace("{step_number}", str(self.step + 1))
                  .replace("{step_count}", str(len(self.project["steps"])))
                  .replace("{step_say}", step["say"]).replace("{step_check}", step["check"])
                  .replace("{question}", question))
        attempts: list[dict[str, Any]] = []
        for index, tier in enumerate(self.tiers):
            last = index == len(self.tiers) - 1
            build, text_of, usage_key, version_key = PROVIDERS[tier["provider"]]
            attempt: dict[str, Any] = {"tier": index + 1, **tier, "confidence": None}
            attempts.append(attempt)
            started = time.perf_counter()
            try:
                response = self.transports[tier["provider"]](build(jpeg, prompt), tier["model"], self.timeout)
                attempt.update(usage=response.get(usage_key), model_version=response.get(version_key))
                attempt["raw_response"] = text_of(response)
                reply = attempt["reply"] = parse_reply(json.loads(attempt["raw_response"]))
            except Exception as exc:
                attempt["error"] = f"{type(exc).__name__}: {exc}"
                logging.exception("Tutor tier %d failed", index + 1)
                continue
            finally:
                attempt["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
            say, final = self.judge(reply, checking, attempt)
            if final or last:
                return say, attempts
        return "I can't reach the model right now. Try again in a moment.", attempts

    def judge(self, reply: dict[str, Any], checking: bool, attempt: dict[str, Any]) -> tuple[str, bool]:
        """Return (what to say, whether this answer is good enough to stop escalating)."""
        if reply["uncertain"]:
            return UNREADABLE, False
        if reply["resistor_bands"]:
            found = attempt["readings"] = readings(reply["resistor_bands"])
            if not found:
                return UNREADABLE, False
            for reading in found:
                for part in self.resistors:
                    if reading["ohms"] == part["value_ohms"]:
                        attempt["bom_match"] = part["ref"]
                        return (f"That's {spoken_ohms(reading['ohms'])}, plus or minus "
                                f"{reading['tolerance_pct']:g} percent. It's {part['ref']} in this project."), True
            needed = ", ".join(f"{spoken_ohms(p['value_ohms'])} for {p['ref']}" for p in self.resistors)
            reading = found[0]
            return (f"That reads as {spoken_ohms(reading['ohms'])}, plus or minus {reading['tolerance_pct']:g} percent, "
                    f"which is not in this project." + (f" You need {needed}." if needed else "")), False
        if checking:
            if reply["step_done"] is True:
                return "Looks good. " + self.advance(1), True
            if reply["step_done"] is False:
                return reply["answer"], True
            return "I can't confirm that step from here. " + UNREADABLE, False
        return reply["answer"], True


def make_tutor_server(address: tuple[str, int], token: str, tutor: Tutor, state: dict[str, Any],
                      write: Callable[[dict[str, Any]], None], record_base: dict[str, Any]) -> ThreadingHTTPServer:
    """POST /frame with a JPEG keeps the newest frame; POST /ask {"text"} answers one spoken request.

    shortcut: plain HTTP on the LAN behind a bearer token, like the detection relay; add TLS before shared networks.
    """
    expected = f"Bearer {token}".encode()
    lock = threading.Lock()  # one question at a time keeps step state and spend predictable

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            if self.path not in ("/frame", "/ask"):
                return self.reply(404, {"error": "not found"})
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return self.reply(401, {"error": "bad token"})
            length = int(self.headers.get("Content-Length") or 0)
            limit = MAX_RELAY_FRAME_BYTES if self.path == "/frame" else MAX_ASK_BYTES
            if not 0 < length <= limit:
                return self.reply(400, {"error": "body missing or too large"})
            body = self.rfile.read(length)
            if self.path == "/frame":
                frame = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    return self.reply(400, {"error": "body is not a decodable image"})
                state["jpeg"], state["image_size"] = body, list(frame.shape[:2])
                # Same shape as the detection relay's reply, so the existing iOS client decodes it unchanged.
                return self.reply(200, {"tracks": [], "image_size_hw_pixels": state["image_size"]})
            try:
                text = json.loads(body)["text"]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                return self.reply(400, {"error": 'body must be JSON {"text": "..."}'})
            with lock:
                started = time.perf_counter()
                step_before = tutor.step
                say, fields = tutor.handle(text, state["jpeg"])
                write({**record_base, "timestamp": time.time(), "question": text, "image_size_hw_pixels":
                       state["image_size"] if fields["attempts"] else None, "step_before": step_before,
                       "step_after": tutor.step, **fields, "say": say,
                       "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)})
                self.reply(200, {"say": say, "step_index": tutor.step, "step_count": len(tutor.project["steps"]),
                                 "project": tutor.project.get("title")})

        def log_message(self, format: str, *args: Any) -> None:
            logging.info("tutor %s " + format, self.address_string(), *args)

    return ThreadingHTTPServer(address, Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="per-question JSONL output (appended)")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--allow-upload", action="store_true",
                        help="confirm the frame current at each question may be uploaded to the configured providers")
    parser.add_argument("--listen", default="0.0.0.0:8765", metavar="HOST:PORT")
    parser.add_argument("--camera", type=int, help="take frames from a local camera instead of the glasses relay")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not args.allow_upload:
        parser.error("--allow-upload is required: the newest frame is sent to a cloud model for each question")
    tiers = load_tiers(args.config)
    for provider in {tier["provider"] for tier in tiers}:
        if not os.environ.get(f"{provider.upper()}_API_KEY"):
            parser.error(f"{provider.upper()}_API_KEY must be set in the environment")

    project = load_project(args.project)
    tutor = Tutor(project, tiers, (HERE / "prompt-tutor-v1.txt").read_text(encoding="utf-8"), timeout=args.timeout)
    command = start_logging(args.output, args.log)
    state: dict[str, Any] = {"jpeg": None, "image_size": None}
    record_base = {
        "schema_version": "1.0.0", "task": "circuit_tutor", "project_id": project.get("id"),
        "prompt_version": PROMPT_VERSION, "command": command,
        "hardware": {"system": platform.system(), "machine": platform.machine()},
    }
    if args.camera is not None:
        def read_camera() -> None:
            for frame in camera_frames(args.camera):
                encoded, jpeg = cv2.imencode(".jpg", frame)
                if encoded:
                    state["jpeg"], state["image_size"] = jpeg.tobytes(), list(frame.shape[:2])
        threading.Thread(target=read_camera, name="tutor-camera", daemon=True).start()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as destination:
        def write(record: dict[str, Any]) -> None:
            destination.write(json.dumps(record, separators=(",", ":")) + "\n")
            destination.flush()

        host, _, port = args.listen.rpartition(":")
        token = secrets.token_hex(16)
        server = make_tutor_server((host, int(port)), token, tutor, state, write, record_base)
        # Token goes to the terminal only, never the log file.
        print(f"tutor listening on {host}:{server.server_address[1]}; token {token}", flush=True)
        print(tutor.current(), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
