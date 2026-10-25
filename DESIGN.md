# ScavScrap — guided circuit building, v0.12

## Purpose and audience

Help someone with no basic electronics knowledge build their first working
breadboard circuit without needing a teacher beside them. First-year engineering
students are also an audience, but instructions must not assume they recognize
a resistor, LED, or breadboard. Explain names, purposes, and actions in plain
language. Making electronics education more accessible is the product motivation.

This is the intended product specification, not a claim of implemented
capabilities. Existing five-device recognition results do not establish
component recognition, hand association, or circuit verification performance.

## Confirmed direction

- The first demonstration is a simple LED circuit, built by a person who has
  never made a circuit before.
- An LLM prepares the project plan before assembly, citing existing beginner
  projects that have actually been built. Live assembly follows that plan.
- Parts may be ordered online or already owned. The expected parts and tools
  are established before the build, rather than discovered through improvisation.
- The demonstration inventory is seven physical pieces across six item types,
  laid out clearly on a table; the external USB power source is additional.
- The user wears Ray-Ban glasses and looks at a PC for diagrams and context.
- The initial vision task checks whether the visible parts match the planned
  inventory. The user can ask what an object is, including what is in their
  right hand.
- Spoken output already works through the finished iOS relay (see “Built so
  far”). ElevenLabs is intended for the lesson voice; the division between
  speech output and conversation handling remains open.
- Assembly is breadboard-only, with no coding, soldering, or additional sensors.
  Multimeters are deferred. The Arduino supplies power through its 5V/GND pins.
- Voice commands are the primary way to advance steps. Progression is
  user-directed; automatic assembly verification remains undecided. PC controls
  are a proposed fallback.

## First demo: USB-powered red LED

Owner-specified inventory, physically confirmed by the team on 2026-10-24:

| Component | Quantity | Inventory source |
| --- | --- | --- |
| Arduino UNO R3 | 1 | CEWITs or INTERNAL |
| Breadboard | 1 | CEWITs or INTERNAL |
| Red LED | 1 | CEWIT LED kit |
| 330Ω resistor | 1 | CEWIT resistor collection |
| Male-to-male jumper wires | 2 | CEWIT jumper box |
| USB cable compatible with Arduino UNO | 1 | Availability must be confirmed |

Total: **seven physical pieces, six item types**, counting the two jumper wires
separately. A computer or USB power adapter is required in addition to this
inventory. The recognition scope must explicitly decide whether the USB cable
is checked visually or confirmed during setup; do not silently drop it.

The specified series connection is:

```text
Arduino 5V → 330Ω resistor → red LED anode (+)
red LED cathode (−) → Arduino GND
```

Use the two jumper wires for the Arduino-to-breadboard 5V and GND connections;
the resistor and LED share the appropriate breadboard nodes. Exact hole
coordinates and the breadboard diagram are drawn for the confirmed breadboard
(owner: Noah, see “Team and workstreams”).
Assemble with USB disconnected, then follow the finalized connection review and
power-up procedure. No digital I/O pin, sketch upload, or software-controlled
switch is part of this circuit.

Expected behavior: the external red LED remains lit while USB powers the
correctly assembled circuit. Removing USB power turns it off. Success requires
observing the external breadboard LED, not an onboard Arduino indicator.

