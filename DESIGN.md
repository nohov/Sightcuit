# Electronics Pokédex — recognition experiment design, v0.6

The future product helps engineering students learn about electronics. The
current milestone does not build that product. It determines, with recorded
evidence, whether a pretrained object detector is useful for five device classes.

## Sequence

```text
pretrained detector evaluation
→ evidence-based model decision
→ live-capture prototypes (laptop webcam, Meta glasses relay)
→ application integration later
```

No application may present a device as visually identified until a pixel-based
model has run and its result satisfies an accepted mapping policy.

## Fixed target contract

1. `laptop`
2. `phone`
3. `headphones`
4. `smartwatch`
5. `speaker`

Exact manufacturer, model, internal parts, material content, value, instance
masks, and multi-device tracking are outside this milestone.

## Baseline

The first proposed baseline is Ultralytics YOLO26n Detect with COCO-pretrained
weights. It is an object detector: each output is a class, confidence, and
bounding box. A box is not a mask, and an absent class is unsupported rather
than an implicit negative classifier for that project class.

The frozen COCO list contains the exact raw classes `laptop` and `cell phone`.
It does not contain the project classes `headphones`, `smartwatch`, or
`speaker`. It contains `clock`, which is not mapped to `smartwatch`. Therefore
the initial support table is:

| Project class | YOLO26n COCO support | Mapping |
| --- | --- | --- |
| `laptop` | Exact built-in class | `laptop` → `laptop` |
| `phone` | Exact built-in class | `cell phone` → `phone` |
| `headphones` | Unsupported | none |
| `smartwatch` | Unsupported | none; `clock` explicitly rejected |
| `speaker` | Unsupported | none |

This limited coverage is an experiment result about the label space, not a
reason to invent mappings. Later evidence may justify evaluating a different
pretrained detector, such as an LVIS- or open-vocabulary model, in a separately
frozen run.

## Reproducibility contract

Each image record preserves:

- image ID, task, model and local weights filename;
- SHA-256 of the exact weights;
- runtime name/version, device, and hardware platform;
- executed command and confidence/IoU thresholds;
- elapsed time and explicit error;
- original image dimensions;
- raw Ultralytics summary rows;
- original model class ID/name, confidence, and `xyxy` pixel box;
- explicit project mapping or `unsupported` status.

The runner must receive an existing local weights file. It verifies the embedded
class list before inference and refuses a mismatch. Manifest ground truth and
provenance are never passed to the model. Filenames provide file locations only
and never determine predictions.

## Evaluation inputs

Use 10–20 permitted photos per target class and 20–30 confusing or unsupported
examples only after collection is approved. Include multiple physical devices,
viewpoints, lighting, distances, occlusions, clutter, and empty scenes. Group
related images by physical device and session.

Detection scoring requires reviewed ground-truth boxes. The existing whole-image
classification scorer is retained only for the separate VLM comparison and must
not be used to claim YOLO localization quality.

## Comparison, not default

Qwen3-VL through Ollama remains a proposed whole-image classifier. It may produce
one family outcome but not object boxes. It was not executed, and it cannot be
reported as detection or segmentation.

## Gemini vs YOLO bake-off

The owner approved a detection bake-off on one reviewed, box-annotated test set.

The **primary candidate** is whole-image Gemini 3.5 Flash-Lite: one call per
image returns labelled boxes for the five classes. In unscored smoke tests on
15 photos of the previous class list it found all 21 target devices.

The **fallback candidate** is the cascade: local YOLO-World proposes boxes at a
low confidence threshold with class-agnostic NMS, then one Gemini call per image
labels every proposal as one of the five classes or `none`. Images with no
proposals make no API call, which matters for a later live-camera mode, but
recall is bounded by YOLO's proposals: on the previous class list YOLO-World
missed two of three projectors at any usable threshold.

Gemini 3.8 Flash is kept for comparison only. On the free tier it is limited
to 20 requests per day and returned timeouts and HTTP 503 errors in smoke tests,
so a full run needs billing enabled.

| Run | Runner | Config |
| --- | --- | --- |
| **Gemini 3.5 Flash-Lite (primary)** | `recognition/gemini_runner.py` | default `--model gemini-3.5-flash-lite`, `prompt-gemini-v2.txt` |
| Cascade (fallback) | `recognition/cascade_runner.py` | `yolo_world_l_model.json` proposals, `--model gemini-3.5-flash-lite`, `prompt-cascade-v2.txt` |
| Gemini 3.8 Flash | `recognition/gemini_runner.py` | `--model gemini-3.8-flash`, same prompt |
| YOLO-World S / L / X | `recognition/yolo_runner.py` | `yolo_world_model.json`, `yolo_world_l_model.json`, `yolo_world_x_model.json` (same 5 prompts) |
| YOLO26n COCO | `recognition/yolo_runner.py` | `yolo_model.json` (baseline, laptop and phone only) |

