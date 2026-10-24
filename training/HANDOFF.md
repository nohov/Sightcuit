# Handoff: YOLO26 electronics detector

For a new Claude Code session continuing this work on a Windows machine with an
NVIDIA RTX 4070 Ti. Read this whole file before acting. Last updated 2026-10-24.

## 1. What the project is

ScavScrap ("Electronics Pokédex") is a hackathon app for engineering students:
photograph tech items, the app finds each one, identifies it, and shows its specs
from cited web sources. The pipeline (see `designspec.txt`, v0.7):

```text
photo → stage 1 detect (YOLO26, trained here, local and fast)
      → stage 2 identify (Gemini: brand + product line, e.g. "Apple MacBook Air")
      → stage 3 specs (Gemini with web search grounding, every spec cites a URL)
```

Exact model/SKU is out of scope: many items in one product line look the same.
The detector only needs coarse categories. Fine distinctions (smartwatch vs
analog watch, Bluetooth vs wired speaker, earbuds vs over-ear) are stage 2's job.

**Your job: stage 1.** Train a YOLO26 detector on tech-item classes.

## 2. Repo state and what is stale

- Work happens on branch `gursimar/yolo26-training` only. Commit and push there.
  Never push to `main`.
- `training/` is the active workspace: `scripts/build_dataset.py`, `README.md`,
  `requirements.txt`, this file. `datasets/`, `weights/`, `runs/`, `*.pt` and
  logs are gitignored on purpose.
- **Stale, do not follow for training work:** `AGENTS.md`, `README.md`,
  `READINESS.md`, `RUNBOOK.md`, `recognition/`, `evaluation/`. They describe an
  earlier milestone (evaluating stock COCO YOLO11 on 5 classes) and forbid
  installing packages, downloading weights and training. The project owner has
  explicitly replaced that: installing, downloading datasets and training inside
  `training/` is the task.
- `designspec.txt` v0.7 still says stage 1 is a cheap hosted VLM (Qwen) and lists
  only 5 classes + `other_electronics`. Both are out of date: stage 1 is now this
  YOLO26 detector and the class list is below. Update the spec when convenient.

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

## 4. Inputs the owner uploads to Google Drive

| File | Put it at | What it is |
|---|---|---|
| `scavscrap.zip` (3.7 GB) | unzip to `training\datasets\scavscrap\` | merged, ready-to-train dataset |
| `scavscrap_v1_best.pt` (5.5 MB) | `training\weights\` | checkpoint after 4 epochs |
| Roboflow zips (~1.2 GB, optional) | `datasets\` at repo root | raw Roboflow exports, needed only to rebuild (section 7) |

`datasets\scavscrap\` must contain `data.yaml`, `train.txt`, `val.txt`,
`images\`, `labels\`. The lists use `./images/...` paths relative to that folder.

## 5. The current dataset (11 classes)

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
  mouse-keyboard-tablet, tablets-wwxv9. Imported with
  `build_dataset.py roboflow <zip> "Their Name=our_class" ...`.

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

## 6. Continue training

From `training\`:

```powershell
.venv\Scripts\yolo detect train data=datasets/scavscrap/data.yaml model=weights/scavscrap_v1_best.pt epochs=50 patience=10 imgsz=640 batch=32 workers=8 device=0 name=scavscrap_v2
```

- v1 history (Apple M4, 13.4k images): mAP50 per epoch 0.40, 0.39, 0.32, 0.38.
  It was stopped at epoch 4 to add data. One epoch took about 21 min on the M4.
  Expect roughly 2–4 min on the 4070 Ti (estimate, not measured).
- Start a new run from a `.pt` file. Do not use `resume=True` with a checkpoint
  from the Mac: it stores absolute macOS paths.
- `runs\detect\<name>\weights\best.pt` updates every epoch, so it is usable
  mid-run. Check per-class results with
  `yolo detect val data=datasets/scavscrap/data.yaml model=runs/detect/<name>/weights/best.pt device=0`.
- Only load `.pt` files we trained or official Ultralytics ones. `.pt` files can
  execute code when loaded.

## 7. Next task: add headphones, speakers, watches (and similar)

The owner wants more item types: headphones, Bluetooth speakers, smartwatches,
"etc." Recommended plan (confirm with the owner before step 3):

1. **Use coarse classes and append them to the end of `CLASSES`** so existing
   IDs 0–10 stay stable: `headphones` (includes earbuds), `speaker` (any
   speaker), `watch` (any wristwatch, including smartwatches). Candidates if the
   owner says "etc." covers them: `camera`, `game_controller`. Stage 2 (Gemini)
   decides Bluetooth vs wired, smart vs analog.
2. **Map them from the big sources.** These exact names were verified in the
   annotation files (two are misspelled upstream):

   | Our class | Open Images | LVIS (`name`) | Objects365 |
   |---|---|---|---|
   | headphones | `Headphones` | `earphone` | `Head Phone`, `earphone` |
   | speaker | none | `speaker_(stero_equipment)` | `Speaker` |
   | watch | `Watch` | `watch` | `Watch` |
   | camera | `Camera` | `camera` | `Camera` |

   Add them to the `OPENIMAGES`, `LVIS` and `O365` dicts, and to
   `LVIS_REQUIRED` and `O365_REQUIRED` so images containing them are pulled.
3. **Rebuild from the sources. Do not just add new images on top.** The existing
   21k images contain headphones, speakers and watches that are unlabeled. If
   they stay unlabeled, the model learns those items are background. The
   annotations exist in Open Images, LVIS and Objects365, but the current zip
   kept only our 11 classes. So rerun the whole build on this machine. It
   re-downloads about 10 GB; see the `training/README.md` "Build" section:
   `selftest`, `openimages`, `lvis`, `objects365`, every `roboflow` import, then
   `split`. Delete `datasets\scavscrap\` first so stale label files can't
   survive.
4. **Top up from Roboflow Universe** with smartwatch, Bluetooth speaker and
   earbuds sets (search universe.roboflow.com). Check each export's class names
   with the zip check in section 8, map them, and prefer exports without heavy
   augmentation.
5. Update `selftest` for any new logic, retrain from `scavscrap_v1_best.pt`
   (the classification head reinitializes for the new class count, which is
   fine), and update `designspec.txt` with the final class list.

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