The official UNO R3 uses USB-B at the board. Select the other cable end for the
chosen computer or adapter and confirm the actual board connector before the
demo. Arduino documents USB power and the board's 5V/GND connections in its
[power guide](https://support.arduino.cc/hc/en-us/articles/360018922259-What-power-supply-can-I-use-with-my-Arduino-board),
[USB connector guide](https://support.arduino.cc/hc/en-us/articles/4733418441116-Upload-a-sketch-in-Arduino-IDE),
and [UNO R3 pinout](https://content.arduino.cc/assets/Pinout-UNOrev3_latest.pdf).
These references establish board details; they are not a cited completed
beginner project or evidence that this particular build has been tested.

## Project preparation

Before the session, the LLM assembles a versioned project package containing:

- Source project titles and URLs, with the steps or circuit details they support.
- Intended behavior and a beginner-friendly explanation.
- Required parts, quantities, required values or ratings, and tools.
- A circuit schematic and breadboard placement diagram for the selected board.
- Ordered assembly instructions, the parts needed for each step, and why each
  connection is made.
- The selected power arrangement, connection procedure, and expected final test.
- Any substitutions or departures from the cited project, explicitly identified.

Citing a working project is not itself validation of the LLM's adaptation.
Sources must be checked for the actual selected parts and supply; the project
review process and responsible reviewer are still undecided. Do not describe
an unreviewed generated plan as reviewed. The owner has specified the circuit
and nominal resistor value, and the team has confirmed the inventory and steps.
Record the confirmed LED specifications, resistor rating, and USB cable in the
project package.

## Build experience

1. Introduce the goal and explain the breadboard and components from first
   principles, using the user's actual planned parts.
2. Ask the user to lay out the expected items. Show which required items have
   visual support, which are missing from view, and which are unresolved.
   An item missing from the image is not necessarily absent from the workspace.
3. Present one prepared assembly step, its required part or parts, placement
   diagram, and short explanation.
4. Answer identification questions with the current glasses image as evidence.
   Keep the object being held distinct from the part needed for the step.
5. Let the user advance with a voice command such as “next step.” Record this
   as user-reported completion, not machine-verified wiring. Allow back/repeat.
6. Follow the finalized project's power and test procedure, then record the
   observed result and any assistance needed.

### Highlighting the needed part

Assume the user cannot recognize any part. For each step, the glasses view on
the PC highlights where the required part is, so they can find it by position
rather than by name. The demo does not use a glasses display, so the highlight
lives on the PC, and speech points there (“the part is highlighted on screen, on the
left side of the table”).

- Boxes must follow the part from frame to frame, so a fast local detector
  places them; Gemini confirms identity asynchronously. Gemini latency alone
  cannot keep a highlight on a moving view.
- Highlight only parts the current frame supports. Never highlight an object
  because it is the last unmatched item.
- When several items share the required category (the two jumper wires),
  highlight all of them and say either one will do; do not invent a distinction.
- If the required part is not detected, say so and ask the user to look across
  the table, rather than showing a stale or guessed box.
- Highlight the required part even while the user holds something else; the
  held-object panel stays separate. When the user picks up the right part,
  confirm it from the held-object answer.

The final success criterion is a novice completing this circuit and observing
the external red LED remain lit while powered. Record any assistance required.
Turning off by removing USB is the expected shutdown, not a separate switching
feature. The earlier ambiguous “turns off” criterion is superseded.

## Built so far

Repository scan on 2026-10-24 (`main` at `e4604acf`). Everything here was built
for the five-device scan; it is reusable plumbing, not component support.

| Piece | State | Reuse for the LED build |
| --- | --- | --- |
| iOS relay (`app/ios/ScavRelay/`) | **Finished.** DAT 1.0.1 camera stream to the laptop, boxes drawn on the phone, failure banner, mock glasses for the simulator. Ran on a physical iPhone 15 Plus with the glasses on 2026-10-24. | Use as-is for frames. |
| Glasses audio out | Built in the relay: capture-button press (MWDATInputs, beta) or tap-to-pause speaks queued texts with `AVSpeechSynthesizer`, routed to the glasses over Bluetooth; another press stops speech. | Speak step instructions and answers through the same path. |
| Laptop relay (`recognition/live_runner.py --listen`) | `POST /frame` (bearer token), `GET /stream.mjpg`, `GET /events` (SSE tracks); YOLO proposals, Gemini labels, tracking, JSONL records, optional OpenCV window. | Host for session state and new event types. |
| Detectors | `scavscrap_v2_best.pt` (fine-tuned YOLO11n, 11 tech-device classes) and YOLO-World configs; v3 checkpoint on `gursimar/yolo26-training`. None has a component class. | Baseline only; component classes are unsupported. |
| Gemini paths | `gemini_runner`, `cascade_runner`, live labelling with versioned prompts and schemas; confidence null. | Migrate prompts and schemas to the component catalog. |
| Narrator (`recognition/narrator.py`) | Gemini text description per label (text only, no image), cached; optional ElevenLabs WAV played on the laptop. | Pattern for component explanations. |
| Dashboard (`frontend/`) | Live MJPEG + SSE feed, boxes, rotating device model, measurements, description, metal assay; inventory drawer on `gurashish/inventory` (not merged). | Feed wiring and box overlay; device panels are replaced. |
| Evaluation (`evaluation/`) | Manifest, prediction schema, detection and classification scoring with tests. | Score component identification. |

Not built: microphone input, transcription, voice-command intents, session
and step state, project packages, component classes, and any component images.

## PC interface

The dashboard focuses on the most confident labelled track, not a detected
right-hand object. Adapt that dashboard concept into a step-focused workspace:

| Display | Intended content |
| --- | --- |
| Glasses view | Current camera image and supported component observations |
| Current step | Plain-language action, explanation, progress, and navigation |
| Required parts | The component or components needed now, regardless of what is held |
| Held or queried object | Supported identity, useful explanation, or unresolved state |
| Assembly diagram | Breadboard layout with the current placement highlighted |
| Circuit reference | Overall circuit and relevant connections for context |

The held-object panel must not replace the required-parts panel. Measurements
and metal assay are not requirements for this experience. Exact panel layout,
visual emphasis, and navigation hardware remain design decisions. This spec
update does not modify frontend code.

## Recognition and evidence boundaries

A small, known inventory narrows the task but does not guarantee visibility or
right-hand association. Treat both as capabilities to evaluate, not assumptions.
A known inventory supplies expectations; image pixels must supply recognition.
Do not assign an unseen object a label solely because it is the remaining item.

Distinguish component category from exact value, polarity, or part identity.
Keep visible evidence, project expectations, and user confirmation separate.
If the image cannot support an answer, report uncertainty; whether to request
a close-up, ask the user to reposition the part, or use another fallback is open.

Preserve image references, predicted labels, boxes, raw model output, and
request failures. Boxes are not masks or verified connections. Gemini confidence
remains null. Parsing or provider errors must not become successful inventory
checks. A Next command records progression, not electrical verification.

### Detector plan

Gemini alone is too slow (10–30 s per label) to keep a highlight on a part while
the view moves, so the build needs a fast local detector for boxes and Gemini
for identity details such as color, value, and connector type.

1. Baseline: run the existing YOLO-World proposals and Gemini labels on about
   20 permitted glasses photos of the parts and record per-class results.
2. Capture training photos with a phone, held at eye level and pointed down
   at the table as the wearer's head would be, 1× lens, no portrait mode.
   Collect about 150 over several sessions: laid out, held in the right hand,
   partly occluded, partly assembled, and under varied light and surfaces.
3. Test on glasses frames only: save 20–30 relayed frames with
   `live_runner.py --listen ... --save-frames DIR` (capture only, no detection
   or upload). Phone photos are sharper and differently framed, so a phone-only
   test set would overstate live performance. The evaluation owner freezes
   these before training.
4. Label: one box per physical piece, using the catalog classifications
   `development_board`, `breadboard`, `led`, `resistor`, `wire`, `cable`.
   Each jumper wire gets its own box.
5. Fine-tune: start from COCO-pretrained YOLO in the existing `training/`
   workspace; try `imgsz=1280` if the LED and resistor are missed at 640.
6. Integrate: a new model config beside `recognition/scavscrap_v2_model.json`,
   landing together with the class, prompt, schema, and test migration.

A detector trained on this one inventory and table is a demo model. Do not
claim general component recognition from it. Jumper wires (thin, often
occluded) and right-hand association are the expected weak points.

Power architecture is resolved: USB source → UNO USB connector → 5V/GND
headers → breadboard circuit. The particular computer or USB adapter and cable
availability remain open. Direct mains wiring is outside the demonstration.

## Evaluation

Evaluate real, permitted glasses images of the selected parts for component
identification, initial inventory matching, and held-object questions. Include
occlusion and ambiguous views even with the small inventory. Report errors,
abstentions, failures, latency, and cost; do not infer accuracy from scene size.
Score highlighting per frame: whether the box for the step's required part lands
on the correct physical piece, and how often it is missing. Freeze the test
sessions, answer key, and pass criteria before any trained model is scored.

Run the complete prepared tutorial with a novice and record completion,
interventions, confusing instructions, and the final circuit behavior. Choose
participant count and acceptance thresholds before claiming success. If automatic
assembly checking is later included, evaluate it separately on correct and
incorrect placements. Mocked software tests do not establish vision performance.

## Open decisions — circle-back list

| Decision | Current position | Needed to resolve |
| --- | --- | --- |
| Physical parts and layout — resolved | Inventory and steps confirmed 2026-10-24 | Record part specifications in the project package; cable is a detector class (`cable`) |
| Power arrangement — partly resolved | USB powers UNO; circuit uses 5V/GND | Choose computer or USB adapter, confirm matching cable and finalize power-up procedure |
| Step completion/checking — explicitly circle back | Voice advances the lesson; no automatic verification promised | Whether any checks occur, when, and what the UI may claim |
| Progression control | Voice is primary | Activation phrase/listening mode, PC fallback, and optional hardware gesture mapping |
| ElevenLabs/voice — explicitly circle back | Voice selected in principle | Speech output only versus conversation handling, microphone, activation, interruption, and repeat behavior |
| Plan validation | LLM prepares plans with citations to existing projects | Source selection, adaptation checks, reviewer/process, and approval before use |
| Hand identification fallback | Small, clearly laid-out inventory intended | Behavior when hand or part is obscured; whether repositioning/close-up requests are acceptable |
| PC presentation | Required parts, held object, breadboard, circuit, and step layout | Relative prominence and navigation layout |
| Demo evaluation | Novice completes first LED circuit | Deadline, participant count, allowed assistance, and pass criteria |
| Project breadth after the demo | Plans prepared before building | Which additional projects and substitutions are supported |

## Component names and frontend inputs

The proposed [component catalog](labels/component_catalog.md) separates identity
(specific supported name) from classification (broad category). It includes the
LED inventory and separately scoped beginner-project expansion candidates,
including jumper-wire endpoint variants. Runtime migration remains atomic with
prompts, schemas, model configs, and tests; this catalog is not model support.

The frontend consumes:

| Input | Required information |
| --- | --- |
| Project package | Project/version, inventory quantities and attributes, step IDs, instructions, explanations, schematic and breadboard assets, source links |
| Session state | Session ID, current step, state revision, user-reported completion, pause/resume state |
| Visual observation | Frame ID, capture time, image dimensions, instance IDs, boxes, identity, classification, attribute evidence, uncertainty, queried-hand association |
| Inventory result | Expected quantity, observed quantity, user-confirmed quantity, unresolved items; keep these separate |
| Voice command | Event ID, final transcript, intent, session/step context, accepted/rejected result |
| Speech output | Text/audio reference, associated step/request, queued/playing/stopped/error state |
| Device/service status | Camera connection, microphone/listening status, backend connection, inference pending/failure and stale observations |

Proposed intents: next_step, previous_step, repeat_step, pause, resume,
identify_object, explain_component. Only final accepted navigation commands
change state. Deduplicate events and reject stale step-context commands so
partial transcripts, retries, and repeated delivery cannot skip steps. Hearing
“next” in the assistant's own speech must not advance the tutorial. Bind visual
answers to the frame used; ignore obsolete answers after the query changes.

## Circuit tutor (separate track)

A voice-guided breadboard tutor reuses the glasses relay. Cost is the design
constraint:
- Frames stream to the laptop for free. A cloud model sees one frame only when
  the user asks a question or presses the capture button.
- Speech in and out is on-device on the iPhone.
- `recognition/tutor_config.json` freezes a cheap tier (Gemini 3.5 Flash-Lite)
  and a stronger tier (Gemini 3.8 Flash) that runs only when the cheap answer is
  uncertain, invalid, or not in the project BOM. OpenAI models are supported in
  the same slots.

The model reports resistor color bands. `recognition/resistor.py` turns them
into ohms and tries both reading directions. A value outside the BOM, or
unreadable bands, is spoken as such and never guessed. Gemini 3.8 Live and
OpenAI Realtime, which stream continuously, cost far more per hour (see the
plan's price table) and are left as an opt-in later.

A trained YOLO for circuit parts is gated on owner approval to train and on a
labelled dataset. No tutor accuracy is claimed until an owner-collected resistor
photo set is scored.

## Ray-Ban input integration

The iOS relay is finished and is not part of the remaining work: camera frames,
capture-button input and spoken output to the glasses run on hardware (see
`app/ios/README.md`). Remaining glasses work is microphone input only. Meta's [iOS changelog](https://github.com/facebook/meta-wearables-dat-ios/blob/main/CHANGELOG.md)
documents experimental speech transcription, camera audio streaming, input
events, motion, and voice invocation starting with LaunchApp in DAT 1.0.
It states that experimental features can be tested but apps using them cannot
yet be published. Verify capability availability on the actual glasses and
firmware; do not assume every event exists on every device.

Use camera input for observations and microphone/transcription for commands and
questions. Choose either SDK transcription or an audio-to-transcription path;
ElevenLabs speech output alone is not a command interpreter. Add microphone
permission, listening-state UI, command parsing, and event forwarding from
phone to laptop alongside the existing `POST /frame`. Bluetooth output routing
is already shown in the relay status line.

The capture button already reaches the app through MWDATInputs (beta) and
currently triggers speech. Remapping it to repeat or pause is a choice, not new
plumbing; keep a fallback because Inputs may not attach. App-launch voice invocation is separate from arbitrary in-lesson
commands. Motion/head gestures and Display/Neural Band interactions are not
required for this PC-based demo. PC buttons/keyboard are proposed fallbacks.

## Repository transition and implementation gates

The runtime still reads the five device classes in `labels/classes.json`
through `labels.TARGET_CLASSES`. This design update does not change that
contract, existing prompts, models, datasets, or evaluation results.

Before a component experiment runs:

- Confirm the power-up procedure (inventory and steps are confirmed).
- Record owner approval in `AGENTS.md` for fine-tuning YOLO on the team's own
  component photos and for the labeling tool's upload path.
- Define component classes and attribute evidence rules in `labels/`; version
  the migration with matching prompts, schemas, and evaluation materials.
- Update the five-device milestone in `AGENTS.md` for the new experiment while
  preserving prediction integrity, provenance, and resource restrictions.
- Put recognition tooling in `recognition/` and permitted test material,
  annotations, and frozen acceptance criteria in `evaluation/`.
- Evaluate a pretrained YOLO baseline before choosing a model or integrating
  guided assembly; report unsupported classes honestly.

Apart from that approved fine-tune, existing restrictions on training,
installation, weight downloads, credentials, cloud jobs, and uploads remain in
force. No public dataset covers all six classes (jumper wires and USB cables are
missing), and public images may not be mixed into the test set. Missing permitted images, local weights,
or approved runtime access must produce `needs_input`, not simulated inference.
Any new upload path or provider needs its own authorization. Existing Google
upload permissions do not automatically cover new component photos.

The next milestone is a runnable component-identification and guided LED-build
evaluation for the selected parts. Automatic assembly checking is undecided. Application integration follows a documented
review of those results. No component-recognition, circuit-verification, or
learning-outcome claim is established by this specification alone.

## Team and workstreams

Two pairs. Within a pair, each shared artifact has one owner; between pairs,
there are only two interfaces.

| Pair | Person | Owns |
| --- | --- | --- |
| A: lesson | 1 — Noah | Breadboard diagram with the current placement highlighted, circuit reference, step workspace in `frontend/` (glasses view with the required-part highlight, current step, required parts, held object, diagram), PC fallback controls |
| A: lesson | 4 — content and evaluation | Step list and plain-language explanations, answer key and frozen test sessions, pass criteria, novice test run, `AGENTS.md` and open-decisions upkeep |
| B: live system | 2 — recognition | Detector plan above, catalog migration into `labels/`, Gemini prompt and schema migration, inventory check, required-part boxes, held-object answers, scored runs |
| B: live system | 3 — voice and session state | Microphone, transcription, intents, session and step state on the laptop relay (revisions, stale/duplicate rejection, ignoring the app's own speech), spoken directions to the highlighted part, events to the dashboard and glasses audio |

Interfaces, frozen on day one so each side can work against mocks:

1. **Step file** (A → B): step ID, instruction, explanation, required
   classifications and quantities, diagram highlight.
2. **`/events` messages** (B → A): session state, inventory result,
   required-part boxes, held-object answers, device/service status.

Person 4 writes the answer key and pass criteria before person 2 scores, so
recognition is not graded by its builder.
