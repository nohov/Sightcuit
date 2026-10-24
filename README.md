# ScavScrap

ScavScrap is the recognition groundwork for an engineering-learning app that
identifies everyday electronics. Before any app ships, this repository answers
one question with recorded evidence: **which pretrained detector reliably finds
these five devices in real photos?**

| Class | Definition (canonical text in [`labels/classes.json`](labels/classes.json)) |
| --- | --- |
| `laptop` | Portable computer with a permanently attached hinged keyboard base |
| `phone` | Handheld mobile phone; not a tablet or landline handset |
| `headphones` | Over- or on-ear headphones with a headband; not earbuds |
| `smartwatch` | Wrist-worn watch with a digital touch display; not a clock |
| `speaker` | Standalone loudspeaker enclosure; not one built into another device |

No model is trained or fine-tuned here. Predictions come only from image pixels:
filenames, folders and ground truth never reach a model.

## Status

| Piece | State |
| --- | --- |
| Detection harness, scorer, tests | Done. 51 unit tests, all mocked; none is model inference |
| Live camera and Meta glasses relay | Ran end to end on real hardware (2026-10-24) |
| Five-class prompts and configs | Migrated to the class list above; **not yet run on real images** |
| Scored bake-off | **Blocked.** It needs permitted photos with reviewed ground-truth boxes |

No accuracy claim can be made until the bake-off is scored.

## Candidates in the bake-off

| Run | How it works | Classes covered |
| --- | --- | --- |
| **Gemini 3.5 Flash-Lite** (primary) | One API call per image returns labelled boxes | All five |
| **Cascade** (fallback) | Local YOLO-World proposes boxes, then one Gemini call labels them | All five; recall is capped by YOLO's proposals |
| YOLO-World S / L / X | Local open-vocabulary detector with five text prompts | All five |
| YOLO26n COCO | Local baseline | `laptop` and `phone` (from COCO `cell phone`) only |

Every run is scored with the same greedy IoU ≥ 0.5 matching. The winner is
picked by the decision rule frozen in
[`evaluation/bakeoff_report_template.md`](evaluation/bakeoff_report_template.md).

## Repository layout

```text
labels/         class contract (classes.json) and box-labelling guide
recognition/    runners, frozen model configs, prompts, output schemas
evaluation/     manifest template, collection rules, scorers, report templates
app/ios/        ScavRelay: Meta glasses → laptop frame relay (Developer Mode only)
frontend/       dashboard that renders live detections (placeholder device data)
tests/          cross-module contract tests
```

| Document | Read it for |
| --- | --- |
| [`DESIGN.md`](DESIGN.md) | Experiment design, support table, stop conditions |
| [`RUNBOOK.md`](RUNBOOK.md) | Exact commands for every run, scoring and checks |
| [`AGENTS.md`](AGENTS.md) | Rules for anyone (human or agent) changing this repo |
| [`evaluation/COLLECTION.md`](evaluation/COLLECTION.md) | How to collect and annotate test photos |
| [`app/ios/README.md`](app/ios/README.md) | Glasses relay setup |

## Quickstart

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync                        # Ultralytics + CLIP, pinned in uv.lock
source .venv/bin/activate
python -m unittest             # 51 tests, no network, no weights
python -m recognition.yolo_runner --help
```

Real runs need local weights and, for Gemini, `GEMINI_API_KEY` in the
environment. See [`RUNBOOK.md`](RUNBOOK.md).

## What every run guarantees

- **Local weights only.** Runners refuse a missing weights path rather than let
  Ultralytics download one, and they check the file's embedded class list
  against the frozen config before inference.
- **Honest mappings.** A raw class maps to a project class only when the config
  declares an exact match. COCO `clock` is not `smartwatch`. An unmapped class
  is recorded as `unsupported`, never as a hit.
- **Honest outputs.** Detectors produce boxes, not masks. Gemini returns no
  calibrated confidence, so its records store `null`.
- **Full provenance.** Each JSONL record keeps the raw model output, original
  class IDs and names, `xyxy` pixel boxes, weights SHA-256, runtime version,
  command, thresholds, timing and errors. Output files are written atomically.
- **Upload consent.** Gemini runs send images to Google. Only images whose
  provenance notes permit that may be used, and live mode requires
  `--allow-upload`.

## Licensing note

Ultralytics models and code are AGPL-3.0 or Enterprise licensed; Gemini is used
under Google's API terms. A license review is needed before product integration.
