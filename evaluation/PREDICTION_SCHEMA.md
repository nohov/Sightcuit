# Prediction schemas

## YOLO object detection (primary)

`recognition/prediction.schema.json` defines one JSON Lines record per image. It
preserves raw Ultralytics summary rows and normalized detections with:

- original class ID and name;
- confidence score;
- bounding box as original-image pixel coordinates
  `[left, top, right, bottom]` (`xyxy`);
- exact project mapping or explicit `unsupported` status;
- model, weights SHA-256, runtime, hardware, command, thresholds, timing, and
  errors.

The raw class list and mapping are frozen in `recognition/yolo_model.json`.
Ground-truth manifest fields never enter the runner. Detection scoring is blocked
until reviewed ground-truth boxes and a box-annotation format are supplied.

## Whole-image VLM classification (comparison only)

`recognition/classification_prediction.schema.json` is retained for the separate
Qwen3-VL/Ollama proposal. `evaluation/score.py` accepts that classification
schema. It does not accept or score YOLO boxes, and its metrics must not be
reported as detector localization quality.
