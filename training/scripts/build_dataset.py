"""Build the merged scavscrap YOLO dataset from Open Images V7, LVIS and Objects365.

Usage: python scripts/build_dataset.py {selftest,openimages,lvis,objects365,roboflow-download,split}
       python scripts/build_dataset.py roboflow export.zip "Their Name=our_class" ...
roboflow-download needs ROBOFLOW_API_KEY in the environment (free account: roboflow.com > Settings > API Keys).
"""

import hashlib
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "datasets" / "_raw"
OUT = ROOT / "datasets" / "scavscrap"

CLASSES = ["laptop", "desktop_computer_tower", "monitor", "printer", "projector",
           "keyboard", "mouse", "phone", "tablet", "tv", "router",
           "headphones", "speaker", "watch"]  # appended so IDs 0-10 match v2; earbuds count as headphones
CID = {name: i for i, name in enumerate(CLASSES)}

OPENIMAGES = {"Laptop": "laptop", "Computer monitor": "monitor", "Printer": "printer",
              "Computer keyboard": "keyboard", "Computer mouse": "mouse", "Mobile phone": "phone",
              "Tablet computer": "tablet", "Television": "tv", "Headphones": "headphones", "Watch": "watch"}
LVIS = {"laptop_computer": "laptop", "monitor_(computer_equipment) computer_monitor": "monitor",
        "printer": "printer", "projector": "projector", "computer_keyboard": "keyboard",
        "mouse_(computer_equipment)": "mouse", "cellular_telephone": "phone",
        "television_set": "tv", "router_(computer_equipment)": "router", "earphone": "headphones",
        "headset": "headphones", "speaker_(stero_equipment)": "speaker", "watch": "watch"}
LVIS_REQUIRED = {"monitor", "printer", "projector", "router", "headphones", "speaker", "watch"}  # images LVIS adds beyond Open Images
O365 = {"Laptop": "laptop", "Computer Box": "desktop_computer_tower", "Projector": "projector",
        "Printer": "printer", "Keyboard": "keyboard", "Mouse": "mouse", "Cell Phone": "phone",
        "Tablet": "tablet", "Router/modem": "router", "Head Phone": "headphones", "earphone": "headphones",
        "Speaker": "speaker", "Watch": "watch"}
O365_MASK = "Moniter/TV"  # sic, upstream spelling; merged class: painted out so it is never an unlabeled monitor or tv
O365_REQUIRED = {"desktop_computer_tower", "projector", "printer", "router", "headphones", "speaker", "watch"}
# Roboflow Universe exports in the dataset: workspace/project/version, then "Their Name=our_class" mappings
# (recovered from the v2 labels; unmapped classes such as person or book are dropped).
ROBOFLOW_SETS = [
    ("object-detection-w6jrg/printer-apkfy/2", "Printer=printer", "Printer - v1 2026-05-06 1-40pm=printer"),
    ("rawattech-wvjzo/tablets-wwxv9/2", "tablet=tablet"),
    ("monitor-3sxsx/monitor-zsqud/7", "monitor hidup=monitor", "monitor mati=monitor"),
    ("printer/printer-ler5v/1", "printer=printer"),
    ("sunmoonuniversary/monitor-vmdjp/1", "monitor=monitor"),
    ("gursimar-gill/desktop-pc-dearc-vfv1m/1", "DESKTOP PC=desktop_computer_tower",
     "Desktop-PC=desktop_computer_tower", "Monitors=monitor"),
    ("kong-pkdaq/mouse-keyboard-tablet/1", "mouse=mouse", "keyboard=keyboard", "tablet=tablet"),
    ("pakapon/detect-router-nowgx/2", "router=router"),
    ("camera-4rq00/classroom-ju7eu/1", "projector=projector"),
]
O365_URL = "https://dorc.ks3-cn-beijing.ksyun.com/data-set/2020Objects365%E6%95%B0%E6%8D%AE%E9%9B%86/val/"


