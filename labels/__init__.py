"""Project class contract, loaded once from `classes.json` so code cannot drift from it."""

import json
from pathlib import Path

_CONTRACT = json.loads(Path(__file__).with_name("classes.json").read_text(encoding="utf-8"))

# Order is frozen: it gives each class a stable raw_class_id in Gemini and cascade records.
TARGET_CLASSES: tuple[str, ...] = tuple(entry["id"] for entry in _CONTRACT["classes"])
NON_CLASS_OUTCOMES: tuple[str, ...] = tuple(entry["id"] for entry in _CONTRACT["non_class_outcomes"])
