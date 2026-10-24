# ScavScrap recognition evaluation

The first milestone is an honest evaluation of pretrained object detection for
exactly five project classes: `laptop`, `desktop_computer_tower`, `monitor`,
`printer`, and `projector`.

Evaluate a YOLO detector before choosing a model or integrating an application.
Predictions must come from image pixels. Filenames, folder names, manifest ground
truth, and provenance must never determine or enter predictions.

Do not train or fine-tune models, install dependencies, download weights, use
paid APIs, start cloud jobs, collect a large dataset, read credentials, or change
global configuration. Use only already-installed runtimes, existing local weights,
and permitted local images. If any are missing, stop at a runnable specification
and report `needs_input`; never simulate inference.

Preserve the detector's original class ID, class name, confidence, and bounding
box. Map a raw class to a project class only when the frozen configuration says
the semantics match exactly. `tv` is not `monitor`. A missing detector class is
unsupported, not a successful classification.

Keep output types honest: YOLO detection produces boxes; boxes are not masks.
The Qwen3-VL/Ollama path is a separate whole-image classification proposal and is
not the default. Do not describe mocked tests as model inference or claim accuracy
without recorded predictions from real images.

Keep class definitions in `labels/`, detector and comparison tooling in
`recognition/`, and evaluation materials in `evaluation/`. Do not read or modify
unrelated projects or credentials. Verify technical and license claims against
primary sources.
