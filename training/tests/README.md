# Automatic tests for the trained detector

`test_trained_model.py` checks that `runs/detect/scavscrap_v2/weights/best.pt`
is a healthy 11-class detector. It is plain `unittest` (no pytest needed) and
runs with the training venv, which already has Ultralytics + the CUDA torch
build. No new dependencies.

## What it checks

| Test | What it proves | Speed |
|---|---|---|
| `test_model_loads_as_detector` | weights load, task is `detect` | fast |
| `test_class_names_match_frozen_contract` | class ids 0–10 are the exact frozen list, in order (stage 2 depends on this) | fast |
| `test_class_names_match_dataset_yaml` | model classes match `datasets/scavscrap/data.yaml` | fast |
| `test_inference_on_val_samples_is_well_formed` | runs 5 real val images; every box is inside the image, conf ∈ [0,1], class id in range | ~1s |
| `test_val_metrics_meet_thresholds` | full `model.val()`: overall mAP50 ≥ 0.60, mAP50-95 ≥ 0.45, and no class drops below AP50 0.05 | ~25s (GPU) |

Gates sit below the measured `scavscrap_v2` result (mAP50 **0.684**, mAP50-95
**0.505**; weakest class router AP50 0.166) and well above the v1 baseline
(~0.40), so a healthy model passes and a real regression fails. The val gate
**skips itself** (does not fail) if the dataset is not present, so the file is
safe to run on a machine that only has the weights.

## Run it

From the `training` directory, with the venv:

```powershell
# Windows (PowerShell). Note the leading .\ — PowerShell won't launch a
# relative-path exe without it (otherwise: CouldNotAutoLoadModule).
cd "C:\Users\Noah Hova\Documents\scavscrap-\training"

# whole suite
.\.venv\Scripts\python -m unittest discover -s tests -v

# just the fast checks (skip the ~25s GPU val gate)
$env:SCAVSCRAP_SKIP_VAL="1"; .\.venv\Scripts\python -m unittest discover -s tests -v
Remove-Item Env:\SCAVSCRAP_SKIP_VAL

# run on CPU instead of GPU 0
$env:SCAVSCRAP_DEVICE="cpu"; .\.venv\Scripts\python -m unittest discover -s tests -v
Remove-Item Env:\SCAVSCRAP_DEVICE
```

```sh
# macOS/Linux
.venv/bin/python -m unittest discover -s tests -v
```

## Overrides (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SCAVSCRAP_MODEL` | `runs/detect/scavscrap_v2/weights/best.pt` | test a different run's `best.pt` |
| `SCAVSCRAP_DATA` | `datasets/scavscrap/data.yaml` | point at another dataset |
| `SCAVSCRAP_DEVICE` | `0` | `cpu` or another GPU index |
| `SCAVSCRAP_MAP50_MIN` | `0.60` | raise after a better run to lock in gains |
| `SCAVSCRAP_MAP5095_MIN` | `0.45` | overall mAP50-95 floor |
| `SCAVSCRAP_CLASS_AP50_MIN` | `0.05` | per-class "not dead" floor |
| `SCAVSCRAP_SMOKE_IMAGES` | `5` | how many val images the smoke test uses |
| `SCAVSCRAP_SKIP_VAL` | *(unset)* | set to `1` to skip the slow val gate |

Relative `SCAVSCRAP_MODEL` / `SCAVSCRAP_DATA` paths resolve against `training/`.
Only ever point `SCAVSCRAP_MODEL` at weights we trained — `.pt` files can run
code when loaded.

## Prompts to run or extend these (paste into Claude Code)

- **Run the gate:** "Run the trained-model tests in `training/tests` with the
  venv and report overall + per-class mAP."
- **After a new run:** "I just finished training run `<name>`. Run
  `training/tests` against `runs/detect/<name>/weights/best.pt` by setting
  `SCAVSCRAP_MODEL`, and if it beats the current gates, raise
  `SCAVSCRAP_MAP50_MIN` / `SCAVSCRAP_MAP5095_MIN` defaults to the new numbers."
- **Add classes (headphones/speaker/watch per HANDOFF §7):** "We added classes
  to the detector. Update `EXPECTED_CLASSES` in `tests/test_trained_model.py` to
  the new frozen list and rerun the suite."
- **CPU-only machine:** "Run `training/tests` on CPU (`SCAVSCRAP_DEVICE=cpu`);
  the val gate will be slow, so run the fast checks first with
  `SCAVSCRAP_SKIP_VAL=1`."