def to_yolo(x, y, w, h, img_w, img_h):
    """Top-left xywh (pixels, or relative with img size 1) -> clipped normalized cx cy w h, or None."""
    x1, y1 = max(0.0, x / img_w), max(0.0, y / img_h)
    x2, y2 = min(1.0, (x + w) / img_w), min(1.0, (y + h) / img_h)
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)


def is_val(stem):
    return int(hashlib.sha1(stem.encode()).hexdigest(), 16) % 100 < 15


def iou(a, b):
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    inter = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


def drop_laptop_monitors(boxes):
    """Open Images and LVIS often also label a laptop's screen as a monitor."""
    laptops = [b for c, b in boxes if c == "laptop"]
    return [(c, b) for c, b in boxes if c != "monitor" or all(iou(b, l) <= 0.5 for l in laptops)]


def write_labels(stem, boxes):
    """boxes: list of (class_name, (cx, cy, w, h)). Writes nothing if empty."""
    boxes = drop_laptop_monitors(boxes)
    if not boxes:
        return False
    (OUT / "labels").mkdir(parents=True, exist_ok=True)
    lines = [f"{CID[c]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for c, (cx, cy, w, h) in boxes]
    (OUT / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")
    return True


def fetch(url, dest):
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            break
        except OSError:
            if attempt == 2:
                raise
            time.sleep(30 * (attempt + 1))
    tmp.rename(dest)
    return dest


def openimages(max_samples=12000):
    os.environ.setdefault("FIFTYONE_DO_NOT_TRACK", "true")
    os.environ.setdefault("FIFTYONE_DATASET_ZOO_DIR", str(RAW / "fiftyone"))
    os.environ.setdefault("FIFTYONE_DATABASE_DIR", str(ROOT / ".fiftyone"))
    import fiftyone.zoo as foz

    ds = foz.load_zoo_dataset("open-images-v7", split="train", label_types=["detections"],
                              classes=list(OPENIMAGES), max_samples=max_samples, shuffle=True,
                              seed=51, dataset_name="scavscrap-openimages", overwrite=True)
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    counts = Counter()
    for s in ds.select_fields("ground_truth"):
        boxes = []
        for d in (s.ground_truth.detections if s.ground_truth else []):
            if d.label in OPENIMAGES and (b := to_yolo(*d.bounding_box, 1, 1)):
                boxes.append((OPENIMAGES[d.label], b))
        stem = "oi_" + Path(s.filepath).stem
        if write_labels(stem, boxes):
            dst = OUT / "images" / f"{stem}.jpg"
            if not dst.exists():
                os.link(s.filepath, dst)
            counts.update(c for c, _ in boxes)
    print("openimages boxes:", dict(counts))


def lvis():
    images, anns, non_exhaustive = {}, defaultdict(list), {}
    for split in ("train", "val"):
        z = fetch(f"https://dl.fbaipublicfiles.com/LVIS/lvis_v1_{split}.json.zip", RAW / "lvis" / f"lvis_v1_{split}.json.zip")
        with zipfile.ZipFile(z) as zf:
            data = json.loads(zf.read(f"lvis_v1_{split}.json"))
        cats = {c["id"]: LVIS[c["name"]] for c in data["categories"] if c["name"] in LVIS}
        missing = set(LVIS) - {c["name"] for c in data["categories"]}
        assert not missing, f"LVIS category names not found: {missing}"
        for im in data["images"]:
            images[im["id"]] = im
            non_exhaustive[im["id"]] = set(im.get("not_exhaustive_category_ids", [])) & cats.keys()
        for a in data["annotations"]:
            if a["category_id"] in cats:
                anns[a["image_id"]].append((cats[a["category_id"]], a["bbox"]))

    keep = [i for i, a in anns.items()
            if not non_exhaustive[i] and LVIS_REQUIRED & {c for c, _ in a}]
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    counts, failed = Counter(), 0

    def one(img_id):
        im = images[img_id]
        stem = f"lvis_{img_id:012d}"
        boxes = [(c, b) for c, bb in anns[img_id] if (b := to_yolo(*bb, im["width"], im["height"]))]
        try:
            fetch(im["coco_url"], OUT / "images" / f"{stem}.jpg")
        except OSError as e:
            print(f"  skip {stem}: {e}")
            return None
        write_labels(stem, boxes)
        return boxes

    with ThreadPoolExecutor(16) as ex:
        for boxes in ex.map(one, keep):
            if boxes is None:
                failed += 1
            else:
                counts.update(c for c, _ in boxes)
    print(f"lvis images: {len(keep) - failed} ({failed} failed) boxes:", dict(counts))


def objects365(max_patches=12):
    from PIL import Image, ImageDraw

    with open(fetch(O365_URL + "zhiyuan_objv2_val.json", RAW / "objects365" / "zhiyuan_objv2_val.json")) as f:
        data = json.load(f)
    cats = {c["id"]: c["name"] for c in data["categories"]}
    missing = (set(O365) | {O365_MASK}) - set(cats.values())
    assert not missing, f"Objects365 category names not found: {missing}"
    anns = defaultdict(list)
    for a in data["annotations"]:
        name = cats[a["category_id"]]
        if name in O365 or name == O365_MASK:
            anns[a["image_id"]].append((name, a["bbox"]))
    images = {im["id"]: im for im in data["images"]}
    del data

    wanted = {i for i, a in anns.items() if O365_REQUIRED & {O365.get(n) for n, _ in a}}
    by_patch = defaultdict(set)
    for i in wanted:
        fn = images[i]["file_name"]  # e.g. images/v1/patch0/objects365_v1_00023118.jpg
        by_patch[fn.split("/")[-3] + "/" + fn.split("/")[-2]].add(i)
    patches = sorted(by_patch, key=lambda p: -len(by_patch[p]))[:max_patches]
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    counts, n_imgs = Counter(), 0

    for patch in patches:
        ids = {Path(images[i]["file_name"]).name: i for i in by_patch[patch]}
        tar_path = fetch(f"{O365_URL}images/{patch}.tar.gz", RAW / "objects365" / f"{patch.replace('/', '_')}.tar.gz")
        with tarfile.open(tar_path) as tf:
            for m in tf:
                img_id = ids.get(Path(m.name).name)
                if img_id is None or not m.isfile():
                    continue
                im = images[img_id]
                stem = f"o365_{Path(m.name).stem}"
                img = Image.open(tf.extractfile(m)).convert("RGB")
                draw, boxes = ImageDraw.Draw(img), []
                for name, (x, y, w, h) in anns[img_id]:
                    if name == O365_MASK:
                        draw.rectangle([x, y, x + w, y + h], fill=(114, 114, 114))
                    elif b := to_yolo(x, y, w, h, im["width"], im["height"]):
                        boxes.append((O365[name], b))
                if write_labels(stem, boxes):
                    img.save(OUT / "images" / f"{stem}.jpg", quality=92)
                    counts.update(c for c, _ in boxes)
                    n_imgs += 1
        print(f"  {patch}: done")
    print(f"objects365 images: {n_imgs} from {len(patches)} patches, boxes:", dict(counts))


def roboflow(zip_path, *mappings):
    """Import a Roboflow YOLO export. mappings: 'Their Name=our_class'; unmapped classes are dropped."""
    from PIL import Image

    mapping = dict(m.rsplit("=", 1) for m in mappings)
    assert set(mapping.values()) <= set(CLASSES), f"unknown target class in {mapping}"
    with zipfile.ZipFile(zip_path) as zf:
        meta = yaml_names(zf.read("data.yaml").decode())
        unknown = set(mapping) - set(meta["names"])
        assert not unknown, f"not in this export's classes {meta['names']}: {unknown}"
        project = re.sub(r"\W+", "-", meta["project"] or Path(zip_path).stem).strip("-")
        labels = {n: zf.read(n).decode() for n in zf.namelist() if "/labels/" in n and n.endswith(".txt")}
        (OUT / "images").mkdir(parents=True, exist_ok=True)
        counts, n_imgs = Counter(), 0
        for n in zf.namelist():
            if "/images/" not in n or n.endswith("/"):
                continue
            label_name = n.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
            boxes = []
            for line in labels.get(label_name, "").splitlines():
                parts = line.split()
                if not parts or meta["names"][int(parts[0])] not in mapping:
                    continue
                if (xywh := yolo_row_xywh(list(map(float, parts[1:])))) and (b := to_yolo(*xywh, 1, 1)):
                    boxes.append((mapping[meta["names"][int(parts[0])]], b))
            stem = short_stem(f"rf_{project}_{Path(n).stem}")
            if write_labels(stem, boxes):
                with zf.open(n) as f:
                    Image.open(f).convert("RGB").save(OUT / "images" / f"{stem}.jpg", quality=95)
                counts.update(c for c, _ in boxes)
                n_imgs += 1
    print(f"roboflow {project}: {n_imgs} images, boxes:", dict(counts))


def roboflow_link(ref, key):
    """Signed zip URL for a YOLOv8 export, asking Roboflow to generate it first if needed."""
    url = f"https://api.roboflow.com/{ref}/yolov8?" + urllib.parse.urlencode({"api_key": key})
    for attempt in range(60):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)["export"]["link"]
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            # Errors are rebuilt from ref + status so the key-bearing URL never reaches the terminal or logs.
            if e.code in (401, 403) or (attempt == 0 and '"error"' in body and "export" not in body.lower()):
                raise RuntimeError(f"Roboflow {ref}: HTTP {e.code} {body}") from None
            if attempt == 0:
                try:
                    urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=60).close()
                except urllib.error.HTTPError as post:
                    raise RuntimeError(f"Roboflow {ref}: export request HTTP {post.code} "
                                       f"{post.read().decode(errors='replace')[:300]}") from None
        time.sleep(5)
    raise RuntimeError(f"Roboflow {ref}: export not ready after 5 minutes; rerun to retry")


