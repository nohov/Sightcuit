#!/usr/bin/env python3
"""Voice-guided circuit tutor: frames stream to the laptop for free; one frame goes to a cloud model per question."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import platform
import re
import secrets
import string
import sys
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import cv2
import numpy as np

from recognition.gemini_runner import RETRY_STATUSES, Transport, build_payload, gemini_transport, response_text
from recognition.live_runner import (EVENTS_KEEPALIVE_SECONDS, MAX_RELAY_FRAME_BYTES, STREAM_POLL_SECONDS,
                                     camera_frames)
from recognition.narrator import (
    DEFAULT_STT_MODEL, DEFAULT_TTS_MODEL, DEFAULT_VOICE, _write, elevenlabs_speak, elevenlabs_transcribe,
)
from recognition.resistor import COLORS, readings, spoken_ohms
from recognition.runio import start_logging


PROMPT_VERSION = "tutor-v7"
HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "tutor_config.json"
IDEAS_VERSION, PLAN_VERSION = "ideas-v2", "plan-v4"
IDEAS_PROMPT = (HERE / f"prompt-{IDEAS_VERSION}.txt").read_text(encoding="utf-8")
PLAN_PROMPT = (HERE / f"prompt-{PLAN_VERSION}.txt").read_text(encoding="utf-8")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
MAX_ASK_BYTES = 4096
MAX_ASK_AUDIO_BYTES = 4 * 1024 * 1024  # the phone caps a recording at 30 s of 48 kHz 16-bit mono, about 2.9 MB
WAKE_WORD = "tutor"  # same as Voice.wakeWord on the phone
# With no --project the tutor starts free: identify parts, ask for ideas, or request a build.
NO_PROJECT = {"id": None, "title": None, "steps": [], "bom": []}
NO_BUILD = "No build chosen yet. Show me a part and ask what is this, or tell me what you want to make."
UNREADABLE = ("I can't tell reliably from this view. Hold it closer under good light and keep it still, "
              "or check it with the multimeter.")

GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "step_done": {"type": "BOOLEAN", "nullable": True},
        "component": {"type": "STRING", "nullable": True},
        "uncertain": {"type": "BOOLEAN"},
    },
    "required": ["answer", "step_done", "component", "uncertain"],
}
OPENAI_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "step_done": {"type": ["boolean", "null"]},
        "component": {"type": ["string", "null"]},
        "uncertain": {"type": "boolean"},
    },
    "required": ["answer", "step_done", "component", "uncertain"],
    "additionalProperties": False,
}
GEMINI_PLAN_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "title": {"type": "STRING"},
        "parts": {"type": "ARRAY", "items": {"type": "STRING"}},
        "missing": {"type": "ARRAY", "items": {"type": "STRING"}},
        "code": {"type": "STRING"},
        "steps": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"say": {"type": "STRING"}, "check": {"type": "STRING"}},
            "required": ["say", "check"],
        }},
        "uncertain": {"type": "BOOLEAN"},
    },
    "required": ["answer", "title", "parts", "missing", "code", "steps", "uncertain"],
}
OPENAI_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "title": {"type": "string"},
        "parts": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"}},
        "code": {"type": "string"},
        "steps": {"type": "array", "items": {
            "type": "object",
            "properties": {"say": {"type": "string"}, "check": {"type": "string"}},
            "required": ["say", "check"],
            "additionalProperties": False,
        }},
        "uncertain": {"type": "boolean"},
    },
    "required": ["answer", "title", "parts", "missing", "code", "steps", "uncertain"],
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


def openai_payload(jpeg: bytes, prompt: str, schema: dict[str, Any] = OPENAI_SCHEMA) -> dict[str, Any]:
    image = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    return {
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image}},
        ]}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "tutor_reply", "strict": True, "schema": schema}},
    }


def openai_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("no choices in OpenAI response")
    text = choices[0].get("message", {}).get("content")
    if not text:
        raise ValueError(f"empty response (finish_reason={choices[0].get('finish_reason')})")
    return text


# provider -> (build payload for a plan or not, extract text, usage key, model version key)
PROVIDERS: dict[str, tuple[Callable[[bytes, str, bool], dict[str, Any]], Callable[[dict[str, Any]], str], str, str]] = {
    "gemini": (lambda jpeg, prompt, plan: build_payload(
                   jpeg, "image/jpeg", prompt, response_schema=GEMINI_PLAN_SCHEMA if plan else GEMINI_SCHEMA),
               response_text, "usageMetadata", "modelVersion"),
    "openai": (lambda jpeg, prompt, plan: openai_payload(jpeg, prompt, OPENAI_PLAN_SCHEMA if plan else OPENAI_SCHEMA),
               openai_text, "usage", "model"),
}
# No Gemini retries: the next tier is the fallback, and backoff on an exhausted quota outlasts the phone's wait.
DEFAULT_TRANSPORTS: dict[str, Transport] = {"gemini": lambda payload, model, timeout: gemini_transport(
    payload, model, timeout, retries=0), "openai": openai_transport}


def parse_reply(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {"answer", "step_done", "component", "uncertain"}:
        raise ValueError("reply must contain exactly answer, step_done, component, uncertain")
    if not isinstance(raw["answer"], str) or not isinstance(raw["uncertain"], bool):
        raise ValueError("answer must be a string and uncertain a boolean")
    if raw["step_done"] is not None and not isinstance(raw["step_done"], bool):
        raise ValueError("step_done must be a boolean or null")
    if raw["component"] is not None and not isinstance(raw["component"], str):
        raise ValueError("component must be a string or null")
    return raw


def parse_plan(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {"answer", "title", "parts", "missing", "code", "steps", "uncertain"}:
        raise ValueError("plan must contain exactly answer, title, parts, missing, code, steps, uncertain")
    if not all(isinstance(raw[key], str) for key in ("answer", "title", "code")) or not isinstance(raw["uncertain"], bool):
        raise ValueError("answer, title and code must be strings and uncertain a boolean")
    for key in ("parts", "missing"):
        if not isinstance(raw[key], list) or not all(isinstance(part, str) for part in raw[key]):
            raise ValueError(f"{key} must be a list of strings")
    if not isinstance(raw["steps"], list) or not all(
            isinstance(step, dict) and set(step) == {"say", "check"} and all(isinstance(v, str) for v in step.values())
            for step in raw["steps"]):
        raise ValueError("steps must be a list of {say, check} strings")
    if not raw["uncertain"] and not (raw["parts"] and raw["steps"]):
        raise ValueError("a certain plan needs parts and steps")
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
# Session requests, matched before COMMANDS so "build a back-up alarm" is not "back".
RESET = re.compile(r"\b(new session|start over)\b")
# Answers while a plan waits for confirmation.
CONFIRM = re.compile(r"\b(yes|yeah|yep|sure|okay|ok|start it|let's do it|let's go)\b")
DECLINE = re.compile(r"\b(no|nope|cancel|never mind|nevermind|back out|go back|not that)\b")
IDEAS = re.compile(r"\bwhat (can|could|should) i (make|build)\b")
PLAN = re.compile(r"\b(i want to|i'd like to|how (do|can|would) i|(can|could) i|help me|let's) (make|build)\b")
# Picking one of the ideas just offered ("let's do the button LED") asks for its plan.
PICK = re.compile(r"\b(do|try|make|build|go with|pick|choose|want)\b")
RESISTOR_QUESTION = re.compile(r"\b(resistors?|resistance|ohms?)\b")
# Speech recognition writes either spelling.
COLOR_WORDS = {**{color: color for color in COLORS}, "gray": "grey", "purple": "violet"}
ASK_BANDS = ("Tell me its band colors, starting from the end farthest from the gold or silver band. "
             "For example: red, red, brown, gold.")


def part_key(name: str) -> str:
    """Compare part names loosely: "220 Ohms resistor" matches "220 ohm resistor"."""
    # shortcut: exact words after case and plural folding; "Arduino Uno" won't match "Arduino Uno R3".
    return " ".join(re.sub(r"s$", "", word) for word in re.findall(r"[a-z0-9]+", name.lower()))


class Tutor:
    def __init__(self, project: dict[str, Any] | None, tiers: list[dict[str, str]], prompt: str,
                 transports: dict[str, Transport] = DEFAULT_TRANSPORTS, timeout: float = 60.0,
                 sketch_dir: Path | None = None) -> None:
        self.project, self.tiers, self.prompt, self.transports, self.timeout = project, tiers, prompt, transports, timeout
        self.sketch_dir = sketch_dir  # where a confirmed plan's Arduino sketch is saved
        self.original = project or NO_PROJECT
        self.reset()

    def reset(self) -> None:
        """Start a new session: the original project, step 1, no parts seen."""
        # shortcut: the session lives in memory and ends with the process; persist it if sessions must survive restarts.
        self.project, self.step, self.components = self.original, 0, []
        self.finished = False  # the last step was confirmed or skipped past
        self.pending: dict[str, Any] | None = None  # a plan that waits for the user's yes or no
        self.offered = False  # the last reply offered ideas, so the next request may pick one
        self.resistors = [part for part in self.project.get("bom", []) if part.get("part") == "resistor"]

    def remember(self, component: str) -> None:
        if component.strip().lower() not in (seen.lower() for seen in self.components):
            self.components.append(component.strip())

    def current(self) -> str:
        steps = self.project["steps"]
        if not steps:
            return NO_BUILD
        return f"Step {self.step + 1} of {len(steps)}. {steps[self.step]['say']}"

    def advance(self, delta: int) -> str:
        last = len(self.project["steps"]) - 1
        if last < 0:
            return NO_BUILD
        if delta > 0 and self.step == last:
            self.finished = True
            return "That was the last step. The circuit is finished."
        self.step, self.finished = min(max(self.step + delta, 0), last), False
        return self.current()

    def handle(self, text: str, jpeg: bytes | None) -> tuple[str, dict[str, Any]]:
        """Return what to say and the record fields for one spoken request."""
        lowered = text.lower()
        offered, self.offered = self.offered, False
        if RESET.search(lowered):
            self.reset()
            return "New session. " + self.current(), {"command": "reset", "attempts": []}
        if self.pending and DECLINE.search(lowered):
            title, self.pending = self.pending["title"], None
            keep = f"Back to {self.project['title']}. " if self.project["title"] else ""
            return f"Okay, not building {title}. {keep}{self.current()}", {"command": "decline", "attempts": []}
        if self.pending and CONFIRM.search(lowered):
            plan, self.pending = self.pending, None
            self.project = {"id": "generated", "title": plan["title"], "steps": plan["steps"], "bom": [],
                            "parts": plan["parts"], "missing": plan["missing"], "code": plan["code"]}
            self.step, self.resistors, self.finished = 0, [], False
            return (f"Starting {plan['title']}. {self.save_sketch(plan)}{self.current()}",
                    {"command": "confirm", "attempts": []})
        session = next((name for name, pattern in (("ideas", IDEAS), ("plan", PLAN)) if pattern.search(lowered)), None)
        if session is None and offered and PICK.search(lowered):
            session = "plan"
        if session == "ideas" and not self.components:
            return "Show me some parts first and ask what is this.", {"command": session, "attempts": []}
        if session and jpeg is None:
            return "I don't have a camera frame yet.", {"command": session, "attempts": []}
        if session:
            prompt = ((IDEAS_PROMPT if session == "ideas" else PLAN_PROMPT)
                      .replace("{components}", ", ".join(self.components) or "none yet").replace("{question}", text))
            judge = self.adopt_plan if session == "plan" else lambda reply, attempt: (
                (UNREADABLE, False) if reply["uncertain"] else (reply["answer"], True))
            say, attempts = self.consult(prompt, jpeg, session == "plan", judge)
            self.offered = session == "ideas"
            return say, {"command": session, "attempts": attempts}
        command = next((name for name, pattern in COMMANDS if pattern.search(lowered)), None)
        if command == "next":
            return self.advance(1), {"command": command, "attempts": []}
        if command == "back":
            return self.advance(-1), {"command": command, "attempts": []}
        if command == "repeat":
            return self.current(), {"command": command, "attempts": []}
        # The camera is too blurry for bands, so the user reads them and code, not a model, decodes them.
        # shortcut: needs the colors heard as words ("read" for "red" is missed); add homophones if logs show misses.
        bands = [COLOR_WORDS[word] for word in re.findall(r"[a-z]+", text.lower()) if word in COLOR_WORDS]
        if len(bands) >= 3:
            return self.resistor_value(bands), {"command": "bands", "bands": bands, "attempts": []}
        checking = command == "check"
        if checking and not self.project["steps"]:
            return NO_BUILD, {"command": command, "attempts": []}
        if not checking and RESISTOR_QUESTION.search(text.lower()):
            return ASK_BANDS, {"command": "ask_bands", "attempts": []}
        if jpeg is None:
            return "I don't have a camera frame yet.", {"command": command, "attempts": []}
        say, attempts = self.consult(self.step_prompt(text), jpeg, False,
                                     lambda reply, attempt: self.judge(reply, checking, attempt))
        answered = [attempt["reply"] for attempt in attempts if "reply" in attempt]
        if not checking and answered and answered[-1]["component"] and not answered[-1]["uncertain"]:
            self.remember(answered[-1]["component"])
        return say, {"command": command, "attempts": attempts}

    def dashboard(self) -> dict[str, Any]:
        """What the dashboard shows: the build's steps, how far along, the parts named so far, and the plan's
        parts list, current step check and sketch. A --project file has no parts list or sketch."""
        steps = self.project["steps"]
        found = {part_key(part) for part in self.components}
        # The model's missing list is from planning time; a part named since then counts as had.
        missing = {part_key(part) for part in self.project.get("missing", [])} - found
        return {"project": self.project["title"], "steps": [step["say"] for step in steps],
                "step_index": self.step, "finished": self.finished, "parts": list(self.components),
                "check": steps[self.step]["check"] if steps else None,
                "needed": [{"part": part, "have": part_key(part) not in missing}
                           for part in self.project.get("parts", [])],
                "code": self.project.get("code", "")}

    def resistor_value(self, bands: list[str]) -> str:
        """Speak the value of bands the user read aloud, trying both reading directions."""
        heard = ", ".join(bands)
        found = readings(bands)
        if not found:
            return f"I heard {heard}. Those colors are wrong; no beginner resistor reads that way. " + ASK_BANDS
        for reading in found:
            for part in self.resistors:
                if reading["ohms"] == part["value_ohms"]:
                    self.remember(f"{spoken_ohms(reading['ohms'])} resistor")
                    return (f"{heard}. That's {spoken_ohms(reading['ohms'])}, plus or minus "
                            f"{reading['tolerance_pct']:g} percent. It's {part['ref']} in this project.")
        self.remember(f"{spoken_ohms(found[0]['ohms'])} resistor")
        needed = ", ".join(f"{spoken_ohms(p['value_ohms'])} for {p['ref']}" for p in self.resistors)
        say = f"{heard}. That's {spoken_ohms(found[0]['ohms'])}, plus or minus {found[0]['tolerance_pct']:g} percent"
        if len(found) > 1:
            say += f", or {spoken_ohms(found[1]['ohms'])} read from the other end"
        # A generated plan has no resistor BOM to compare against.
        return say + "." + (f" That's not in this project. You need {needed}." if needed else "")

    def step_prompt(self, question: str) -> str:
        steps = self.project["steps"]
        step = steps[self.step] if steps else {"say": "none, no build chosen yet", "check": "none"}
        return (self.prompt.replace("{project}", json.dumps(self.project))
                .replace("{step_number}", str(self.step + 1))
                .replace("{step_count}", str(len(self.project["steps"])))
                .replace("{step_say}", step["say"]).replace("{step_check}", step["check"])
                .replace("{components}", ", ".join(self.components) or "none yet")
                .replace("{question}", question))

    def save_sketch(self, plan: dict[str, Any]) -> str:
        """Save a plan's Arduino code as name/name.ino, the folder layout the Arduino IDE requires; never run it."""
        if not plan["code"].strip() or self.sketch_dir is None:
            return ""
        name = re.sub(r"[^a-z0-9]+", "_", plan["title"].lower()).strip("_") or "sketch"
        path = self.sketch_dir / name / f"{name}.ino"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan["code"], encoding="utf-8")
        return f"I saved its Arduino sketch on the laptop as {name}.ino in {self.sketch_dir.name}. "

    def adopt_plan(self, plan: dict[str, Any], attempt: dict[str, Any]) -> tuple[str, bool]:
        """Hold a model-generated build until the user says yes; the current build is untouched until then."""
        if plan["uncertain"]:
            return "I can't plan that as a safe beginner circuit. Try describing something simpler.", False
        self.pending = plan
        missing = (f"You still need {', '.join(plan['missing'])}." if plan["missing"]
                   else "You have everything it needs.")
        keep = f"keep building {self.project['title']}" if self.project["title"] else "back out"
        return (f"{plan['answer']} It uses {', '.join(plan['parts'])}. {missing} "
                f"Say yes to start it, or no to {keep}."), True

    def consult(self, prompt: str, jpeg: bytes, plan: bool,
                judge: Callable[[dict[str, Any], dict[str, Any]], tuple[str, bool]]) -> tuple[str, list[dict[str, Any]]]:
        attempts: list[dict[str, Any]] = []
        for index, tier in enumerate(self.tiers):
            last = index == len(self.tiers) - 1
            build, text_of, usage_key, version_key = PROVIDERS[tier["provider"]]
            attempt: dict[str, Any] = {"tier": index + 1, **tier, "confidence": None}
            attempts.append(attempt)
            started = time.perf_counter()
            try:
                response = self.transports[tier["provider"]](build(jpeg, prompt, plan), tier["model"], self.timeout)
                attempt.update(usage=response.get(usage_key), model_version=response.get(version_key))
                attempt["raw_response"] = text_of(response)
                reply = attempt["reply"] = (parse_plan if plan else parse_reply)(json.loads(attempt["raw_response"]))
            except Exception as exc:
                attempt["error"] = f"{type(exc).__name__}: {exc}"
                logging.exception("Tutor tier %d failed", index + 1)
                continue
            finally:
                attempt["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
            say, final = judge(reply, attempt)
            if final or last:
                return say, attempts
        return "I can't reach the model right now. Try again in a moment.", attempts

    def judge(self, reply: dict[str, Any], checking: bool, attempt: dict[str, Any]) -> tuple[str, bool]:
        """Return (what to say, whether this answer is good enough to stop escalating)."""
        if reply["uncertain"]:
            return UNREADABLE, False
        if checking:
            if reply["step_done"] is True:
                return "Looks good. " + self.advance(1), True
            if reply["step_done"] is False:
                return reply["answer"], True
            return "I can't confirm that step from here. " + UNREADABLE, False
        return reply["answer"], True


def cached_speak(text: str, directory: Path, speak: Callable[[str], bytes]) -> bytes:
    """Voice each distinct reply once; step instructions and fixed prompts repeat across sessions."""
    path = directory / f"{hashlib.sha256(text.encode('utf-8')).hexdigest()}.wav"
    if path.exists():
        return path.read_bytes()
    audio = speak(text)
    _write(path, audio)
    return audio


def wake_question(transcript: str) -> str:
    """The words after the wake word, like the phone; the whole transcript when the wake word was misheard."""
    match = re.search(rf"\b{WAKE_WORD}\b", transcript, re.IGNORECASE)
    return (transcript[match.end():] if match else transcript).strip(string.punctuation + string.whitespace)


def make_tutor_server(address: tuple[str, int], token: str, tutor: Tutor, state: dict[str, Any],
                      write: Callable[[dict[str, Any]], None], record_base: dict[str, Any],
                      speak: Callable[[str], bytes] | None = None,
                      transcribe: Callable[[bytes], str] | None = None) -> ThreadingHTTPServer:
    """POST /frame with a JPEG keeps the newest frame; POST /ask {"text"} or a WAV answers one spoken request.

    With speak, the reply carries the spoken WAV; without it, or if speaking fails, the phone uses its own voice.
    A WAV ask is transcribed with transcribe; without it, or if that fails, a 503 asks the phone for its own text.
    The dashboard reads GET /stream.mjpg and /events?token= like the detection relay; events carry no tracks
    because the tutor runs no detector, and carry the steps and parts in "tutor", sent again whenever they change.

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
                self.stream(url.path == "/stream.mjpg")
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser closed the tab or reconnected

        def stream(self, video: bool) -> None:
            self.start_stream("multipart/x-mixed-replace; boundary=frame" if video else "text/event-stream")
            last, shown, index, last_write = None, None, 0, time.monotonic()
            while True:
                jpeg, lesson = state["jpeg"], tutor.dashboard()
                if (jpeg is not None and jpeg is not last) or (not video and lesson != shown):
                    last, shown, index = jpeg, lesson, index + 1
                    if video:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                         + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                    else:
                        payload = json.dumps({"frame_index": index, "timestamp": time.time(),
                                              "image_size_hw_pixels": state["image_size"], "tracks": [],
                                              "tutor": lesson})
                        self.wfile.write(f"data: {payload}\n\n".encode())
                elif not video and time.monotonic() - last_write >= EVENTS_KEEPALIVE_SECONDS:
                    self.wfile.write(b": keepalive\n\n")
                else:
                    time.sleep(STREAM_POLL_SECONDS)
                    continue
                self.wfile.flush()
                last_write = time.monotonic()

        def do_POST(self) -> None:
            if self.path not in ("/frame", "/ask"):
                return self.reply(404, {"error": "not found"})
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return self.reply(401, {"error": "bad token"})
            length = int(self.headers.get("Content-Length") or 0)
            spoken = self.path == "/ask" and self.headers.get("Content-Type", "").startswith("audio/")
            limit = MAX_RELAY_FRAME_BYTES if self.path == "/frame" else MAX_ASK_AUDIO_BYTES if spoken else MAX_ASK_BYTES
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
            if spoken:
                if transcribe is None:
                    return self.reply(503, {"error": "no ElevenLabs speech-to-text on the laptop"})
                try:
                    text = wake_question(transcribe(body))
                except Exception:
                    logging.exception("Transcription failed; the phone sends its own transcript")
                    text = ""
                if not text:
                    return self.reply(503, {"error": "transcription failed or heard no question"})
            else:
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
                write({**record_base, "timestamp": time.time(), "question": text,
                       "question_source": "elevenlabs" if spoken else "phone", "image_size_hw_pixels":
                       state["image_size"] if fields["attempts"] else None, "step_before": step_before,
                       "step_after": tutor.step, **fields, "components": list(tutor.components),
                       "project_id": tutor.project.get("id"), "project_title": tutor.project.get("title"),
                       "pending_plan": tutor.pending["title"] if tutor.pending else None, "say": say,
                       "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)})
                # The model whose reply produced `say`; null when none answered, so the phone never claims one did.
                answered = [attempt["model"] for attempt in fields["attempts"] if "reply" in attempt]
                audio = None
                if speak is not None:
                    try:
                        audio = base64.b64encode(speak(say)).decode()
                    except Exception:
                        logging.exception("Speech failed; the phone speaks instead")
                self.reply(200, {"say": say, "step_index": tutor.step, "step_count": len(tutor.project["steps"]),
                                 "project": tutor.project.get("title"), "model": answered[-1] if answered else None,
                                 "audio_wav_base64": audio})

        def log_message(self, format: str, *args: Any) -> None:
            logging.info("tutor %s " + format, self.address_string(), *args)

    return ThreadingHTTPServer(address, Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="per-question JSONL output (appended)")
    parser.add_argument("--project", type=Path, help="start on this build; without it no build is chosen")
    parser.add_argument("--allow-upload", action="store_true",
                        help="confirm the frame current at each question may be uploaded to the configured providers")
    parser.add_argument("--listen", default="0.0.0.0:8765", metavar="HOST:PORT")
    parser.add_argument("--camera", type=int, help="take frames from a local camera instead of the glasses relay")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--voice-id", default=DEFAULT_VOICE, help="ElevenLabs voice for spoken replies")
    parser.add_argument("--tts-model", default=DEFAULT_TTS_MODEL, help="ElevenLabs text-to-speech model")
    parser.add_argument("--stt-model", default=DEFAULT_STT_MODEL, help="ElevenLabs speech-to-text model")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not args.allow_upload:
        parser.error("--allow-upload is required: the newest frame is sent to a cloud model for each question")
    tiers = load_tiers(args.config)
    for provider in {tier["provider"] for tier in tiers}:
        if not os.environ.get(f"{provider.upper()}_API_KEY"):
            parser.error(f"{provider.upper()}_API_KEY must be set in the environment")
    # The relay's fixed token, so the phone stays connected across tutor restarts and switches from live_runner.
    token = os.environ.get("SCAVSCRAP_RELAY_TOKEN") or secrets.token_hex(16)
    if not re.fullmatch(r"[0-9a-f]{32,}", token):
        parser.error("SCAVSCRAP_RELAY_TOKEN must be at least 32 lowercase hex characters")

    project = load_project(args.project) if args.project else NO_PROJECT
    tutor = Tutor(project, tiers, (HERE / f"prompt-{PROMPT_VERSION}.txt").read_text(encoding="utf-8"),
                  timeout=args.timeout, sketch_dir=args.output.parent / "sketches")
    command = start_logging(args.output, args.log)
    state: dict[str, Any] = {"jpeg": None, "image_size": None}
    record_base = {
        "schema_version": "1.0.0", "task": "circuit_tutor",
        "prompt_version": PROMPT_VERSION,
        "ideas_prompt_version": IDEAS_VERSION, "plan_prompt_version": PLAN_VERSION, "command": command,
        "hardware": {"system": platform.system(), "machine": platform.machine()},
    }
    speak = transcribe = None
    if os.environ.get("ELEVENLABS_API_KEY"):
        # Reply text goes to text-to-speech; only utterances the phone heard the wake word in go to speech-to-text.
        voice_dir = HERE.parent / "cache" / "tts" / f"{args.voice_id}_{args.tts_model}"
        speak = lambda text: cached_speak(text, voice_dir, lambda t: elevenlabs_speak(t, args.voice_id, args.tts_model))
        transcribe = lambda wav: elevenlabs_transcribe(wav, args.stt_model, args.timeout)
        record_base["tts"] = f"elevenlabs:{args.voice_id}/{args.tts_model}"
        record_base["stt"] = f"elevenlabs:{args.stt_model}"
    else:
        record_base["tts"] = record_base["stt"] = None
        print("Voice: Apple on-device (set ELEVENLABS_API_KEY for ElevenLabs)", file=sys.stderr)
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
        server = make_tutor_server((host, int(port)), token, tutor, state, write, record_base, speak, transcribe)
        # Token goes to the terminal only, never the log file.
        print(f"tutor listening on {host}:{server.server_address[1]}; token {token}", flush=True)
        print(f"dashboard: open http://localhost:5173/?relay=http://localhost:{server.server_address[1]}"
              f"&token={token}", flush=True)
        print(tutor.current(), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
