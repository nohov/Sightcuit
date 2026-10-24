# Handoff: ScavScrap electronics detector, v3 (adds headphones, speaker, watch)

For a new Claude Code session continuing this work on the Windows machine with
the NVIDIA RTX 4070 Ti. Read this whole file before acting. Last updated 2026-10-24.

## 0. TL;DR: what to do on this machine

1. Pull the branch (section 2), set up the machine (section 3), and create
   `.env` in the repo root with `GEMINI_API_KEY=...` (only needed for the live app).
2. Get a Roboflow API key into the environment (section 4). Every download is a
   command; nothing comes from Google Drive any more.
3. Rebuild the dataset from scratch with 14 classes (section 7, about 30-90 min).
4. Train v3 (section 7, estimate 2.5-3.5 h for yolo11n).
5. Check per-class scores, point the live app at v3, test it live, commit
   `weights/scavscrap_v3_best.pt`, push (section 7.5).

## 1. What the project is

ScavScrap ("Electronics Pokédex") is a hackathon app for engineering students:
point a camera at tech items, the app finds each one, identifies it, and shows
its specs from cited web sources. The pipeline:

```text
camera frame → stage 1 detect (YOLO, trained here, local, ~10 ms/frame)
             → stage 2 identify (Gemini: brand + product family, e.g. "Apple MacBook")
             → stage 3 specs (Gemini with web search grounding, every spec cites a URL)
```

Stage 1 and 2 already run live: `recognition/live_runner.py` (see section 6).
Exact model/SKU is out of scope on purpose: MacBooks (and many product lines)
look the same outside but differ inside, so Gemini names the family only. The
detector only needs coarse categories; fine distinctions (smartwatch vs analog
watch, Bluetooth vs wired speaker, earbuds vs over-ear) are Gemini's job.

**Why v3:** the live test showed Gemini can name a smartwatch or earbuds
correctly, but only if the detector draws a box. v2 has no accessory classes,
so it boxed them as `phone` for 1-2 frames at 15-29% confidence. v3 teaches the
detector `headphones`, `speaker` and `watch`.

## 2. Repo state

- Branch: `gursimar/yolo26-training`. `git pull` it. Commit and push there.
  Never push to `main`.
- `training/` is the training workspace. `datasets/`, `runs/` and logs are
  gitignored. Trained checkpoints are force-added on purpose
  (`git add -f weights/scavscrap_vN_best.pt`) so other machines get them by pulling.
- `recognition/live_runner.py` is the live camera app, already switched to the
  trained detector and to free-text Gemini labels. Its tests:
  `python -m unittest recognition.tests.test_live_runner` from the repo root.
- **Stale, do not follow for training work:** `AGENTS.md`, `READINESS.md`, and
  the evaluation parts of `README.md`/`RUNBOOK.md`. They describe an earlier
  milestone (evaluating stock COCO YOLO11 on 5 classes) and forbid installing
  packages, downloading weights and training. The owner has replaced that.
- `.env` (holds `GEMINI_API_KEY`) is gitignored. Each machine needs its own copy
  in the repo root; never commit it or paste the key into chat.

