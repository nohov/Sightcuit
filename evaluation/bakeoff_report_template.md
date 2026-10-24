# Gemini vs YOLO detection bake-off report

Status: template. Fill in only from recorded runs; do not edit the decision rule
after seeing results.

## Decision rule (frozen before any run)

1. A run is **disqualified** if any of the five classes has recall < 0.6 at
   IoU ≥ 0.5 (`Disqualified = yes` in the scorer output).
2. Among remaining runs, pick the highest **mean per-class F1**.
3. If mean F1 differs by < 0.05, prefer in order: local and free over cloud,
   lower p95 latency, then the more permissive license for the later app
   (Ultralytics is AGPL-3.0 or Enterprise; Gemini is under Google API terms).
4. If every run is disqualified, record `no model selected` and the
   failing classes. Do not relax the threshold to force a winner.

Each run is compared at its fixed operating point. Gemini has no confidence
scores, so no threshold sweep or mAP is used for any run.

## Run identity

| Run | Model / weights | Config or prompt | Weights SHA-256 or model_version | Date |
| --- | --- | --- | --- | --- |
| Gemini | | `prompt-gemini-v1.txt` | | |
| YOLO-World | `yolov8s-worldv2.pt` | `yolo_world_model.json` | | |
| YOLO11n COCO | `yolo11n.pt` | `yolo_model.json` | | |

- Manifest and checksum:
- Images per class / distractor images:
- Reviewer of ground-truth boxes:

## Results

Paste `python3 -m evaluation.score_detection` output here unchanged.

## Decision

- Selected run:
- Rule step that decided it:
- Gemini cost for the run (from `usage` token counts):
- Known failure patterns seen when viewing boxes:
