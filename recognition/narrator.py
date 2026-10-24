"""Descriptions of identified products: Gemini writes a short text, optionally voiced by ElevenLabs; cached."""

from __future__ import annotations

from concurrent.futures import Executor, Future, ThreadPoolExecutor
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from recognition.gemini_runner import Transport, gemini_transport, response_text


HERE = Path(__file__).resolve().parent
PROMPT_VERSION = "describe-v1"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # premade voice used in ElevenLabs' API docs
DEFAULT_TTS_MODEL = "eleven_flash_v2_5"  # lowest latency and price per character
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=wav_22050"  # WAV plays without codecs
MAX_DESCRIPTION_CHARS = 600


def gemini_describe(label: str, model: str, timeout: float = 60.0, transport: Transport = gemini_transport) -> str:
    """Text-only Gemini call; only the label leaves the machine, no camera image."""
    prompt = (HERE / f"prompt-{PROMPT_VERSION}.txt").read_text(encoding="utf-8").replace("{label}", label)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "thinkingConfig": {"thinkingLevel": "minimal"}},
    }
    # shortcut: no web grounding, so facts come from the model; add the google_search tool if accuracy matters.
    text = " ".join(response_text(transport(payload, model, timeout)).split())
    if not 0 < len(text) <= MAX_DESCRIPTION_CHARS:
        raise ValueError(f"description must be 1-{MAX_DESCRIPTION_CHARS} characters, got {len(text)}")
    return text


def elevenlabs_speak(text: str, voice: str, model: str, timeout: float = 60.0) -> bytes:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    request = Request(
        TTS_URL.format(voice=voice),
        data=json.dumps({"text": text, "model_id": model}).encode("utf-8"),
        headers={"Content-Type": "application/json", "xi-api-key": key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            audio = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"ElevenLabs HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}") from None
    except URLError as exc:
        raise RuntimeError(f"ElevenLabs connection failed: {exc.reason}") from None
    if audio[:4] != b"RIFF":
        raise ValueError("ElevenLabs did not return WAV audio")
    return audio


def play_wav(path: Path) -> Any:
    """Start playback without blocking; returns a process to stop, or None where a new sound replaces the old."""
    if sys.platform == "darwin":
        return subprocess.Popen(["afplay", str(path)])
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return None
    return subprocess.Popen(["aplay", "-q", str(path)])  # shortcut: Linux needs alsa-utils


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:80] or "item"


class Narrator:
    """A description per label, written once in the background and kept on disk, so repeat items and runs cost
    nothing. With speak and audio_dir it is also voiced; texts are shared across voices.

    prepare() and click() are called only from the display thread; the worker only writes files.
    """

    def __init__(self, text_dir: Path, describe: Callable[[str], str], speak: Callable[[str], bytes] | None = None,
                 audio_dir: Path | None = None, play: Callable[[Path], Any] = play_wav,
                 executor: Executor | None = None) -> None:
        if (speak is None) != (audio_dir is None):
            raise ValueError("speak and audio_dir go together")
        self.text_dir, self.audio_dir = text_dir, audio_dir
        self.describe, self.speak, self.play = describe, speak, play
        self.pool = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="narrator")
        self.jobs: dict[str, Future] = {}
        self.playing: Any = None

    def text_path(self, label: str) -> Path:
        return self.text_dir / f"{slug(label)}.txt"

    def wav(self, label: str) -> Path:
        assert self.audio_dir is not None
        return self.audio_dir / f"{slug(label)}.wav"

    def ready(self, label: str) -> bool:
        return self.text_path(label).exists() and (self.speak is None or self.wav(label).exists())

    def description(self, label: str) -> str | None:
        return self.text_path(label).read_text(encoding="utf-8").strip() if self.text_path(label).exists() else None

    def prepare(self, label: str) -> None:
        """Start making the description unless it exists or was already tried; a failure waits for a click."""
        if label not in self.jobs and not self.ready(label):
            self.jobs[label] = self.pool.submit(self._make, label)

    def click(self, label: str) -> str:
        if self.ready(label):
            if self.speak is None:
                return "shown"
            self.stop()
            self.playing = self.play(self.wav(label))
            return "playing"
        job = self.jobs.get(label)
        if job is None or (job.done() and job.exception() is not None):
            self.jobs[label] = self.pool.submit(self._make, label)
            return "retrying"
        return "pending"

    def stop(self) -> None:
        if self.playing is not None and self.playing.poll() is None:
            self.playing.terminate()

    def close(self) -> None:
        self.stop()
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _make(self, label: str) -> None:
        try:
            text = self.description(label)
            if text is None:
                text = self.describe(label)
                _write(self.text_path(label), (text + "\n").encode("utf-8"))
                logging.info("Description ready label=%r text=%r", label, text)
            if self.speak is not None:
                _write(self.wav(label), self.speak(text))
                logging.info("Audio ready label=%r", label)
        except Exception:
            logging.exception("Description failed label=%r", label)
            raise


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    partial.write_bytes(data)
    os.replace(partial, path)  # ready() never sees a half-written file