## 3. Machine setup (Windows, PowerShell, from `training\`)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
.venv\Scripts\yolo settings datasets_dir=$PWD\datasets weights_dir=$PWD\weights runs_dir=$PWD\runs sync=False
```

- Install the CUDA torch build first. Plain `pip install` on Windows gives a
  CPU-only torch. The check must print `True`. If `cu128` fails, check the
  driver's CUDA version with `nvidia-smi` and pick the matching index URL.
- `README.md` commands use macOS paths (`.venv/bin/...`). On Windows use
  `.venv\Scripts\...`.
- Unzip with 7-Zip into a short path (e.g. `C:\scavscrap\`) if Explorer fails:
  Windows has a 260-character path limit.

## 4. Inputs: one API key

All data downloads are commands (section 7.2). The only manual input is a
Roboflow API key, for the 9 Roboflow Universe exports the dataset uses:

1. Sign in at roboflow.com (free), then Settings > API Keys, copy the private key.
2. Add a line `ROBOFLOW_API_KEY=...` to `.env` in the repo root (gitignored),
   next to `GEMINI_API_KEY`. Never paste the key into chat or a commit.
3. Load `.env` into the PowerShell session before building:
   `Get-Content ..\.env | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item "env:$k" $v }`
   (from `training\`).

`build_dataset.py roboflow-download` then fetches each export through the
Roboflow API (YOLOv8 format), caches it in `datasets\_raw\roboflow\`, and
imports it with the class mapping in `ROBOFLOW_SETS`. Those mappings were
recovered from the v2 labels, so the rebuild matches v2.

- `gursimar-gill/desktop-pc-dearc-vfv1m` is a fork in Gursimar's workspace. If
  it fails with HTTP 403/404 under someone else's key, use Gursimar's key or
  make that project public in Roboflow.
- Not tested end to end yet (no key on the Mac that wrote it). The API path and
  the 401 error handling were checked. If the API response format surprises
  you, fix `roboflow_link()` and update this note.
- `scavscrap.zip` (the old 11-class dataset on Google Drive) is not needed.

## 5. The v2 dataset (11 classes; v3 adds 3, see section 7)

`0 laptop, 1 desktop_computer_tower, 2 monitor, 3 printer, 4 projector,
5 keyboard, 6 mouse, 7 phone, 8 tablet, 9 tv, 10 router`

21,185 images (18,037 train / 3,148 val). Boxes per class: laptop 8143,
desktop_computer_tower 2067, monitor 10384, printer 3791, **projector 358**,
keyboard 6645, mouse 3430, phone 5109, tablet 5366, tv 2682, **router 758**.

Sources, all merged by `scripts/build_dataset.py`:

- **Open Images V7**: 12,000 train images via FiftyOne, filtered to our classes.
- **LVIS v1**: 1,833 COCO images containing monitor/printer/projector/router.
- **Objects365**: 1,910 images from 12 *validation* patches (the only source of
  towers apart from Roboflow). Downloaded from a public server in Beijing that
  times out sometimes. The script retries.
- **Roboflow Universe**: desktop-pc-dearc, detect-router-nowgx, monitor-zsqud,
  monitor-vmdjp, printer-apkfy, printer-ler5v, classroom-ju7eu (projector),
  mouse-keyboard-tablet, tablets-wwxv9. Listed with their versions and class
  mappings in `ROBOFLOW_SETS`; `build_dataset.py roboflow-download` fetches and
  imports all of them.

Label decisions already made. Keep them when rebuilding:

- `tv` is separate from `monitor` on purpose.
- Objects365's merged `Moniter/TV` class (that spelling is upstream) is painted
  gray in the image, not guessed.
- A `monitor` box overlapping a `laptop` box with IoU > 0.5 is dropped. Open
  Images and LVIS label laptop screens as monitors (~400 boxes).
- LVIS images whose `not_exhaustive_category_ids` include one of our classes are
  skipped.
- Roboflow polygon rows are converted to their bounding box. Filenames are capped
  at 100 characters (Windows paths). Augmented copies of one photo stay in the
  same split (grouped by the name before `.rf.`).
- Split is a stable hash of the filename, 15% val.

Known label noise (accept it, or fix with more data):

- Open Images and LVIS have no tower class, so towers in those photos are
  unlabeled.
- Single-class Roboflow sets (printer, tablet, monitor) contain other devices
  that nobody labeled.
- Projector and router are thin. More Objects365 *train* patches (3.9 GB each,
  stream them and keep only matching images) are the best fix. The Hugging Face
  mirror `jxu124/objects365` has labels only, no images.

## 6. Current model (v2) and the live app

v2: yolo11n, 11 classes, trained 49/50 epochs on a 4070 Super, 21,185 images,
~2-3 min/epoch. mAP50 0.683, mAP50-95 0.504. File:
`weights/scavscrap_v2_best.pt` (committed).

Live app, from the repo root. macOS:

```sh
set -a; . ./.env; set +a
training/.venv/bin/python -m recognition.live_runner evaluation/live_predictions.jsonl --allow-upload --camera 0 --device mps
```

Windows (PowerShell):

```powershell
Get-Content .env | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item "env:$k" $v }
training\.venv\Scripts\python -m recognition.live_runner evaluation/live_predictions.jsonl --allow-upload --camera 0 --device 0
```

Press `q` in the window to quit. How it behaves (all in `recognition/live_runner.py`,
prompt in `recognition/prompt-live-v2.txt`, tested in
`recognition/tests/test_live_runner.py`):

- Defaults: `training/weights/scavscrap_v2_best.pt` with
  `recognition/scavscrap_v2_model.json` (the frozen class list the app checks
  the weights against), detection threshold from that config (0.25), Gemini
  `--thinking-level minimal`.
- A box that lasts 5 frames (~0.2 s) is drawn at once in **yellow** with the
  detector class (`#3 phone...`). When Gemini answers it turns **green** with
  the name (`#3 Apple iPhone`). If Gemini says "none" (not a tech item, e.g. a
  toothpaste tube the detector calls a phone at 84%), the box disappears.
