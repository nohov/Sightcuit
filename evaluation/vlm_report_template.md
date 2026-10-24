# Whole-image VLM classification report template

This template is not for YOLO detection or localization metrics.

## Run identity

- Evaluation manifest:
- Manifest checksum:
- Prediction file:
- Model identifier:
- Prompt version:
- Runtime and hardware:
- Run date:
- Reviewer:

## Dataset accounting

- Total manifest rows:
- Rows per expected outcome:
- Distinct physical devices per target class:
- Distinct location/session groups:
- Confusing or unsupported examples:
- Ambiguous ground-truth rows:
- Unreadable ground-truth rows:
- Permission or provenance exceptions:
- Duplicate or leakage review:

## Results

Copy values from the generated JSON report; do not calculate them by hand.

| Class | Precision | Recall | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| laptop | | | | | |
| phone | | | | | |
| headphones | | | | | |
| smartwatch | | | | | |
| speaker | | | | | |

- Overall confusion summary:
- Abstention count and rate:
- Unsupported-object false acceptance count and rate:
- Request failure count and rate:
- Latency count, mean, median, and p95:
- Unexpected prediction IDs:
- Malformed prediction records:

## Mistake review

For each important error pattern, cite image IDs without copying private images
into the report.

| Pattern | Image IDs | Likely cause | Follow-up experiment |
| --- | --- | --- | --- |
| | | | |

## Evidence and limitations

- Commands actually run:
- Tests actually run:
- Whether real inference ran:
- Missing images, runtimes, weights, or dependencies:
- Ground-truth disagreements:
- Conclusions supported by this run:
- Claims this run does not support:
