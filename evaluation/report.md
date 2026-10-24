# Evaluation preparation report

Prepared an independent image collection package for the five stable target
classes plus confusing, unsupported, and unreadable inputs. The current manifest
supports whole-image review and provenance. A YOLO localization evaluation also
requires reviewed ground-truth boxes, which do not yet exist.

The retained whole-image VLM scorer consumes the reviewed CSV manifest and its
classification JSONL records. It reports per-class precision and recall, a full outcome
confusion map, abstention rate, unsupported-object false acceptance, request
failures, and latency. Every manifest row remains in the report. Missing records,
non-null prediction errors, and invalid outcomes become explicit
`request_failure` results rather than disappearing or inheriting the runner's
fallback class.

No images or completed labels were invented. The image directories and CSV
template are empty. Unit tests use only synthetic records created at test time.

It does not score YOLO boxes and cannot support a localization-quality claim.

## Integration review

YOLO raw detections use `recognition/prediction.schema.json`. The legacy
whole-image scorer and `classification_prediction.schema.json` remain only for
the separate VLM comparison. No YOLO precision, recall, or localization metric
can be computed until reviewed boxes are added.