- Gemini gets the full frame plus a full-resolution close-up of each box, and
  returns `label`, `identified` and `hint`. Labels are brand + product family
  ("Apple iPhone"), never the exact model, because one family looks alike
  outside but differs inside. If only a generic type is visible ("smartphone"),
  it adds a hint (`move closer`, `improve lighting`, `hold still`,
  `show the logo side`) and the box is re-asked every 10 s while in view.
- Gemini runs off the detection thread, one call at a time. Measured: 6-26 s per
  answer (Gemini 3.5 Flash-Lite, plus 4/8/16 s retries on frequent HTTP 503).
- Tracking: a same-class box near a track's last position continues it, and a
  track survives ~1.5 s unseen. Before this, a hand-held phone got 13 track IDs
  in 76 s and Gemini answers landed on dead tracks.
- Each frame is appended to `evaluation/live_predictions.jsonl` (gitignored);
  analyse it to debug what was detected, sent and answered.

## 7. Next task: build and train v3 (14 classes)

### 7.1 Already done (on the Mac, 2026-10-24)

`scripts/build_dataset.py` now has 14 classes. The new ones are appended so IDs
0-10 are unchanged from v2: `11 headphones` (earbuds included), `12 speaker`,
`13 watch` (smartwatches included). Source names were checked against the real
annotation files:

| Our class | Open Images | LVIS (`name`) | Objects365 |
|---|---|---|---|
| headphones | `Headphones` | `earphone`, `headset` | `Head Phone`, `earphone` |
| speaker | none | `speaker_(stero_equipment)` (sic) | `Speaker` |
| watch | `Watch` | `watch` | `Watch` |

They are in `OPENIMAGES`, `LVIS`, `O365`, `LVIS_REQUIRED` and `O365_REQUIRED`.
`selftest` passes. Not added (ask the owner first): `camera`, `game_controller`.

### 7.2 Rebuild the dataset from scratch

Do not add new images on top of the old dataset. The existing 21k images
contain headphones, speakers and watches that are unlabeled; left that way, the
model learns they are background. A full rebuild relabels every image.

