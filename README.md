# ScavScrap

**A planned, voice-guided first electronics lesson using Ray-Ban glasses and a PC.** The first demonstration aims to help someone who has never built a circuit assemble a red LED on a breadboard and see it stay lit while powered. The PC shows the camera view, the current instruction, required parts, and diagrams; the glasses provide camera input and spoken guidance.

The guided build is the direction in [the latest design spec](DESIGN.md), not a finished product. This repository currently contains a working glasses-to-laptop relay, an older five-device recognition experiment, and a device-scan dashboard. Component recognition, guided session state, microphone commands, and the LED lesson still need implementation and evaluation.

## First demonstration

The proposed lesson uses **seven physical pieces across six item types**:

| Item | Quantity |
| --- | ---: |
| Arduino UNO R3 | 1 |
| Breadboard | 1 |
| Red LED | 1 |
| 330 Ω resistor | 1 |
| Male-to-male jumper wire | 2 |
| USB cable compatible with the Arduino UNO | 1 |

A computer or USB power adapter is also required. The Arduino supplies 5V and GND through its headers. The intended series path is `5V → 330 Ω resistor → LED anode (+) → LED cathode (−) → GND`. Assembly happens with USB disconnected; the power-up procedure and exact breadboard placement belong in a reviewed project package. No sketch upload, digital I/O pin, soldering, or multimeter is part of this first build.

The lesson is intended to:

1. Explain the goal and each part in plain language.
2. Compare the visible table with the planned inventory, distinguishing **seen**, **not visible**, and **unresolved** items. “Not visible” does not prove an item is absent.
3. Show one prepared assembly step at a time, including the needed parts, a highlighted breadboard placement, and a short explanation.
4. Answer questions such as “What is in my right hand?” using the current glasses image. The held object stays separate from the parts required for the step.
5. Let the user move back, repeat, or advance by voice. Advancing records **user-reported completion**, not verified wiring.
6. Guide the final power and observation check. Success means the **external red LED** remains lit while USB powers the assembled circuit; removing USB power turns it off.

The project plan should be prepared before assembly with source links to completed beginner projects, a checked parts list, instructions, a schematic, and a diagram for the actual breadboard. A citation alone does not validate an adapted circuit. The source review process and reviewer remain open decisions.

## Planned PC interface

The latest spec defines the information the PC must present, while exact panel layout and visual emphasis remain open. **The images below reuse a temporary placeholder; they are not screenshots or claims that these screens are implemented.** Each use of `[Image #1]` marks a planned UI image to replace when the corresponding design is ready.

### Inventory and setup

<img src="docs/images/ui-placeholder.png" width="640" alt="Image #1 — placeholder for the inventory and setup view">

*`[Image #1]` represents the initial glasses camera view beside the seven-piece checklist. It should distinguish visually supported quantities, user-confirmed quantities, items missing from the current view, and unresolved items. Camera, microphone, relay, and inference status should be visible without implying a successful check when observation fails.*

### Guided assembly step

<img src="docs/images/ui-placeholder.png" width="640" alt="Image #1 — placeholder for the guided assembly workspace">

*`[Image #1]` represents a step-focused workspace: current plain-language action and explanation, progress and navigation, required-part list, live glasses view with supported boxes on the needed parts, a breadboard diagram highlighting the current placement, and the overall circuit reference. Both jumper wires may be highlighted when either one is suitable. A missing detection should appear as unresolved rather than as a stale or guessed box.*

### Held-object question

<img src="docs/images/ui-placeholder.png" width="640" alt="Image #1 — placeholder for the held-object identification view">

*`[Image #1]` represents an answer to a question about the object in the user's hand. The answer should cite what the current frame supports, explain the part in beginner-friendly terms, or say it cannot tell. It must remain distinct from the required parts for the current step.*

The PC, rather than a display in the glasses, carries the visual highlights. Spoken directions can point to a highlighted part on the screen. Highlighting and right-hand association are capabilities to evaluate; neither is established by the existing five-device detector.

## What works today

