# YOLO object-detection baseline report

Status: **needs_input**. No real image inference ran.

## Baseline decision

The first frozen candidate is Ultralytics YOLO11n Detect with COCO-pretrained
`yolo11n.pt` weights. This is a proposed local baseline, not an accuracy result.
Ultralytics documents YOLO11 as a mature alternative and its detection checkpoint
as COCO-pretrained. Predict mode returns object boxes, original class IDs/names,
and confidence values.

The official 80-class COCO configuration was inspected and copied in order into
`yolo_model.json`. Evidence-backed project support is:

| Project class | Status | Evidence and decision |
| --- | --- | --- |
| `laptop` | `supported_exact` | COCO class 63 is `laptop`; map exactly |
| `desktop_computer_tower` | `unsupported` | no matching COCO class |
| `monitor` | `unsupported` | no `monitor` class; COCO `tv` is rejected |
| `printer` | `unsupported` | no matching COCO class |
| `projector` | `unsupported` | no matching COCO class |

This means YOLO11n/COCO cannot evaluate four of the five target classes as
positive detector categories. Detecting `tv` does not count as detecting a
monitor. A later model comparison may evaluate an LVIS or open-vocabulary
detector, but it must use its own frozen class list and mappings.

## Harness

`yolo_runner.py` uses only the Python standard library until it has confirmed
that the supplied weights path exists. This prevents the Ultralytics convenience
behavior that downloads a symbolic model name. When an approved local runtime
and weights exist, it:

1. loads the local detection checkpoint;
2. compares its embedded class list with the frozen 80-class list;
3. sends each manifest image path to `model.predict`, which decodes image pixels;
4. parses `Results.summary(normalize=False)` rows;
5. rejects invalid IDs, class names, scores, and boxes;
6. writes one atomic JSONL record per image.

Every record preserves raw summary rows and normalized detections with original
class ID/name, confidence, and `[x1, y1, x2, y2]` pixel boxes. It also records the
weights SHA-256, runtime version, device, hardware platform, executed command,
confidence/IoU thresholds, elapsed time, original image size, and explicit error.

The harness reads only `image_id` and `path` from the manifest. Expected outcome,
device grouping, source, and permission fields do not enter inference. A focused
test uses a file named `definitely-a-laptop.jpg` with a raw `tv` detection and
confirms that the result remains unsupported rather than becoming a laptop.

## Local inspection

Inspected on 2026-10-23:

- hardware: Apple M4 MacBook Pro, 16 GB memory;
- Python: 3.14.3 on arm64 macOS;
- `ultralytics`: not installed;
- PyTorch and torchvision: not installed;
- ONNX Runtime: 1.24.4 installed;
- local YOLO `.pt`, `.onnx`, `.engine`, or `.mlmodel` weights: none found in the
  project or standard inspected model caches;
- permitted project images: none found.

ONNX Runtime alone is insufficient because no compatible model weights are
present. No dependency was installed and no weight or image was downloaded.

## Exact future command

After the missing inputs are supplied separately:

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

## Separate VLM comparison

`vlm_runner.py`, `prompt-v1.txt`, `model_response.schema.json`, and
`classification_prediction.schema.json` retain the Qwen3-VL/Ollama proposal. It
is whole-image classification, not object detection or segmentation. It is not
the default, and it was not executed because Ollama, weights, and images are
absent. Its mocked transport tests establish request/response handling only.

## License constraint

Ultralytics publishes AGPL-3.0 and Enterprise licensing options. The educational
evaluation may proceed only under an applicable license; later product
integration needs an explicit license review rather than assuming commercial
permission.

## Checks

The completion contract lists the exact commands run after this report was
written. Passing parser tests does not establish model accuracy or prove that
the absent runtime/weights work on this machine.

## Primary sources

- YOLO11 model documentation: https://docs.ultralytics.com/models/yolo11/
- Ultralytics prediction API and result fields: https://docs.ultralytics.com/modes/predict/
- Ultralytics detection task definition: https://docs.ultralytics.com/tasks/detect/
- Official COCO class configuration: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
- Ultralytics licensing summary: https://docs.ultralytics.com/
