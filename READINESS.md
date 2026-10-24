# Pretrained detector readiness

## Ready

- A frozen YOLO11n/COCO class list and five-class support decision exist.
- Only `laptop` has an exact mapping; four targets are explicitly unsupported.
- The standard-library harness requires local weights and refuses automatic
  download by checking the path before importing Ultralytics.
- Raw names, class IDs, scores, boxes, thresholds, weights hash, runtime version,
  hardware, command, timing, and errors have defined output fields.
- Unit tests cover real-style Ultralytics summaries, threshold filtering, invalid
  boxes, filename leakage, class-list consistency, and unsupported mappings.

## Not ready

- `ultralytics` and PyTorch are not installed.
- No local YOLO `.pt` or compatible ONNX weights were found.
- No permitted project test images or reviewed ground-truth boxes exist.
- No real image inference, accuracy measurement, or latency measurement ran.

## Status

`needs_input`

The next inputs are an approved installed YOLO runtime, an existing local
YOLO11n COCO detection checkpoint, and a small permission-documented test set
with reviewed boxes. Supplying those inputs is separate from this correction;
the repository will not download them automatically.
