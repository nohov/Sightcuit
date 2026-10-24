"""Output and logging plumbing shared by the batch and live runners."""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import shlex
import sys
import tempfile
from typing import Any, Callable, Iterator


@contextmanager
def atomic_jsonl(output: Path) -> Iterator[Callable[[dict[str, Any]], None]]:
    """Yield a write(record) function; `output` is replaced only if the whole run finishes."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as destination:
            temporary_path = Path(destination.name)
            yield lambda record: destination.write(json.dumps(record, separators=(",", ":")) + "\n")
        os.replace(temporary_path, output)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def start_logging(output: Path, log: Path | None) -> str:
    """Log to `log` (default `<output>.log`) and return the exact command line for run records."""
    log_path = log or output.with_suffix(output.suffix + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    command = shlex.join([sys.executable, *sys.argv])
    logging.info("Starting command: %s", command)
    return command
