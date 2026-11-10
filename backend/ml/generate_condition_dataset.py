"""Build a small YOLO11 classification dataset for product condition.

Real return photos are used as bases, then class-specific wear is painted on
so Like New / Good / Fair / Poor / Damaged are visually distinct.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "ml" / "datasets" / "condition_synthetic"
UPLOADS = ROOT / "uploads"
SIZE = (224, 224)
CLASSES = ("like_new", "good", "fair", "poor", "damaged")

TRAIN_PER_CLASS = 80
VAL_PER_CLASS = 16


def _labeled_bases(images: list[tuple[Path, Image.Image]]) -> dict[str, list[Image.Image]]:
    labeled: dict[str, list[Image.Image]] = {name: [] for name in CLASSES}
    for path, image in images:
        key = path.name.lower()
        if "hp_b" in key:
            labeled["damaged"].append(image)
        elif "levi" in key:
            labeled["like_new"].append(image)
        elif "155313" in key:
            labeled["like_new"].append(image)
        elif "155538" in key:
            labeled["fair"].append(image)
            labeled["good"].append(image)
        else:
            labeled["good"].append(image)
    return labeled


def _load_bases() -> list[tuple[Path, Image.Image]]:
    loaded: list[tuple[Path, Image.Image]] = []
    if UPLOADS.exists():
        for path in UPLOADS.iterdir():
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            try:
                loaded.append((path, Image.open(path).convert("RGB")))
            except OSError:
                continue
    if len(loaded) < 2:
        raise ValueError(
            f"At least two distinct source images are required to split without leakage; found {len(loaded)}."
        )
    return loaded


def _synthetic_product(rng: random.Random) -> Image.Image:
    image = Image.new(
        "RGB",
        SIZE,
        (rng.randint(180, 240), rng.randint(180, 240), rng.randint(180, 240)),
    )
    draw = ImageDraw.Draw(image)
    color = (rng.randint(20, 90), rng.randint(20, 90), rng.randint(20, 120))
    shape = rng.choice(["phone", "box", "circle"])
    if shape == "phone":
        x0, y0 = 70, 30
        draw.rounded_rectangle((x0, y0, x0 + 84, y0 + 164), radius=16, fill=color)
        draw.rounded_rectangle((x0 + 10, y0 + 22, x0 + 74, y0 + 140), radius=6, fill=(30, 30, 35))
    elif shape == "box":
        draw.rounded_rectangle((40, 50, 184, 174), radius=12, fill=color)
        draw.rectangle((50, 60, 174, 164), outline=(255, 255, 255), width=2)
    else:
        draw.ellipse((48, 48, 176, 176), fill=color)
        draw.ellipse((78, 78, 146, 146), fill=(220, 220, 220))
    return image


def _fit(image: Image.Image) -> Image.Image:
    return ImageOps.fit(image, SIZE, method=Image.Resampling.BILINEAR)


def _jitter(image: Image.Image, rng: random.Random) -> Image.Image:
    image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.9, 1.12))
    image = ImageEnhance.Color(image).enhance(rng.uniform(0.85, 1.15))
    image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.9, 1.12))
    if rng.random() < 0.5:
        image = ImageOps.mirror(image)
    angle = rng.uniform(-8, 8)
    image = image.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=(230, 230, 230))
    return _fit(image)


def _scratches(image: Image.Image, rng: random.Random, count: int, width: int) -> Image.Image:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for _ in range(count):
        color = (rng.randint(20, 70),) * 3
        x1, y1 = rng.randint(0, SIZE[0]), rng.randint(0, SIZE[1])
        x2, y2 = x1 + rng.randint(-90, 90), y1 + rng.randint(-40, 40)
        draw.line((x1, y1, x2, y2), fill=color, width=width)
    return overlay


def _stains(image: Image.Image, rng: random.Random, count: int, radius: int) -> Image.Image:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay, "RGBA")
    for _ in range(count):
        x, y = rng.randint(10, SIZE[0] - 10), rng.randint(10, SIZE[1] - 10)
        r = rng.randint(max(6, radius // 2), radius)
        color = (rng.randint(40, 90), rng.randint(25, 60), rng.randint(15, 40), rng.randint(90, 160))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
    return overlay.convert("RGB")


def _crack(image: Image.Image, rng: random.Random) -> Image.Image:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    x, y = rng.randint(40, 160), rng.randint(40, 160)
    for _ in range(rng.randint(4, 8)):
        nx, ny = x + rng.randint(-50, 50), y + rng.randint(-50, 50)
        draw.line((x, y, nx, ny), fill=(10, 10, 10), width=rng.randint(2, 4))
        x, y = nx, ny
    draw.ellipse((x - 12, y - 10, x + 18, y + 16), fill=(15, 15, 15))
    return overlay


def _apply_condition(image: Image.Image, label: str, rng: random.Random) -> Image.Image:
    image = _jitter(image, rng)
    if label == "like_new":
        return image
    if label == "good":
        image = ImageEnhance.Color(image).enhance(0.92)
        if rng.random() < 0.4:
            image = _scratches(image, rng, count=2, width=1)
        return image.filter(ImageFilter.SMOOTH)
    if label == "fair":
        image = ImageEnhance.Color(image).enhance(0.8)
        image = ImageEnhance.Contrast(image).enhance(0.9)
        image = _scratches(image, rng, count=6, width=1)
        image = _stains(image, rng, count=2, radius=14)
        return image
    if label == "poor":
        image = ImageEnhance.Color(image).enhance(0.65)
        image = ImageEnhance.Brightness(image).enhance(0.85)
        image = _scratches(image, rng, count=14, width=2)
        image = _stains(image, rng, count=5, radius=22)
        return image.filter(ImageFilter.SMOOTH)
    image = ImageEnhance.Color(image).enhance(0.5)
    image = ImageEnhance.Brightness(image).enhance(0.72)
    image = _scratches(image, rng, count=18, width=3)
    image = _stains(image, rng, count=7, radius=28)
    image = _crack(image, rng)
    return image.filter(ImageFilter.SHARPEN)


def generate(seed: int = 24) -> Path:
    rng = random.Random(seed)
    loaded = _load_bases()
    if DATA_DIR.exists() and any(
        path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        for path in DATA_DIR.rglob("*")
    ):
        raise FileExistsError(f"Refusing to overwrite existing synthetic data under {DATA_DIR}")
    rng.shuffle(loaded)
    val_count = max(1, round(len(loaded) * 0.2))
    split_sources = {
        "train": loaded[val_count:],
        "val": loaded[:val_count],
    }
    labeled_by_split = {
        split: _labeled_bases(sources)
        for split, sources in split_sources.items()
    }
    for split, count in (("train", TRAIN_PER_CLASS), ("val", VAL_PER_CLASS)):
        bases = [image for _, image in split_sources[split]]
        labeled = labeled_by_split[split]
        for label in CLASSES:
            folder = DATA_DIR / split / label
            folder.mkdir(parents=True, exist_ok=True)
            for index in range(count):
                source_key = ""
                real_pool = labeled.get(label) or []
                use_real = bool(real_pool) and rng.random() < 0.55
                if use_real:
                    source_path, source_image = real_pool[rng.randrange(len(real_pool))]
                    source_key = source_path.stem
                    source = _fit(source_image)
                    sample = _jitter(source, rng)
                elif rng.random() < 0.7:
                    source_path, source_image = split_sources[split][rng.randrange(len(bases))]
                    source_key = source_path.stem
                    source = _fit(source_image)
                    sample = _apply_condition(source, label, rng)
                else:
                    source_key = f"painted_{split}_{label}_{index:03d}"
                    sample = _apply_condition(_synthetic_product(rng), label, rng)
                output_path = folder / f"{label}__{source_key}__{split}__{index:03d}.jpg"
                if output_path.exists():
                    raise FileExistsError(f"Refusing to overwrite generated image: {output_path}")
                sample.save(output_path, quality=rng.randint(78, 95))
    return DATA_DIR


if __name__ == "__main__":
    output = generate()
    print(f"Wrote condition dataset to {output}")
