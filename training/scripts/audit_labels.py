"""Visual audit of auto-generated labels.

Draws bounding boxes on a random sample of labeled images and saves
them to datasets/circuit/audit/ so you can spot-check DINO's work.

Usage:
    python scripts/audit_labels.py           # 30 random images
    python scripts/audit_labels.py --n 60    # more samples
    python scripts/audit_labels.py --cls switch  # one class only
"""

import argparse
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT    = Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "circuit"
AUDIT   = DATASET / "audit"

CLASSES = ["board", "blue_wire", "red_led", "resistor", "switch", "wire"]
COLORS  = {
    "board":     "#f59e0b",
    "blue_wire": "#3b82f6",
    "red_led":   "#ef4444",
    "resistor":  "#8b5cf6",
    "switch":    "#10b981",
    "wire":      "#6b7280",
}


def draw_boxes(img_path: Path, label_path: Path) -> Image.Image:
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    for line in label_path.read_text().strip().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cid, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
        cls = CLASSES[cid] if cid < len(CLASSES) else str(cid)
        color = COLORS.get(cls, "#ffffff")

        x1 = int((cx - bw / 2) * w)
        y1 = int((cy - bh / 2) * h)
        x2 = int((cx + bw / 2) * w)
        y2 = int((cy + bh / 2) * h)

        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        draw.rectangle([x1, y1 - 20, x1 + len(cls) * 8 + 8, y1], fill=color)
        draw.text((x1 + 4, y1 - 18), cls, fill="#000000")

    return img


def run(n: int, cls_filter: str | None):
    AUDIT.mkdir(exist_ok=True)

    images = sorted((DATASET / "images").glob("*.jpg"))
    if cls_filter:
        images = [p for p in images if p.stem.startswith(cls_filter)]

    sample = random.sample(images, min(n, len(images)))
    saved = 0

    for img_path in sample:
        label_path = DATASET / "labels" / f"{img_path.stem}.txt"
        if not label_path.exists():
            continue
        result = draw_boxes(img_path, label_path)
        # Shrink large images for easy viewing
        result.thumbnail((1200, 900), Image.LANCZOS)
        result.save(AUDIT / f"audit_{img_path.stem}.jpg", "JPEG", quality=88)
        saved += 1

    print(f"Saved {saved} audit images to {AUDIT}/")
    print("Open that folder and check boxes look right.")
    print()
    print("What to look for:")
    print("  GOOD: tight box around the object")
    print("  BAD:  box covers the whole image, or misses the object entirely")
    print("  BAD:  wrong class label on the box")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n",   type=int, default=30, help="number of images to audit")
    parser.add_argument("--cls", default=None, help="filter to one class e.g. switch")
    args = parser.parse_args()
    run(args.n, args.cls)
