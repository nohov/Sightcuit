# Whole-image VLM comparison proposal

This is a secondary, unexecuted classification comparison. The YOLO object
detector is the first milestone and default baseline.

The frozen scope follows `labels/classes.json` and `labels/guide.md`: exactly the
five target classes plus `ambiguous`, `unsupported`, and `unreadable`, with one
primary-device outcome per image.

## Comparison candidate

If a later whole-image comparison is approved, use
`qwen3-vl:4b-instruct-q4_K_M` through a local Ollama server after installation and
model download are separately authorized. This is a proposal, not an accuracy
claim and not object detection.

Why this is the smallest credible option:

- It accepts image and text input, while the five-class task needs open-vocabulary
  distinctions that a fixed-label classifier may not contain (especially
  `projector` and `desktop_computer_tower`).
- Ollama's local REST API accepts base64 images and a JSON Schema, so the checked-in
  runner needs only Python's standard library.
- The exact Ollama artifact is a 4.02B-parameter Q4_K_M model plus a 415M vision
  projector, is about 3.3 GB, requires Ollama 0.12.7, and is listed under Apache
  2.0. The upstream Qwen3-VL repository and the specific Hugging Face model card
  also identify Apache 2.0. Ollama itself is MIT-licensed.

Requirements not currently satisfied:

- Ollama 0.12.7 or newer and `qwen3-vl:4b-instruct-q4_K_M` weights. Installing Ollama
  and downloading the model were prohibited for this task.
- Evaluation images and a JSONL manifest. No image files exist in the repository.
- Enough free memory for the runtime, vision encoder, model, and image processing.
  The model artifact size is documented, but peak memory and latency on this
  machine have not been measured.

The inspected host is an Apple M4 MacBook Pro with 16 GB memory, macOS 26.2,
Python 3.14.3, and Node 25.8.0. Pillow 12.2.0 and jsonschema 4.26.0 are present,
but the project has no dependency manifest. Torch, torchvision, Transformers,
MLX, MLX-VLM, Ollama, llama.cpp, the OpenAI SDK, and pytest are absent. The only
cached Hugging Face model is a text embedding model, not a vision model.

### Limitations

- Qwen's published capabilities and benchmark results do not establish accuracy
  on these five project labels. Quantization may change behavior. The prompt must
  be evaluated on held-out images before use.
- This is whole-image classification, not detection, segmentation, or proof that
  the predicted device is the intended subject.
- A response that looks certain is not calibrated. The output intentionally has
  no confidence or probability field.
- `ambiguous`, `unsupported`, and `unreadable` are model decisions when inference
  succeeds. Local file failures map to `unreadable`; provider, transport, and
  invalid-response failures map to `unsupported` with a non-null `error`, so they
  cannot be mistaken for successful inference.
- The runner verifies that a file exists and is non-empty. It delegates full image
  decoding to the vision runtime; a corrupt non-empty file should produce either
  `unreadable` or an explicit inference error.

## Local versus hosted

| Choice | Benefits | Costs and risks |
|---|---|---|
| Local Qwen3-VL 4B + Ollama | Images remain on the machine; repeat runs have no per-request API charge; quantization tag and prompt are recorded | Requires an approved runtime install and 3.3 GB model download; local memory/latency and five-class quality are unmeasured; local structured output still requires validation; registry tags can move, so record the installed artifact ID before evaluation |
| Hosted vision model | No local weights or accelerator setup; current services such as GPT-6 Astra accept image input and structured output | Images leave the machine; credentials and paid inference are required; token/image costs and service behavior can change; the current runner does not implement a hosted adapter |

GPT-6 Astra is only a concrete hosted comparison, not the default: its official
model page lists image input and structured outputs, but also usage-based pricing.
No hosted request was made and no credential was read or changed.

## Reproducible runner

The runner accepts Evaluation's reviewed CSV manifest directly and also retains
legacy JSON Lines support. It reads only `image_id` and `path`; every other CSV
field is ignored and never enters the model request. A legacy JSONL entry is:

```json
{"image_id":"lab-001","path":"images/lab-001.jpg"}
```

Paths are relative to the manifest. Extra manifest fields are ignored and never
sent to the model. In particular, ground-truth labels may be present for later
scoring but are excluded from requests. Each valid manifest row produces one
JSONL record with `image_id`, the class or abstention `outcome`, model identifier,
prompt version, measured request latency, explicit error, evidence, and preserved
raw model response. The output is written to a temporary file and atomically
replaced after all entries finish.

After separately approving and completing the missing install/download:

```sh
ollama serve
ollama pull qwen3-vl:4b-instruct-q4_K_M
python3 recognition/vlm_runner.py evaluation/manifest.csv evaluation/vlm_predictions.jsonl
```

`prompt-v1.txt` is the frozen prompt. `model_response.schema.json` is passed to
Ollama. `classification_prediction.schema.json` specifies the persisted record. Change the prompt
version whenever prompt wording or class rules change.

## Checks actually run

Executed on 2026-10-23:

```sh
python3 -m unittest discover -s recognition/tests -v
python3 -m py_compile recognition/vlm_runner.py
python3 recognition/vlm_runner.py --help
```

All mocked unit tests passed. They cover valid JSONL and CSV predictions,
ground-truth exclusion from requests, a missing image, and an invalid model outcome
with raw response preservation. Python compilation and CLI help also succeeded.

No actual vision-model inference ran: there is no compatible installed runtime,
vision weight, or project image. Therefore there are no recognition predictions,
latency measurements, or accuracy results.

## Primary sources

- Qwen3-VL upstream repository, runtime guidance, and license:
  https://github.com/QwenLM/Qwen3-VL
- Specific Qwen3-VL 4B model card and license metadata:
  https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
- Ollama model artifact details and minimum version:
  https://ollama.com/library/qwen3-vl:4b-instruct
- Ollama vision request format:
  https://docs.ollama.com/capabilities/vision
- Ollama structured-output behavior:
  https://docs.ollama.com/capabilities/structured-outputs
- Ollama software license:
  https://github.com/ollama/ollama/blob/main/LICENSE
- OpenAI image-input documentation and limitations:
  https://developers.openai.com/api/docs/guides/images-vision
- OpenAI structured-output documentation:
  https://developers.openai.com/api/docs/guides/structured-outputs
- Hosted comparison model capabilities and pricing:
  https://developers.openai.com/api/docs/models/gpt-6-astra
