# ScavScrap — guided circuit building, v0.11

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
- ElevenLabs is intended for voice; the division between speech output and
  conversation handling remains open.
- Assembly is breadboard-only, with no coding, soldering, or additional sensors.
  Multimeters are deferred. The Arduino supplies power through its 5V/GND pins.
- Voice commands are the primary way to advance steps. Progression is
  user-directed; automatic assembly verification remains undecided. PC controls
  are a proposed fallback.

## First demo: USB-powered red LED

Owner-specified inventory (availability is not yet physically verified):

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
coordinates and the diagram depend on the actual breadboard and remain pending.
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
and nominal resistor value; actual LED specifications, resistor rating, board
layout, and physical part availability still need confirmation.

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

The final success criterion is a novice completing this circuit and observing
the external red LED remain lit while powered. Record any assistance required.
Turning off by removing USB is the expected shutdown, not a separate switching
feature. The earlier ambiguous “turns off” criterion is superseded.

## PC interface and current repository

The existing `frontend/src/App.jsx` provides a glasses recording panel with
boxes, a rotating device model, measurements, device particulars, and a metal
assay. Its current focus is the most confident labelled track, not a detected
right-hand object. These are existing implementation facts, not new features.

Adapt that dashboard concept into a step-focused workspace:

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

Power architecture is resolved: USB source → UNO USB connector → 5V/GND
headers → breadboard circuit. The particular computer or USB adapter and cable
availability remain open. Direct mains wiring is outside the demonstration.

## Evaluation

Evaluate real, permitted glasses images of the selected parts for component
identification, initial inventory matching, and held-object questions. Include
occlusion and ambiguous views even with the small inventory. Report errors,
abstentions, failures, latency, and cost; do not infer accuracy from scene size.

Run the complete prepared tutorial with a novice and record completion,
interventions, confusing instructions, and the final circuit behavior. Choose
participant count and acceptance thresholds before claiming success. If automatic
assembly checking is later included, evaluate it separately on correct and
incorrect placements. Mocked software tests do not establish vision performance.

## Open decisions — circle-back list

| Decision | Current position | Needed to resolve |
| --- | --- | --- |
| Physical parts and layout | Seven pieces across six types specified above | Confirm availability, breadboard layout, LED specifications, resistor rating, and USB cable; decide cable recognition scope |
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

## Ray-Ban input integration

The current iOS relay handles camera frames only. Its README records DAT 1.0.1.
Meta's [iOS changelog](https://github.com/facebook/meta-wearables-dat-ios/blob/main/CHANGELOG.md)
documents experimental speech transcription, camera audio streaming, input
events, motion, and voice invocation starting with LaunchApp in DAT 1.0.
It states that experimental features can be tested but apps using them cannot
yet be published. Verify capability availability on the actual glasses and
firmware; do not assume every event exists on every device.

Use camera input for observations and microphone/transcription for commands and
questions. Choose either SDK transcription or an audio-to-transcription path;
ElevenLabs speech output alone is not a command interpreter. Add microphone
permission, listening-state UI, command parsing, and event forwarding from
phone to laptop. Test audio output routing separately.

Optional touch/button events can later map to repeat or pause after testing
MWDATInputs on the hardware. Do not assume the capture button can be freely
remapped. App-launch voice invocation is separate from arbitrary in-lesson
commands. Motion/head gestures and Display/Neural Band interactions are not
required for this PC-based demo. PC buttons/keyboard are proposed fallbacks.

## Repository transition and implementation gates

The runtime still reads the five device classes in `labels/classes.json`
through `labels.TARGET_CLASSES`. This design update does not change that
contract, existing prompts, models, datasets, or evaluation results.

Before a component experiment runs:

- Confirm the LED set, initial project plan, and power arrangement.
- Define component classes and attribute evidence rules in `labels/`; version
  the migration with matching prompts, schemas, and evaluation materials.
- Update the five-device milestone in `AGENTS.md` for the new experiment while
  preserving prediction integrity, provenance, and resource restrictions.
- Put recognition tooling in `recognition/` and permitted test material,
  annotations, and frozen acceptance criteria in `evaluation/`.
- Evaluate a pretrained YOLO baseline before choosing a model or integrating
  guided assembly; report unsupported classes honestly.

Existing restrictions on training, installation, weight downloads, credentials,
cloud jobs, and uploads remain in force. Missing permitted images, local weights,
or approved runtime access must produce `needs_input`, not simulated inference.
Any new upload path or provider needs its own authorization. Existing Google
upload permissions do not automatically cover new component photos.

The next milestone is a runnable component-identification and guided LED-build
evaluation for the selected parts. Automatic assembly checking is undecided. Application integration follows a documented
review of those results. No component-recognition, circuit-verification, or
learning-outcome claim is established by this specification alone.
