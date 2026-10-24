#!/usr/bin/env python3
"""Automatic tests for the trained ScavScrap YOLO detector.

Run from the ``training`` directory with the project venv so Ultralytics and the
CUDA torch build are importable::

    .venv\\Scripts\\python -m unittest discover -s tests          # Windows
    .venv/bin/python -m unittest discover -s tests               # macOS/Linux
    .venv\\Scripts\\python tests\\test_trained_model.py           # direct run

What gets checked (fast tests first, slow val gate last):

1. the weights file exists and loads as an 11-class detector whose class names
   match ``datasets/scavscrap/data.yaml`` exactly and in order;
2. inference on a handful of real validation images produces well-formed boxes
   (xyxy inside the image, confidence in [0, 1], class id in range);
3. a full ``model.val()`` pass clears the quality gates below.

The val gate skips itself (rather than failing) when the dataset is not present,
so this file is safe to run on a machine that only has the weights. Thresholds
sit comfortably below the measured scavscrap_v2 numbers (overall mAP50 0.684 /
mAP50-95 0.505, weakest class router AP50 0.166) and well above the v1 baseline
(~0.40), so a healthy model passes and a real regression fails. Override any of
them with the ``SCAVSCRAP_*`` environment variables documented below.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

# training/ (parent of tests/) is the root all default paths resolve against.
TRAINING_ROOT = Path(__file__).resolve().parents[1]


def _resolve(env_var: str, default_relative: str) -> Path:
    value = os.environ.get(env_var)
    path = Path(value) if value else TRAINING_ROOT / default_relative
    return path if path.is_absolute() else (TRAINING_ROOT / path)


MODEL_PATH = _resolve("SCAVSCRAP_MODEL", "runs/detect/scavscrap_v2/weights/best.pt")
DATA_PATH = _resolve("SCAVSCRAP_DATA", "datasets/scavscrap/data.yaml")
DEVICE = os.environ.get("SCAVSCRAP_DEVICE", "0")  # "0" = first GPU, "cpu" otherwise

# Quality gates. Current scavscrap_v2: overall mAP50 0.684, mAP50-95 0.505;
# weakest class router AP50 0.166. Floors leave margin so the gate is a real
# regression signal, not a flaky re-measurement of the exact training result.
MAP50_MIN = float(os.environ.get("SCAVSCRAP_MAP50_MIN", "0.60"))
MAP5095_MIN = float(os.environ.get("SCAVSCRAP_MAP5095_MIN", "0.45"))
PER_CLASS_AP50_MIN = float(os.environ.get("SCAVSCRAP_CLASS_AP50_MIN", "0.05"))

# Frozen class contract. Stage 2 (Gemini) relies on these ids being stable, so
# the order matters as much as the membership.
EXPECTED_CLASSES = [
    "laptop",
    "desktop_computer_tower",
    "monitor",
    "printer",
    "projector",
    "keyboard",
    "mouse",
    "phone",
    "tablet",
    "tv",
    "router",
]

# How many validation images the inference smoke test exercises.
SMOKE_IMAGE_COUNT = int(os.environ.get("SCAVSCRAP_SMOKE_IMAGES", "5"))


def _data_yaml_names(data_yaml: Path) -> list[str]:
    """Read the ordered class-name list out of an Ultralytics data.yaml."""
    import yaml  # ships as an Ultralytics dependency

    spec = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    names = spec["names"]
    if isinstance(names, dict):  # {0: laptop, 1: ...}
        return [names[i] for i in range(len(names))]
    return list(names)  # already an ordered list


def _val_image_paths(data_yaml: Path, limit: int) -> list[Path]:
    """Resolve the first ``limit`` existing images from the val list."""
    spec = __import__("yaml").safe_load(data_yaml.read_text(encoding="utf-8"))
    val_list = (data_yaml.parent / spec["val"]).resolve()
    if not val_list.is_file():
        return []
    images: list[Path] = []
    for line in val_list.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        candidate = (val_list.parent / line).resolve()
        if candidate.is_file():
            images.append(candidate)
        if len(images) >= limit:
            break
    return images


class TrainedModelTests(unittest.TestCase):
    model = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - environment guard
            raise unittest.SkipTest(f"ultralytics not importable: {exc}")
        if not MODEL_PATH.is_file():
            raise unittest.SkipTest(
                f"trained weights not found at {MODEL_PATH}; set SCAVSCRAP_MODEL"
            )
        # Only our own trained weights are loaded here; .pt files can execute
        # code on load, so never point SCAVSCRAP_MODEL at an untrusted file.
        cls.model = YOLO(str(MODEL_PATH), task="detect")

    def _names_in_order(self) -> list[str]:
        names = self.model.names
        return [names[i] for i in range(len(names))]

    def test_model_loads_as_detector(self) -> None:
        self.assertEqual(self.model.task, "detect")

    def test_class_names_match_frozen_contract(self) -> None:
        self.assertEqual(self._names_in_order(), EXPECTED_CLASSES)

    def test_class_names_match_dataset_yaml(self) -> None:
        if not DATA_PATH.is_file():
            self.skipTest(f"data.yaml not found at {DATA_PATH}")
        self.assertEqual(self._names_in_order(), _data_yaml_names(DATA_PATH))

    def test_inference_on_val_samples_is_well_formed(self) -> None:
        if not DATA_PATH.is_file():
            self.skipTest(f"data.yaml not found at {DATA_PATH}")
        images = _val_image_paths(DATA_PATH, SMOKE_IMAGE_COUNT)
        if not images:
            self.skipTest("no validation images available for the smoke test")

        n_classes = len(self._names_in_order())
        results = self.model.predict(
            source=[str(p) for p in images],
            conf=0.25,
            iou=0.7,
            device=DEVICE,
            save=False,
            verbose=False,
        )
        self.assertEqual(len(results), len(images))

        for image, result in zip(images, results):
            with self.subTest(image=image.name):
                self.assertIsNotNone(result.boxes, "model produced no boxes tensor")
                height, width = result.orig_shape
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    self.assertTrue(
                        0 <= x1 < x2 <= width + 1 and 0 <= y1 < y2 <= height + 1,
                        f"box {[x1, y1, x2, y2]} outside {width}x{height}",
                    )
                    conf = float(box.conf[0])
                    self.assertGreaterEqual(conf, 0.0)
                    self.assertLessEqual(conf, 1.0)
                    cls_id = int(box.cls[0])
                    self.assertTrue(0 <= cls_id < n_classes, f"class id {cls_id} out of range")

    def test_val_metrics_meet_thresholds(self) -> None:
        if os.environ.get("SCAVSCRAP_SKIP_VAL"):
            self.skipTest("val gate skipped via SCAVSCRAP_SKIP_VAL")
        if not DATA_PATH.is_file():
            self.skipTest(f"data.yaml not found at {DATA_PATH}; cannot run the val gate")
        if not _val_image_paths(DATA_PATH, 1):
            self.skipTest("validation images not present; cannot run the val gate")

        metrics = self.model.val(
            data=str(DATA_PATH),
            split="val",
            device=DEVICE,
            verbose=False,
            plots=False,
        )
        map50 = float(metrics.box.map50)
        map5095 = float(metrics.box.map)
        print(f"\n[val gate] overall mAP50={map50:.4f} mAP50-95={map5095:.4f}")

        names = self._names_in_order()
        per_class = {}
        for position, cls_id in enumerate(metrics.box.ap_class_index):
            name = names[int(cls_id)]
            ap50 = float(metrics.box.ap50[position])
            per_class[name] = ap50
            print(f"[val gate]   {name:<24} AP50={ap50:.4f}")

        self.assertGreaterEqual(
            map50, MAP50_MIN, f"overall mAP50 {map50:.4f} below gate {MAP50_MIN}"
        )
        self.assertGreaterEqual(
            map5095, MAP5095_MIN, f"overall mAP50-95 {map5095:.4f} below gate {MAP5095_MIN}"
        )

        # Every trained class must still detect something — a class that drops to
        # ~0 means it was broken by a dataset or label regression.
        missing = [name for name in names if name not in per_class]
        self.assertFalse(missing, f"classes absent from val predictions entirely: {missing}")
        dead = {n: ap for n, ap in per_class.items() if ap < PER_CLASS_AP50_MIN}
        self.assertFalse(dead, f"classes below per-class AP50 floor {PER_CLASS_AP50_MIN}: {dead}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
