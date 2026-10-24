#!/usr/bin/env python3
"""Run the frozen five-class image experiment through a local Ollama server."""

from __future__ import annotations

import argparse
import base64
import csv
import json
from pathlib import Path
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from labels import NON_CLASS_OUTCOMES, TARGET_CLASSES
from recognition.runio import atomic_jsonl


PROMPT_VERSION = "electronics-pokedex-v2"
DEFAULT_MODEL = "qwen3-vl:4b-instruct-q4_K_M"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434/api/chat"
OUTCOMES = {*TARGET_CLASSES, *NON_CLASS_OUTCOMES}
HERE = Path(__file__).resolve().parent
Transport = Callable[[dict[str, Any], str, float], dict[str, Any]]


def manifest_entries(manifest: Path):
    """Yield line number and entry from evaluation CSV or legacy JSONL."""
    if manifest.suffix.lower() == ".csv":
        with manifest.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            missing = {"image_id", "path"} - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV manifest missing fields: {', '.join(sorted(missing))}")
            yield from enumerate(reader, 2)
        return

    with manifest.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if line.strip():
                yield line_number, line


def ollama_transport(payload: dict[str, Any], endpoint: str, timeout: float) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama connection failed: {exc.reason}") from exc


def build_payload(
    image_bytes: bytes, model: str, prompt: str, response_schema: dict[str, Any]
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            }
        ],
        "stream": False,
        "format": response_schema,
        "options": {"temperature": 0},
    }


def parse_model_response(response: dict[str, Any]) -> tuple[str, str, str]:
    if response.get("error"):
        raise ValueError(f"provider error: {response['error']}")
    raw = response["message"]["content"]
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {"outcome", "evidence"}:
        raise ValueError("response must contain only outcome and evidence")
    outcome, evidence = parsed["outcome"], parsed["evidence"]
    if outcome not in OUTCOMES or not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("response has an invalid outcome or evidence")
    return outcome, evidence.strip(), raw


def error_record(image_id: str, model: str, outcome: str, error: str, latency_ms: float = 0.0,
                 raw_response: str | None = None) -> dict[str, Any]:
    return {
        "image_id": image_id,
        "outcome": outcome,
        "evidence": None,
        "model_identifier": model,
        "prompt_version": PROMPT_VERSION,
        "latency_ms": round(latency_ms, 3),
        "error": error,
        "raw_response": raw_response,
    }


def classify(
    entry: dict[str, Any],
    manifest_dir: Path,
    model: str,
    endpoint: str,
    timeout: float,
    prompt: str,
    response_schema: dict[str, Any],
    transport: Transport = ollama_transport,
) -> dict[str, Any]:
    image_id = entry.get("image_id")
    if not isinstance(image_id, str) or not image_id:
        return error_record("unknown", model, "unsupported", "manifest_error: image_id must be a non-empty string")
    image_path = entry.get("path")
    if not isinstance(image_path, str) or not image_path:
        return error_record(image_id, model, "unreadable", "manifest_error: path must be a non-empty string")

    try:
        image_bytes = (manifest_dir / image_path).read_bytes()
        if not image_bytes:
            raise ValueError("image file is empty")
    except (OSError, ValueError) as exc:
        return error_record(image_id, model, "unreadable", f"image_error: {exc}")

    started = time.perf_counter()
    response: dict[str, Any] | None = None
    try:
        payload = build_payload(image_bytes, model, prompt, response_schema)
        response = transport(payload, endpoint, timeout)
        outcome, evidence, raw = parse_model_response(response)
        return {
            "image_id": image_id,
            "outcome": outcome,
            "evidence": evidence,
            "model_identifier": model,
            "prompt_version": PROMPT_VERSION,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": None,
            "raw_response": raw,
        }
    except Exception as exc:
        raw = None
        if isinstance(response, dict):
            message = response.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            raw = content if isinstance(content, str) else json.dumps(response, sort_keys=True)
        return error_record(
            image_id,
            model,
            "unsupported",
            f"inference_error: {type(exc).__name__}: {exc}",
            (time.perf_counter() - started) * 1000,
            raw,
        )


def run_manifest(
    manifest: Path,
    output: Path,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 120.0,
    transport: Transport = ollama_transport,
) -> None:
    manifest, output = manifest.resolve(), output.resolve()
    if manifest == output:
        raise ValueError("manifest and output paths must differ")
    prompt = (HERE / "prompt-vlm-v2.txt").read_text(encoding="utf-8")
    response_schema = json.loads((HERE / "model_response.schema.json").read_text(encoding="utf-8"))

    with atomic_jsonl(output) as write:
        for line_number, raw_entry in manifest_entries(manifest):
            try:
                entry = raw_entry if isinstance(raw_entry, dict) else json.loads(raw_entry)
                if not isinstance(entry, dict):
                    raise ValueError("entry must be an object")
                record = classify(
                    entry, manifest.parent, model, endpoint, timeout, prompt,
                    response_schema, transport,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                record = error_record(
                    f"manifest-line-{line_number}", model, "unsupported", f"manifest_error: {exc}"
                )
            write(record)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="CSV or JSONL with image_id and path")
    parser.add_argument("output", type=Path, help="prediction JSONL path")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    run_manifest(args.manifest, args.output, args.model, args.endpoint, args.timeout)


if __name__ == "__main__":
    main()
