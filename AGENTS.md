# ScavScrap recognition evaluation

The first milestone is an honest evaluation of pretrained object detection for
exactly five project classes: `laptop`, `phone`, `headphones`, `smartwatch`,
and `speaker`. `labels/classes.json` is the single source of the class list;
code reads it through `labels.TARGET_CLASSES`.

Evaluate a YOLO detector before choosing a model or integrating an application.
Predictions must come from image pixels. Filenames, folder names, manifest ground
truth, and provenance must never determine or enter predictions.

Do not train or fine-tune models, install dependencies, download weights, start
cloud jobs, collect a large dataset, read credentials, or change global
configuration. The owner-approved exceptions for the bake-off are:

- Gemini API calls through `recognition/gemini_runner.py` and
  `recognition/cascade_runner.py`, using
  `GEMINI_API_KEY` from the environment only. Never write the key to files,
  logs, commands, or records. Send only images whose
  `permission_provenance_notes` permit upload to Google.
- One owner-run install of Ultralytics and download of the frozen
  YOLO-World weights named in `recognition/yolo_world_model.json`.
- A Developer-Mode-only iOS relay prototype in `app/ios/` that adds the Meta
  Wearables Device Access Toolkit Swift package. It sends glasses frames only
  to the owner's laptop via `recognition/live_runner.py --listen`; Gemini calls
  stay on the laptop.

- A circuit tutor, separate from the five-class evaluation:
  `recognition/tutor_runner.py` sends the newest frame to the models frozen in
  `recognition/tutor_config.json` (Gemini, and OpenAI if configured) only when
  the user asks a question or presses the glasses capture button, never as a
  continuous stream. Use `GEMINI_API_KEY` / `OPENAI_API_KEY` from the
  environment only, under the same never-write rule. The iPhone listens for
  the wake word on-device; microphone audio of an utterance without it never
  leaves the phone. An utterance with it goes to the laptop as a WAV (at most
  30 s) plus the on-device transcript. When `ELEVENLABS_API_KEY` is set in the
  laptop's environment (same never-write rule), the laptop sends that WAV,
  never images, to ElevenLabs speech-to-text, and each reply's text to
  ElevenLabs text-to-speech, caching the WAV under `cache/tts/`; otherwise the
  phone's transcript is used and the iPhone speaks the reply itself. The iOS app may add
  the experimental `MWDATInputs` module for the capture button. Resistor values
  come from `recognition/resistor.py`, never from a model. Model confidence
  is null. No tutor accuracy is claimed until a recorded resistor eval is scored.

Otherwise use only already-installed runtimes, existing local weights, and
permitted local images. If any are missing, stop at a runnable specification
and report `needs_input`; never simulate inference.

Preserve the detector's original class ID, class name, confidence, and bounding
box. Map a raw class to a project class only when the frozen configuration says
the semantics match exactly. `clock` is not `smartwatch`. A missing detector class is
unsupported, not a successful classification.

Keep output types honest: YOLO and Gemini detection produce boxes; boxes are not
masks. Gemini returns no calibrated confidence, so record it as null rather than
inventing one. The Qwen3-VL/Ollama path is a separate whole-image classification
proposal and is not the default. Do not describe mocked tests as model inference or claim accuracy
without recorded predictions from real images.

Keep class definitions in `labels/`, detector and comparison tooling in
`recognition/`, and evaluation materials in `evaluation/`. Do not read or modify
unrelated projects or credentials. Verify technical and license claims against
primary sources.
