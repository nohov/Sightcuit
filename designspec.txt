# Electronics Pokédex — recognition pipeline design, v0.7

The future product helps engineering students learn about electronics. A student
photographs tech items; the app finds them, identifies what each one is, and
shows its specs from cited web sources.

This milestone builds and evaluates the recognition pipeline. It does not build
the app UI.

## Pipeline

```text
photo
→ stage 1: detect      (cheap hosted vision model, e.g. a Qwen-VL model)
→ stage 2: identify    (stronger hosted vision model, e.g. Gemini)
→ stage 3: specs       (stage-2 model with web search grounding)
→ result per item
```

Each stage sits behind a small adapter so its provider can change without
touching the others:

```python
detect(image) -> list[Detection]
identify(image, detection) -> Identification
lookup_specs(identification) -> SpecSheet
```

No item may be presented as recognized until real model requests have run and
every response satisfies its stage's output contract. Model output is evidence
to evaluate, not ground truth.

## Stage 1: detect

A cheap, fast hosted vision-language model receives one orientation-corrected,
compressed photo and a frozen prompt. It returns every visible tech item:

```json
{
  "items": [
    {"category": "laptop", "box": [0.12, 0.30, 0.58, 0.81], "evidence": "open clamshell with keyboard and display"}
  ]
}
```

- `category` is one of the classes in `labels/classes.json`. The initial set is
  `laptop`, `desktop_computer_tower`, `monitor`, `printer`, `projector`, plus
  `other_electronics` for tech items outside that set. Adding a category is a
  change to `labels/classes.json` and a new prompt version.
- `box` is `[x1, y1, x2, y2]` normalized to 0–1. It is used to crop the item for
  stage 2; it is approximate and not a precise localization claim.
- An empty `items` list is a valid answer for a photo with no tech items.
  `unreadable` is returned when the photo cannot be interpreted.

## Stage 2: identify

A stronger hosted vision model receives the crop, the full photo for context,
and the stage-1 category. It identifies the item at product-line level:

```json
{
  "level": "product_line",
  "category": "laptop",
  "brand": "Apple",
  "product_line": "MacBook Air",
  "evidence": "Apple logo on lid, thin wedge profile, no visible ports on front"
}
```

`level` records how far identification got:

- `product_line` — brand and product line (e.g. "Apple MacBook Air", "HP LaserJet")
- `brand_only` — brand is clear, product line is not
- `category_only` — only the category is supported by visible evidence

Exact model, generation, year and SKU are out of scope. Many items in one
product line look the same (e.g. MacBook Air generations), and guessing them
would present invented precision. Evidence must cite visible features only.
Stage 2 may correct the stage-1 category; both values are kept.

## Stage 3: specs

The stage-2 model, using its web search grounding tool, retrieves typical specs
for the identified product line:

```json
{
  "product_line": "Apple MacBook Air",
  "specs": [
    {"name": "display", "value": "13.3–15.3 in, ~2560×1600", "source": "https://..."}
  ]
}
```

- Every spec carries a source URL. A spec without a source is dropped.
- Because the exact model is unknown, values describe the product line as
  ranges or typical values, never as the exact unit's specs.
- `brand_only` and `category_only` items get category-level educational info
  only, not product specs.
- Results are cached by product line so repeated items do not repeat lookups.

## Failures versus abstentions

Invalid JSON, an unknown category or level, timeout, rate limit or provider error
is a request failure at that stage. It is recorded as a failure with an explicit
error and is never converted to an empty detection, `category_only`, or a
correct abstention. A stage-1 failure stops that photo; a stage-2 or stage-3
failure stops only that item.

## Reproducibility contract

Each record preserves, per stage:

- image ID and SHA-256, without ground truth in any model request;
- provider, exact model ID, API and adapter versions;
- prompt and response-schema versions;
- image dimensions, crop box and preprocessing settings;
- request parameters that affect model behavior;
- start time, elapsed time, token usage, provider request ID when returned, and
  explicit error;
- normalized output and raw response with secrets removed;
- for stage 3, the search queries and source URLs returned by grounding.

Freeze provider, model ID, prompt and schema for each stage before a run.
Changing any of them creates a new experiment version. The runner writes
records atomically and keeps one record per manifest row, including failures.
Filenames never determine predictions.

## Evaluation

Use 10–20 permitted photos per category, 20–30 photos with no tech items or
confusing non-tech objects, and some multi-item scenes. Vary devices,
viewpoints, lighting, distance, occlusion and clutter. Group images by physical
device and capture session. Lock the test manifest before model requests begin.

Report:

- stage 1: per-category precision and recall, missed items, false detections on
  non-tech photos, and whether each box contains its item;
- stage 2: brand and product-line accuracy, the distribution of `level`, and
  wrong product lines stated at `product_line` level (the worst error);
- stage 3: share of specs with sources, and a manual spot check of at least 20
  specs against their cited pages;
- end to end: request failures per stage, median and p95 latency, and cost per
  photo.

Preserve representative errors and raw responses.

## Comparison, not default

YOLO remains a possible stage-1 replacement if the app needs live video boxes,
tracking or offline use; its COCO weights cover only `laptop` from the initial
set, so it would need fine-tuning first. A local Qwen-VL through Ollama remains
an offline alternative for stage 1.

## Gemini vs YOLO bake-off

- Tell participants that photos are sent to the configured vision providers and
  that item identities are sent to a web search tool.
- Record each provider's retention and training-data terms before sending images.
- Send selected photos only, not continuous video.
- Remove images after evaluation according to the approved retention plan.
- Set a request limit and cost ceiling per stage before enabling paid calls.
- Retry only transient failures, with a capped retry count.
- API credentials stay on the backend, never in logs or client code.

## Stop conditions

If an approved provider, model ID, credentials, cost ceiling, retention terms or
permitted images are missing for a stage, build that stage's adapter, schema,
tests and a blocker report, then stop before making a request.

## Later application milestone

After the evaluation supports a model choice per stage, a separate milestone may
add photo capture, educational cards, corrections and saved collections. Its UI
must distinguish detections, identifications, sourced specs, user corrections and
failures, and must never present a product-line guess as an exact model.