def roboflow_download():
    """Download and import every ROBOFLOW_SETS export. Zips are cached in _raw/roboflow/ for reruns."""
    key = os.environ.get("ROBOFLOW_API_KEY")
    assert key, "set ROBOFLOW_API_KEY in the environment (roboflow.com > Settings > API Keys)"
    for ref, *mappings in ROBOFLOW_SETS:
        dest = RAW / "roboflow" / (ref.replace("/", "_") + ".zip")
        if not dest.exists():
            fetch(roboflow_link(ref, key), dest)
        roboflow(dest, *mappings)


def short_stem(stem, limit=100):
    """Windows paths cap at 260 chars. Keeps the part before '.rf.' (the split group key) stable."""
    if len(stem) <= limit:
        return stem
    base, _, rest = stem.partition(".rf.")
    base = f"{base[:limit - 40]}-{hashlib.sha1(base.encode()).hexdigest()[:10]}"
    return f"{base}.rf.{rest[:16]}" if rest else base


def yolo_row_xywh(coords):
    """Normalized YOLO box (cx cy w h) or polygon (x1 y1 x2 y2 ...) -> top-left x y w h, or None."""
    if len(coords) == 4:
        cx, cy, w, h = coords
        return cx - w / 2, cy - h / 2, w, h
    if len(coords) >= 6 and len(coords) % 2 == 0:
        xs, ys = coords[0::2], coords[1::2]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    return None