From `training\`:

```powershell
Remove-Item -Recurse -Force datasets\scavscrap   # stale 11-class labels must not survive
.venv\Scripts\python scripts\build_dataset.py selftest
.venv\Scripts\python scripts\build_dataset.py openimages   # FiftyOne download, the slow part
.venv\Scripts\python scripts\build_dataset.py lvis
.venv\Scripts\python scripts\build_dataset.py objects365   # Beijing server, may time out; it retries
.venv\Scripts\python scripts\build_dataset.py roboflow-download   # needs ROBOFLOW_API_KEY (section 4)
.venv\Scripts\python scripts\build_dataset.py split        # writes train.txt, val.txt, data.yaml
```

Estimate: 30-90 min, mostly the Open Images download (keep `datasets\_raw\`
afterwards; reruns reuse it). `split` prints boxes per class. **Check the three
new classes.** Rough target: 1,000+ boxes each.

- If `headphones` or `watch` are low: raise `openimages(max_samples=12000)`; the
  12k cap is shared across all Open Images classes.
- `speaker` will be the weakest (Open Images has no speaker class). Top it up
  from Roboflow (7.3).

### 7.3 Optional: Roboflow top-ups for weak classes

Only if a class is under ~1,000 boxes after 7.2, or scores poorly after
training. Download each as a **YOLOv8** zip (free Roboflow account), check its
`data.yaml` names, import before `split`:

| Set | Map to | Notes |
|---|---|---|
| https://universe.roboflow.com/aihat/headphones-moskk | headphones | ~1,070 images |
| https://universe.roboflow.com/project-qysdi/earbuds-vepar | headphones | earbuds |
| https://universe.roboflow.com/bag-bibi4/earphone-jueif | headphones | ~143 images |
| https://universe.roboflow.com/abirami-j/gadget_detection_exam | watch (smartwatch class only) | drop its other classes |
| https://universe.roboflow.com/annotations-1grak | speaker, watch | ~56 images, small |

Prefer exports without heavy augmentation. Image counts are from the listing
pages, not verified.

### 7.4 Train v3

Start from v2 so the 11 known classes keep what they learned. Ultralytics
reinitializes only the class head for the new class count.

```powershell
.venv\Scripts\yolo detect train data=datasets/scavscrap/data.yaml model=weights/scavscrap_v2_best.pt epochs=50 patience=10 imgsz=640 batch=32 workers=8 device=0 name=scavscrap_v3
```

Time estimate (not measured on a 4070 Ti; scaled from v2's 2-3 min/epoch for
21k images on a 4070 Super, which is about the same speed): with ~28-32k images,
~3-4 min/epoch, **~2.5-3.5 h** for 50 epochs, less if `patience` stops it early.
yolo11s (`model=yolo11s.pt batch=16`) is more accurate, ~5-8 h.

### 7.5 After training

1. Per-class check:
   `.venv\Scripts\yolo detect val data=datasets/scavscrap/data.yaml model=runs/detect/scavscrap_v3/weights/best.pt device=0`
   Write mAP50 overall and for headphones/speaker/watch into this file.
2. `copy runs\detect\scavscrap_v3\weights\best.pt weights\scavscrap_v3_best.pt`
   then `git add -f weights/scavscrap_v3_best.pt`.
3. Point the live app at v3: copy `recognition/scavscrap_v2_model.json` to
   `recognition/scavscrap_v3_model.json`, set `weights_filename` to
   `scavscrap_v3_best.pt`, append `"headphones", "speaker", "watch"` to
   `expected_builtin_classes`, update `model_identifier`. Change the two
   defaults in `recognition/live_runner.py` `main()` (`--weights`, `--config`)
   to v3. Run the live runner tests.
4. Live check: run the live app (section 6) and hold up headphones, earbuds,
   a smartwatch and a Bluetooth speaker. Each should get a yellow box within
   ~0.2 s labelled with its new class, then a green Gemini name. Note any that
   never get a box.
5. Commit and push to `gursimar/yolo26-training`.

### 7.6 Later, if non-tech items keep getting boxes

The detector has never been shown "nothing here", so phone-shaped objects
(toothpaste, a fork) become `phone`. YOLO learns this from background images:
photos with an empty label file. `build_dataset.py` currently skips images with
no boxes. Adding ~5-10% background images (e.g. Open Images photos of kitchen,
bathroom and desk objects with none of our classes) would cut these false boxes.
Gemini already hides them, so this only matters if the yellow boxes annoy.

## 8. Gotchas

- Before extracting any downloaded zip, list it and check that no entry starts
  with `/` or contains `..`. `build_dataset.py roboflow` asserts that every
  mapped class name exists in the export's `data.yaml`.
- Category names are matched exactly and the script asserts they exist, so a
  typo fails loudly instead of silently dropping a class.
- FiftyOne's usage tracking is disabled in the script (`FIFTYONE_DO_NOT_TRACK`).
  Ultralytics' is disabled via `yolo settings sync=False`.
- Licensing: Objects365 is listed as non-commercial (research or hackathon only).
  Open Images images are listed CC BY 2.0 but not guaranteed per image. Roboflow
  sets used are CC BY 4.0 (credit required if published). The images contain
  real people: train on them, don't redistribute them.
- API keys (Roboflow, Hugging Face, Gemini) go in environment variables, never
  in the repo or the chat.