| Area | Current state |
| --- | --- |
| iOS relay | The Meta Wearables Device Access Toolkit camera streams frames to the laptop. The relay ran on an iPhone 15 Plus with glasses on 2026-10-24; it draws returned boxes on the phone and supports spoken output routed to the glasses. See [iOS setup](app/ios/README.md). |
| Laptop live runner | `recognition/live_runner.py --listen` receives frames, exposes an MJPEG stream and detection events, and runs the existing device-detection path. |
| Device recognition | Existing configs, runners, and evaluation tools target five device classes: `laptop`, `phone`, `headphones`, `smartwatch`, and `speaker`. They do **not** recognize the LED-build components. No five-class accuracy is claimed without scored real-image runs. |
| Dashboard | [`frontend/`](frontend/README.md) shows the device-scan feed and illustrative device panels. It is not yet the step-focused lesson interface above. |
| Circuit tutor prototype | `recognition/tutor_runner.py` can answer on a requested frame; [`recognition/resistor.py`](recognition/resistor.py) decodes resistor bands spoken by the user. This separate track has no claimed tutor accuracy. |

Still needed for the guided LED build: a reviewed project package and breadboard diagram; component classes and evaluated boxes; inventory and held-object results; microphone input and command handling; session state; the step-focused PC workspace; and a novice build evaluation. Automatic connection or circuit verification is undecided and must not be implied by advancing a step.

## Run the existing prototypes

For the Python tools, use the pinned environment described in [the runbook](RUNBOOK.md):

```sh
uv sync
python -m unittest
python -m recognition.live_runner --help
```

The existing frontend can be started separately:

```sh
cd frontend
npm install
npm run dev
```

See [the iOS relay guide](app/ios/README.md) for device setup and the laptop listener. Real model runs need the configured local weights. Gemini calls require `GEMINI_API_KEY` and permission to upload the specific images; the key stays in the environment. The commands above run or inspect existing tools, not the planned guided lesson.

## Recognition and evaluation rules

The known inventory supplies expectations, but an image must support any visual identification. Do not label an unseen part because it is the last unmatched item. Keep visible observations, expected inventory, and user confirmations separate. A box is an object location, not a mask, a verified connection, or proof of correct assembly. Record uncertainty and provider failures rather than converting them into successful checks.

The proposed component classes are `development_board`, `breadboard`, `led`, `resistor`, `wire`, and `cable`; see the [component catalog](labels/component_catalog.md). They are a design target, **not current model support**. The spec calls for baseline runs, permitted training photos, a held-out glasses-frame test set, and scoring of part identification, inventory matching, held-object answers, and required-part highlights. A novice must also complete the full prepared lesson before a learning or build-success claim is made. See [DESIGN.md](DESIGN.md) for the evaluation plan and implementation gates.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`DESIGN.md`](DESIGN.md) | Latest product direction, first-demo circuit, UI requirements, open decisions, and evaluation gates |
| [`RUNBOOK.md`](RUNBOOK.md) | Commands for the existing recognition experiments |
| [`AGENTS.md`](AGENTS.md) | Repository rules for recognition, provenance, dependencies, and credentials |
| [`labels/`](labels/) | Current five-device class contract and proposed component catalog |
| [`recognition/`](recognition/) | Existing detection, relay, and circuit-tutor tooling |
| [`evaluation/`](evaluation/) | Collection, annotation, and scoring materials |
| [`app/ios/`](app/ios/) | Glasses camera relay and spoken-output app |
| [`frontend/`](frontend/) | Existing React/Vite device-scan dashboard |
| [`design/`](design/) | Earlier illustrative device-scan mockups, not the planned LED lesson |

## License and third-party terms

Repository code is licensed under [AGPL-3.0](LICENSE). Photos under `evaluation/images/` and `walkaround/` are not covered by that license; their owners reserve rights unless provenance notes say otherwise. Ultralytics code and weights have AGPL-3.0 or commercial terms; the Meta Wearables Device Access Toolkit has [Meta's developer terms](https://wearables.developer.meta.com/terms). Gemini requests send permitted images to Google. Check the relevant terms before distributing or deploying a modified system.