def yaml_names(text):
    """Read 'names' and roboflow 'project' from a Roboflow data.yaml without a YAML dependency."""
    names = re.search(r"^names:\s*\[(.*)\]", text, re.M)
    project = re.search(r"^\s+project:\s*(\S+)", text, re.M)
    return {"names": [s.strip().strip("'\"") for s in names.group(1).split(",")] if names else [],
            "project": project.group(1) if project else None}


def split():
    stems = sorted(p.stem for p in (OUT / "labels").glob("*.txt") if (OUT / "images" / f"{p.stem}.jpg").exists())
    for name, want_val in (("train", False), ("val", True)):
        # Roboflow augmentations share the name before ".rf."; keep them in one split.
        lines = [f"./images/{s}.jpg" for s in stems if is_val(s.split(".rf.")[0]) == want_val]
        (OUT / f"{name}.txt").write_text("\n".join(lines) + "\n")
        print(f"{name}: {len(lines)} images")
    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(CLASSES))
    (OUT / "data.yaml").write_text(f"train: train.txt\nval: val.txt\nnames:\n{names}\n")
    counts = Counter()
    for s in stems:
        for line in (OUT / "labels" / f"{s}.txt").read_text().split("\n"):
            if line:
                counts[CLASSES[int(line.split()[0])]] += 1
    print("total boxes per class:", {c: counts[c] for c in CLASSES})


