"""Auto-label circuit component images using Grounding DINO.

Reads dataset_combined.zip, runs Grounding DINO on every image,
writes YOLO-format labels, and outputs a ready-to-train dataset
under datasets/circuit/ with data.yaml, train.txt, val.txt.

Usage:
    python scripts/autolabel.py
    python scripts/autolabel.py --threshold 0.25 --review
"""

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP  = ROOT.parent / "dataset_combined.zip"
OUT  = ROOT / "datasets" / "circuit"

CLASSES = ["board", "blue_wire", "red_led", "resistor", "switch", "wire"]
CID = {c: i for i, c in enumerate(CLASSES)}

# Text prompts fed to Grounding DINO per class folder name in the zip.
# Multiple prompts per class improve recall on varied photos.
PROMPTS = {
    "board":     "arduino board . breadboard . circuit board",
    "blue_wire": "blue usb cable . blue wire . blue cable",
    "red_led":   "red LED . red light emitting diode . red led light",
    "resistor":  "resistor . electronic resistor . resistor component",
    "switch":    "switch . toggle switch . push button switch",
    "wire":      "jumper wire . jumper cable . wire",
}

THRESHOLD = 0.25   # Grounding DINO confidence threshold


def load_model():
    from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
    import torch
    model_id = "IDEA-Research/grounding-dino-base"
    print(f"Loading Grounding DINO ({model_id})...")
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"  Model on {device}")
    return processor, model, device


def predict(processor, model, device, image, prompt, threshold):
    import torch
    inputs = processor(images=image, text=prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    results = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=threshold,
        target_sizes=[image.size[::-1]],
    )[0]
    return results["boxes"].cpu(), results["scores"].cpu()


def to_yolo(box, img_w, img_h):
    """xyxy pixels → normalized cx cy w h, clipped."""
    x1, y1, x2, y2 = box.tolist()
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img_w, x2), min(img_h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    cx = (x1 + x2) / 2 / img_w
    cy = (y1 + y2) / 2 / img_h
    w  = (x2 - x1) / img_w
    h  = (y2 - y1) / img_h
    return cx, cy, w, h


def is_val(stem):
    return int(hashlib.sha1(stem.encode()).hexdigest(), 16) % 100 < 15


def run(threshold, review):
    from PIL import Image
    import io

    if not ZIP.exists():
        sys.exit(f"ERROR: {ZIP} not found. Expected at {ZIP}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "images").mkdir(exist_ok=True)
    (OUT / "labels").mkdir(exist_ok=True)

    processor, model, device = load_model()

    stats = {c: {"images": 0, "boxes": 0, "skipped": 0} for c in CLASSES}
    train_stems, val_stems = [], []
    review_items = []  # (stem, cls, n_boxes) for low-confidence images

    with zipfile.ZipFile(ZIP, "r") as zf:
        entries = [e for e in zf.infolist()
                   if e.filename.lower().endswith((".jpg", ".jpeg", ".png"))
                   and "__MACOSX" not in e.filename]

        print(f"Processing {len(entries)} images...")
        for idx, entry in enumerate(entries):
            parts = entry.filename.split("/")
            if len(parts) < 3:
                continue
            cls = parts[1]
            if cls not in CLASSES:
                continue

            stem = f"{cls}_{Path(entry.filename).stem}"
            img_bytes = zf.read(entry.filename)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img_w, img_h = image.size

            prompt = PROMPTS[cls]
            boxes, scores = predict(processor, model, device, image, prompt, threshold)

            lines = []
            for box, score in zip(boxes, scores):
                yolo = to_yolo(box, img_w, img_h)
                if yolo:
                    cx, cy, w, h = yolo
                    lines.append(f"{CID[cls]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

            if not lines:
                stats[cls]["skipped"] += 1
                if review:
                    review_items.append((stem, cls, 0))
                continue

            # Save image
            img_path = OUT / "images" / f"{stem}.jpg"
            image.save(img_path, "JPEG", quality=95)

            # Save label
            (OUT / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")

            stats[cls]["images"] += 1
            stats[cls]["boxes"]  += len(lines)

            if is_val(stem):
                val_stems.append(stem)
            else:
                train_stems.append(stem)

            if (idx + 1) % 50 == 0:
                print(f"  {idx+1}/{len(entries)} done")

    # Write train/val lists
    (OUT / "train.txt").write_text(
        "\n".join(f"./images/{s}.jpg" for s in sorted(train_stems)) + "\n")
    (OUT / "val.txt").write_text(
        "\n".join(f"./images/{s}.jpg" for s in sorted(val_stems)) + "\n")

    # Write data.yaml
    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(CLASSES))
    (OUT / "data.yaml").write_text(
        f"train: train.txt\nval: val.txt\nnames:\n{names}\n")

    # Print summary
    print("\n=== Auto-label summary ===")
    total_imgs, total_boxes, total_skip = 0, 0, 0
    for cls in CLASSES:
        s = stats[cls]
        print(f"  {cls:12s}  {s['images']:3d} labeled  {s['boxes']:4d} boxes  {s['skipped']:3d} skipped")
        total_imgs  += s["images"]
        total_boxes += s["boxes"]
        total_skip  += s["skipped"]
    print(f"  {'TOTAL':12s}  {total_imgs:3d} labeled  {total_boxes:4d} boxes  {total_skip:3d} skipped")
    print(f"  train: {len(train_stems)}  val: {len(val_stems)}")
    print(f"\nDataset at: {OUT}")

    if review and review_items:
        review_path = OUT / "no_detections.json"
        review_path.write_text(json.dumps(
            [{"stem": s, "class": c, "boxes": n} for s, c, n in review_items], indent=2))
        print(f"  {len(review_items)} images with no detections: {review_path}")

    print("\nNext step:")
    print(f"  .venv\\Scripts\\yolo detect train data={OUT / 'data.yaml'} "
          f"model=weights/scavscrap_v2_best.pt "
          f"epochs=50 patience=7 imgsz=1280 batch=8 workers=4 device=0 name=circuit_v1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=THRESHOLD,
                        help=f"Grounding DINO confidence threshold (default {THRESHOLD})")
    parser.add_argument("--review", action="store_true",
                        help="Save a list of images with no detections for manual review")
    args = parser.parse_args()
    run(args.threshold, args.review)
