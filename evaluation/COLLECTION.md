# Evaluation image collection

## Target size

Collect a small independent evaluation set:

- 10–20 usable photos for each of `laptop`, `desktop_computer_tower`,
  `monitor`, `printer`, and `projector`.
- 20–30 additional confusing or unsupported photos in total. Include tablets,
  televisions, all-in-one computers, scanners, cameras, empty rooms, and scenes
  containing multiple devices without a clear primary subject.

Use at least three distinct physical devices per target class where practical.
Do not satisfy a class quota with many near-identical photos of one device.
Vary viewpoint, distance, scale, lighting, background clutter, partial occlusion,
and device state while keeping the intended primary device identifiable.

## Folder layout

Empty collection folders are provided under `evaluation/images/` for the five
classes and the `ambiguous`, `unsupported`, and `unreadable` outcomes. Folder name
does not establish ground truth; the reviewed CSV manifest does.

If these empty directories are absent after cloning, recreate them with:

```sh
mkdir -p evaluation/images/{laptop,desktop_computer_tower,monitor,printer,projector,ambiguous,unsupported,unreadable}
```

## Manifest procedure

Copy `manifest_template.csv` to a versioned evaluation manifest. Add one row per
image and preserve these fields:

- `image_id`: unique, stable identifier that does not encode the expected class.
- `path`: repository-relative or manifest-relative image path agreed with the
  runner.
- `expected_outcome`: one of the five target classes, `ambiguous`, `unsupported`,
  or `unreadable`.
- `annotation_path`: path to the separately reviewed ground-truth box record;
  required before scoring localization and never sent to the detector.
- `physical_device_id`: stable identifier shared by every photo of the same
  physical object. Use a documented scene ID for empty scenes.
- `location_session_id`: stable identifier for one location and collection
  session.
- `source`: who or what supplied the image, without exposing unnecessary personal
  information.
- `permission_provenance_notes`: permission, ownership, and reuse restrictions.

Do not put the expected outcome in `image_id` or an image filename. Class-named
collection folders may make the local path informative to a human, but the YOLO
runtime must determine detections from decoded image pixels. The harness uses the
path only to open the image and never maps filename text to a class.

For detection evaluation, add reviewed ground-truth boxes in original-image
pixel `xyxy` coordinates using a separately frozen annotation format. A
whole-image expected outcome is not a localization annotation.

## Grouping and leakage control

Keep every photo of the same `physical_device_id` together. Also keep one
`location_session_id` together when repeated backgrounds could reveal the answer.
This milestone uses one independent test collection, not a training split. If the
set is later divided, assign whole physical-device and location/session groups,
never individual photos.

Inspect exact and near duplicates before locking the manifest. Retakes that differ
only trivially do not count as varied examples.

## Ambiguous ground truth

Apply `labels/guide.md` first. Use `ambiguous` only when the image is readable but
the primary device or target class cannot be resolved. Use `unreadable` when image
quality prevents identification, and `unsupported` when the primary object is
identifiable but outside the five classes.

Have a second reviewer inspect every proposed `ambiguous` row and every disputed
label. Record the final decision outside model-visible inputs. Do not force an
ambiguous image into a target class merely to fill a quota. Unreadable images may
exercise failure handling but do not count toward the 10–20 usable photos for a
target class.

## Locking the test

Before inference:

1. Verify permissions and provenance notes.
2. Confirm unique image IDs and valid expected outcomes.
3. Review physical-device and location/session grouping.
4. Record a checksum of the final CSV and do not tune prompts against its labels.
5. Run the integration checks that verify the frozen class map and prevent
   filename-based mapping.
