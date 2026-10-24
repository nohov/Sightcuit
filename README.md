# ScavScrap pretrained recognition evaluation

ScavScrap is evaluating whether an existing object detector can locate five
electronics families for a later engineering-learning application:

- `laptop`
- `desktop_computer_tower`
- `monitor`
- `printer`
- `projector`

The milestone order is:

```text
pretrained detector evaluation
→ evidence-based model decision
→ application integration later
```

There is no recognition web app in this milestone. The removed prototype matched
filenames and did not inspect pixels; it was not computer vision.

## YOLO baseline

The frozen baseline is a proposed local Ultralytics YOLO11n detection checkpoint
pretrained on COCO. The exact COCO class list contains `laptop`; it does not
contain `desktop_computer_tower`, `monitor`, `printer`, or `projector`. COCO's
`tv` class is deliberately not mapped to `monitor`.

`recognition/yolo_runner.py`:

- requires an existing local weights path, preventing automatic downloads;
- verifies the weights' embedded class list against `recognition/yolo_model.json`;
- reads image pixels through the YOLO runtime;
- records raw detections, original names, scores, `xyxy` pixel boxes, thresholds,
  runtime version, weights SHA-256, device, command, elapsed time, and errors;
- never reads expected labels when producing predictions.

## Current blocker

No real inference ran. The inspected environment has no Ultralytics or PyTorch
runtime, no local YOLO weights, and no project test images. ONNX Runtime is
installed, but no compatible ONNX weights are present. The experiment status is
therefore `needs_input`, not complete.

After the owner separately supplies an approved runtime, an existing local
`yolo11n.pt`, and permitted images in the manifest, the exact run shape is:

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

Do not use the symbolic weights name in place of an existing path: Ultralytics
can otherwise download missing weights automatically.

## Checks

```sh
python3 -m unittest recognition.tests.test_yolo_runner -v
python3 -m unittest recognition.tests.test_vlm_runner -v
python3 -m unittest evaluation.tests.test_score -v
python3 -m unittest tests.test_integration -v
python3 -m py_compile recognition/yolo_runner.py recognition/vlm_runner.py evaluation/score.py
python3 recognition/yolo_runner.py --help
```

The Qwen3-VL/Ollama files remain only as an unexecuted whole-image classification
comparison. They do not produce boxes and are not the default baseline.

See `recognition/report.md`, `READINESS.md`, and `RUNBOOK.md` for evidence,
blockers, and collection/run instructions.
