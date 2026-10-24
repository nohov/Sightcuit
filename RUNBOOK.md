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

## 5. Bake-off runs (owner-approved exceptions in `AGENTS.md`)

YOLO-World uses the same runner with its own frozen config. Its weights
(`yolov8s-worldv2.pt`) and the CLIP text encoder that `set_classes` needs are an
owner-run, one-time download:

```sh
python3 recognition/yolo_runner.py \
  evaluation/manifest.csv \
  evaluation/yolo_world_predictions.jsonl \
  --weights /absolute/path/to/yolov8s-worldv2.pt \
  --config recognition/yolo_world_model.json \
  --device cpu
```

The fallback candidate, the cascade, needs both the YOLO-World L weights and the
Gemini key. It sends an image to Google only when YOLO proposes at least one box:

```sh
set -a; . ./.env; set +a   # loads GEMINI_API_KEY without printing it
.venv/bin/python -m recognition.cascade_runner \
  evaluation/manifest.csv \
  evaluation/cascade_predictions.jsonl \
  --weights /absolute/path/to/yolov8l-worldv2.pt
```

Defaults: `--config recognition/yolo_world_l_model.json`,
`--model gemini-3.5-flash-lite`, `--proposal-confidence 0.1`.

Live camera (cascade + track cache): YOLO-World runs on every frame, boxes are
matched to in-memory tracks by IoU, and Gemini labels only tracks with no cached
label (at most one call per `--min-call-interval`, default 2 s). Frames with new
tracks are uploaded to Google, so `--allow-upload` is required. Press `q` to quit:

```sh
set -a; . ./.env; set +a
.venv/bin/python -m recognition.live_runner \
  evaluation/live_predictions.jsonl \
  --weights /absolute/path/to/yolov8l-worldv2.pt \
  --allow-upload --camera 0
```

Each JSONL line is one frame; `label_source` is `gemini` on the labelling frame
and `track_cache` afterwards. Cached labels are not fresh per-frame inference.

Whole-image Gemini runs send every image to Google. Set the key in the shell
only, then smoke-test three images before the full manifest:

```sh
export GEMINI_API_KEY=...   # never commit or log
python3 -m recognition.gemini_runner \
  evaluation/manifest.csv \
  evaluation/gemini_predictions.jsonl \
  --model gemini-3.5-flash-lite   # primary; gemini-3.8-flash needs billing beyond 20 requests/day
```

## 6. Score only after box annotations exist

Ground-truth boxes follow the frozen format in `evaluation/COLLECTION.md`. Score
every run together:

```sh
python3 -m evaluation.score_detection evaluation/manifest.csv \
  evaluation/cascade_predictions.jsonl \
  evaluation/gemini_predictions.jsonl \
  evaluation/yolo_world_predictions.jsonl \
  evaluation/yolo_predictions.jsonl \
  --json evaluation/bakeoff_results.json
```

Paste the output into a copy of `evaluation/bakeoff_report_template.md` and
apply its frozen decision rule. `evaluation/score.py` remains the whole-image
VLM scorer only.

## Checks

```sh
python3 -m unittest recognition.tests.test_yolo_runner recognition.tests.test_vlm_runner \
  recognition.tests.test_gemini_runner recognition.tests.test_cascade_runner \
  evaluation.tests.test_score evaluation.tests.test_score_detection tests.test_integration -v
python3 -m py_compile recognition/yolo_runner.py recognition/vlm_runner.py \
  recognition/gemini_runner.py recognition/cascade_runner.py \
  evaluation/score.py evaluation/score_detection.py
```
