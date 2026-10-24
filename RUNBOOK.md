# First YOLO detection experiment

Run commands from `~/Documents/scavscrap`.

## 1. Supply approved local inputs

Do not use this runbook to install a runtime or download weights. Confirm that an
approved Ultralytics runtime and an existing local `yolo11n.pt` are available.
Add only permitted images and complete `evaluation/manifest.csv` from the
template. Keep labels out of filenames and image IDs.

Detection evaluation also needs reviewed ground-truth boxes in original-image
pixel coordinates. Do not treat whole-image labels as localization annotations.

## 2. Verify the manifest and frozen mapping

```sh
python3 evaluation/score.py evaluation/manifest.csv
python3 -m json.tool recognition/yolo_model.json >/dev/null
python3 -m json.tool recognition/prediction.schema.json >/dev/null
shasum -a 256 /absolute/path/to/yolo11n.pt
```

## 3. Run detection

```sh
python3 recognition/yolo_runner.py \
  evaluation/manifest.csv \
  evaluation/yolo_predictions.jsonl \
  --weights /absolute/path/to/yolo11n.pt \
  --confidence 0.25 \
  --iou 0.70 \
  --device cpu \
  --log evaluation/yolo_run.log
```

The weights argument must resolve to a local file. The harness refuses a missing
path and a class list that differs from the frozen COCO order.

## 4. Inspect evidence

```sh
head -n 1 evaluation/yolo_predictions.jsonl | python3 -m json.tool
grep -n '"error":' evaluation/yolo_predictions.jsonl
sed -n '1,160p' evaluation/yolo_run.log
```

Confirm the recorded weights SHA-256, runtime version, device, command,
thresholds, timing, raw class names, confidence values, and `xyxy` boxes.
Unsupported raw classes remain in `raw_predictions` and have no project mapping.

## 5. Score only after box annotations exist

The current `evaluation/score.py` validates manifests and scores the separate
whole-image VLM output. It does not score bounding boxes. Add or approve a
detection scorer only with a frozen ground-truth box format; until then, inspect
YOLO outputs without claiming detection precision or recall.

## Checks

```sh
python3 -m unittest recognition.tests.test_yolo_runner -v
python3 -m unittest recognition.tests.test_vlm_runner -v
python3 -m unittest evaluation.tests.test_score -v
python3 -m unittest tests.test_integration -v
python3 -m py_compile recognition/yolo_runner.py recognition/vlm_runner.py evaluation/score.py
```