`evaluation/score_detection.py` scores every run with the same greedy IoU ≥ 0.5
matching. The decision rule is frozen in `evaluation/bakeoff_report_template.md`
before any run.

## Live mode (prototype, not evaluated)

`recognition/live_runner.py` runs the cascade on a live feed. It is a prototype
for the later live-camera product, not a bake-off run, and has no accuracy
claim.

- Each frame: YOLO-World (`yolo_world_l_model.json`, proposal confidence 0.1,
  at most 20 proposals) proposes boxes.
- A greedy IoU tracker (IoU ≥ 0.3) matches boxes to in-memory tracks; a track
  is dropped after 15 missed frames. Ultralytics ByteTrack was not used because
  it needs the uninstalled `lap` package.
- Gemini is called only for tracks without a cached label, at most once every
  `--min-call-interval` seconds (default 2.0). Each JSONL record says whether a
  label came from `gemini` or `track_cache`, so a cached label is never shown
  as fresh inference.
- A new box is suppressed, and recorded as suppressed, when its IoU with a box
  already matched this frame is ≥ 0.6 or at least 80% of it lies inside that
  box. This stops part-of-device boxes (a laptop screen, a corner) from
  becoming new tracks and stealing a device's label. Trade-off: a small device
  fully inside a bigger one's box (a phone lying on a laptop) gets no track of
  its own.
- A `keyboard` or `monitor` box at least 80% inside any live laptop track,
  including one missed for a few frames, is suppressed before track matching,
  so a flickering laptop box never detaches the laptop's own keyboard or
  screen.
- A track only continues with a box of the same detector class: on glasses
  frames a phone box overlapping the laptop's otherwise took over its track
  and showed the laptop's cached label.
- Live mode ignores proposals under 32 px on their short side
  (`--min-box-side`), recording them as `too_small_proposals`. On 504×896
  glasses frames such boxes were mostly false `smartwatch` hits that Gemini
  confirmed (5 of 8), against 2 of 216 phone hits.
- With a display, the main thread shows every camera frame while a worker
  thread runs detection on the newest frame only; boxes trail a moving device
  by up to one inference (~3 s on CPU). `--no-display` stays single-threaded.
- `--allow-upload` is required because frames go to Google.

## Meta glasses relay (Developer Mode prototype)

The glasses cannot run the models, so the phone is only a relay:

```text
glasses camera → ScavRelay (iPhone, Meta DAT SDK) → HTTP POST /frame
→ live_runner --listen on the owner's laptop → YOLO-World + Gemini
→ tracks JSON back to the phone overlay
```

- `live_runner --listen HOST:PORT` replaces the local camera with JPEG frames
  POSTed to `/frame`. It requires a per-run random bearer token, caps bodies at
  5 MB, rejects frames that fail to decode, and feeds the unchanged live loop.
  It returns the last finished tracks, so overlays trail by one inference.
- `app/ios/ScavRelay` (SwiftUI, Meta Wearables DAT `MWDATCore`/`MWDATCamera`)
  registers with the Meta AI app, streams the glasses camera (504×896, 7 fps),
  posts frames, and draws returned boxes. Relay and network failures show as a
  red banner, never as detections. The token is stored in the iOS Keychain.
  DAT analytics are opted out. A DEBUG-only mock device plays a permitted local
  clip in the simulator.
- Gemini calls and API keys stay on the laptop. Frames cross the LAN as plain
  HTTP behind the token, so only a trusted home network is acceptable.
- Status: built and launched in the iOS simulator. On physical glasses,
  registration and "no eligible device" errors are still being worked through;
  no glasses frame has been recorded yet.

## UI studies (mockups only)

`design/` holds visual studies, not an application: a `DetectionBox` React
component that places an original `xyxy` box over a frame by percentage without
changing the detection, and "Steel & Steam" steampunk theme previews. Their
boxes and labels are illustrative, not model output.

## Stop conditions

Do not install dependencies, download weights, use paid inference, start cloud
jobs, collect a large dataset, read credentials, or modify global configuration,
except for the owner-approved exceptions in `AGENTS.md` (Gemini calls, the
one YOLO-World install and weights download, and the Developer-Mode iOS relay's
DAT package).
If runtime, local weights, or permitted images are absent, produce the harness,
schemas, frozen mapping, tests, and blockers, then stop at `needs_input`.

## Later application milestone

Only after an evidence-based model decision may a separate application milestone
add photo capture, educational cards, corrections, and saved collections. Its UI
must distinguish model detections, user corrections, unsupported classes, and
failures without presenting guesses as visual recognition.
