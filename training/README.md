# YOLO26 training

Standalone training workspace, separate from the evaluation code in the rest of
the repo. Datasets, weights and runs stay local and are gitignored.

## Setup (once per machine)

```sh
cd training
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
T=$PWD; .venv/bin/yolo settings datasets_dir=$T/datasets weights_dir=$T/weights runs_dir=$T/runs sync=False
```

`yolo settings` writes a per-user file, so run it on each machine. The first
`weights/yolo26n.pt` reference downloads the pretrained checkpoint.

## Build the merged dataset

`scripts/build_dataset.py` pulls tech-item subsets from Open Images V7, LVIS and
Objects365 (val split), maps them to 11 classes and writes
`datasets/scavscrap/data.yaml`. No accounts needed. Raw downloads go to
`datasets/_raw/` (safe to delete after building).

```sh
.venv/bin/python scripts/build_dataset.py selftest
.venv/bin/python scripts/build_dataset.py openimages   # ~12k images via FiftyOne
.venv/bin/python scripts/build_dataset.py lvis         # COCO images, fetched one by one
.venv/bin/python scripts/build_dataset.py objects365   # val patches with towers/projectors
.venv/bin/python scripts/build_dataset.py split        # writes train.txt, val.txt, data.yaml
.venv/bin/yolo detect train data=datasets/scavscrap/data.yaml model=weights/yolo26n.pt \
  epochs=100 imgsz=640 batch=16 device=mps name=scavscrap
```

Objects365's merged `Monitor/TV` boxes are painted gray rather than guessed. LVIS
images where our classes are marked not exhaustively labeled are skipped. Open
Images and LVIS have no desktop-tower class, so towers in those photos are
unlabeled. Objects365 is listed as non-commercial: research and hackathon use only.

Roboflow exports (format "YOLOv8" or "YOLO26") merge in with a class mapping;
unmapped classes are dropped. Then rerun `split`:

```sh
.venv/bin/python scripts/build_dataset.py roboflow "../datasets/Desktop PC.v1i.yolo26.zip" \
  "DESKTOP PC=desktop_computer_tower" "Desktop-PC=desktop_computer_tower" "Monitors=monitor"
```

## Train on another dataset

Put each dataset in YOLO format under `datasets/<name>/` with a `data.yaml`
(Roboflow: export as "YOLOv8"; every Ultralytics model reads that layout).

```sh
.venv/bin/yolo detect train data=datasets/<name>/data.yaml model=weights/yolo26n.pt \
  epochs=100 imgsz=640 batch=16 device=mps name=<run-name>
```

Results land in `runs/detect/<run-name>/`; `weights/best.pt` is the trained model.
Use `yolo26s.pt` for more accuracy at roughly 3x the compute.

## Check a trained model

```sh
.venv/bin/yolo detect val data=datasets/<name>/data.yaml model=runs/detect/<run-name>/weights/best.pt device=mps
.venv/bin/yolo detect predict model=runs/detect/<run-name>/weights/best.pt source=path/to/photo.jpg device=mps
```