def selftest():
    def r(b):
        return tuple(round(v, 6) for v in b)

    assert r(to_yolo(10, 20, 30, 40, 100, 200)) == (0.25, 0.2, 0.3, 0.2)
    assert r(to_yolo(0.1, 0.1, 0.2, 0.2, 1, 1)) == (0.2, 0.2, 0.2, 0.2)
    assert r(to_yolo(-10, 0, 20, 10, 100, 100)) == (0.05, 0.05, 0.1, 0.1)  # clipped at left edge
    assert to_yolo(100, 0, 10, 10, 100, 100) is None  # fully outside
    assert to_yolo(5, 5, 0, 10, 100, 100) is None  # zero width
    lap, mon_same, mon_far = (0.5, 0.5, 0.4, 0.4), (0.5, 0.48, 0.38, 0.36), (0.1, 0.1, 0.1, 0.1)
    kept = drop_laptop_monitors([("laptop", lap), ("monitor", mon_same), ("monitor", mon_far)])
    assert kept == [("laptop", lap), ("monitor", mon_far)]
    assert drop_laptop_monitors([("monitor", mon_same)]) == [("monitor", mon_same)]
    def r4(b):
        return tuple(round(v, 6) for v in b)

    assert r4(yolo_row_xywh([0.5, 0.5, 0.2, 0.4])) == (0.4, 0.3, 0.2, 0.4)
    assert r4(yolo_row_xywh([0.1, 0.2, 0.5, 0.2, 0.5, 0.6, 0.1, 0.6])) == (0.1, 0.2, 0.4, 0.4)
    assert yolo_row_xywh([0.1, 0.2, 0.3]) is None
    long_a, long_b = "rf_x_" + "a" * 150 + ".rf." + "1" * 32, "rf_x_" + "a" * 150 + ".rf." + "2" * 32
    sa, sb = short_stem(long_a), short_stem(long_b)
    assert len(sa) <= 100 and sa != sb and sa.split(".rf.")[0] == sb.split(".rf.")[0]
    assert short_stem("rf_x_short.rf.abc") == "rf_x_short.rf.abc"
    meta = yaml_names("names: ['DESKTOP PC', \"Monitors\"]\nroboflow:\n  project: desk-pc\n")
    assert meta == {"names": ["DESKTOP PC", "Monitors"], "project": "desk-pc"}
    assert is_val("oi_abc") == is_val("oi_abc")
    assert 10 < sum(is_val(f"x{i}") for i in range(1000)) / 10 < 20
    assert set(OPENIMAGES.values()) | set(LVIS.values()) | set(O365.values()) == set(CLASSES)  # every class has a source
    for ref, *mappings in ROBOFLOW_SETS:
        assert len(ref.split("/")) == 3 and ref.split("/")[2].isdigit(), ref
        assert mappings and all(m.rsplit("=", 1)[1] in CLASSES for m in mappings), ref
    assert CLASSES[:11] == ["laptop", "desktop_computer_tower", "monitor", "printer", "projector",
                            "keyboard", "mouse", "phone", "tablet", "tv", "router"]  # v2 IDs unchanged
    print("selftest ok")


if __name__ == "__main__":
    {"selftest": selftest, "openimages": openimages, "lvis": lvis, "objects365": objects365,
     "roboflow": roboflow, "roboflow-download": roboflow_download, "split": split}[sys.argv[1]](*sys.argv[2:])
