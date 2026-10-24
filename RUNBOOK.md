# Runbook

Run every command from the repository root with the virtual environment active
(`source .venv/bin/activate`). Runners are modules: always use `python -m`.

This runbook does not install runtimes or download weights. Those are one-time,
owner-run steps, listed in `AGENTS.md`.

## 1. Prepare inputs

- Add only permitted photos and fill in `evaluation/manifest.csv` from
  `evaluation/manifest_template.csv`. Keep labels out of filenames and image IDs.
- Gemini and cascade runs upload images to Google. Use only rows whose
  `permission_provenance_notes` allow that.
- Scoring needs reviewed ground-truth boxes in original-image pixels, in the
  format in `evaluation/COLLECTION.md`. Whole-image labels are not boxes.

Check the manifest and frozen configs:

```sh
python -m evaluation.score evaluation/manifest.csv
python -m json.tool recognition/yolo_model.json >/dev/null
shasum -a 256 /absolute/path/to/yolo26n.pt
```

## 2. Run the candidates

Each run writes one JSONL record per image, plus a log next to it
(`<output>.log`, or `--log PATH`). The weights argument must be an existing
local file whose name matches the config.

YOLO26n COCO baseline (`laptop` and `phone` only):

```sh
python -m recognition.yolo_runner \
  evaluation/manifest.csv evaluation/yolo_predictions.jsonl \
  --weights /absolute/path/to/yolo26n.pt --device cpu
```

YOLO-World, same runner with an open-vocabulary config (`_l_` and `_x_`
variants exist for the larger weights):

```sh
python -m recognition.yolo_runner \
  evaluation/manifest.csv evaluation/yolo_world_predictions.jsonl \
  --weights /absolute/path/to/yolov8s-worldv2.pt \
  --config recognition/yolo_world_model.json --device cpu
```

Gemini, the primary candidate. Load the key into the shell without printing it,
and smoke-test three images before the full manifest:

```sh
set -a; . ./.env; set +a
python -m recognition.gemini_runner \
  evaluation/manifest.csv evaluation/gemini_predictions.jsonl
```

The default model is `gemini-3.5-flash-lite`. `--model gemini-3.8-flash` is
kept for comparison, but it needs billing beyond 20 requests a day.

The cascade, the fallback candidate. It calls Gemini only when YOLO-World
proposes at least one box:

```sh
python -m recognition.cascade_runner \
  evaluation/manifest.csv evaluation/cascade_predictions.jsonl \
  --weights /absolute/path/to/yolov8l-worldv2.pt
```

Defaults: `--config recognition/yolo_world_l_model.json`,
`--proposal-confidence 0.1`.

## 3. Inspect the evidence

```sh
head -n 1 evaluation/yolo_predictions.jsonl | python -m json.tool
grep -n '"error":"' evaluation/yolo_predictions.jsonl
```

Confirm the weights SHA-256, runtime version, command, thresholds, raw class
names, confidences and `xyxy` boxes. Unsupported raw classes stay in
`raw_predictions` with `mapping_status: "unsupported"`.

## 4. Score

Only after box annotations exist. Score every run together:

```sh
python -m evaluation.score_detection evaluation/manifest.csv \
  evaluation/gemini_predictions.jsonl \
  evaluation/cascade_predictions.jsonl \
  evaluation/yolo_world_predictions.jsonl \
  evaluation/yolo_predictions.jsonl \
  --json evaluation/bakeoff_results.json
```

Paste the table into a copy of `evaluation/bakeoff_report_template.md` and
apply its frozen decision rule. (`evaluation/score.py` only scores the separate
whole-image VLM comparison.)

## 5. Live camera

The trained detector (`training/weights/scavscrap_v2_best.pt` with
`recognition/scavscrap_v2_model.json`, both the defaults) runs on every frame.
A box that lasts 5 frames shows at once in yellow with the detector class.
Gemini then names it in free text from `recognition/prompt-live-v2.txt`: brand
and product family when a logo or family-unique design is visible ("Apple
iPhone"), never an exact model, else a generic type ("smartphone") plus a hint
("move closer", "improve lighting", "hold still", "show the logo side"). Gemini
sees the full frame and a full-resolution close-up of each box, runs off the
detection thread, and re-asks generic labels every 10 s. The box turns green
with the name, or disappears if Gemini says "none". Frames with new tracks are
uploaded, so `--allow-upload` is required. Press `q` to quit.

```sh
set -a; . ./.env; set +a
python -m recognition.live_runner evaluation/live_predictions.jsonl \
  --allow-upload --camera 0 --device mps
```

Each named box also gets a 2-3 sentence description (`recognition/narrator.py`,
prompt `recognition/prompt-describe-v1.txt`, cached in `cache/narration/`). The
label shows `[click]` when it is ready; clicking the box shows it in a panel.
With `ELEVENLABS_API_KEY` set, the click also plays it as audio.

Each JSONL line is one detected frame. `label_source` is `gemini` on the
labelling frame and `track_cache` afterwards: cached labels are not fresh
per-frame inference. Tracks continue across small jumps of the same detector
class, so a moved item keeps its label.

For Meta glasses, replace `--camera 0` with `--listen 0.0.0.0:8765`. Setup is in
`app/ios/README.md`. The dashboard gets `gemini_label` as the project class
(`laptop`, `phone`, ...) once Gemini confirms the item, plus `name` with
Gemini's free-text name.

## Checks

```sh
python -m unittest
```

These tests mock every model and API. Passing them says nothing about accuracy.
