"""Train an isolated three-way condition classifier from real labeled images.

The primary dataset must use ``train/<condition>/`` and ``val/<condition>/``
folders. Five source labels are mapped to the three recommendation classes.
The legacy painted dataset is never used as the primary dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "ml" / "datasets" / "condition_real"
LEGACY_PAINTED_DATA = ROOT / "ml" / "datasets" / "condition"
DEFAULT_OUTPUT = ROOT / "ml" / "weights" / "condition_yolo11_candidate.pt"
PRODUCTION_WEIGHTS = ROOT / "ml" / "weights" / "condition_yolo11.pt"
RUNS_DIR = ROOT / "ml" / "runs"

SOURCE_TO_TARGET = {
    "like_new": "resell",
    "good": "resell",
    "fair": "refurbish",
    "poor": "recycle",
    "damaged": "recycle",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _condition_folder(path: Path) -> str | None:
    key = path.name.strip().lower().replace("-", "_").replace(" ", "_")
    return key if key in SOURCE_TO_TARGET else None


def _images(folder: Path) -> list[Path]:
    return sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ) if folder.is_dir() else []


def _source_identifier(path: Path) -> str:
    stem = path.stem.casefold()
    for label in sorted(SOURCE_TO_TARGET, key=len, reverse=True):
        stem = re.sub(rf"^{re.escape(label)}(?:__|_|-)", "", stem)
    stem = re.sub(r"(?i)(?:__|_|-)(?:train|valid|val|test)(?:__|_|-)?\d*$", "", stem)
    stem = re.sub(r"(?i)^(?:train|valid|val|test)(?:__|_|-)?\d*$", "", stem)
    stem = re.sub(r"(?i)(?:__|_|-)(?:aug|copy|repeat)[_-]?\d+.*$", "", stem)
    return stem.strip("_")


def _normalized_source_path(path: Path) -> str:
    source_id = _source_identifier(path)
    if not source_id:
        raise ValueError(f"Cannot derive a source-image identifier from filename: {path.name}")
    return source_id


def _image_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_split(data_dir: Path, split: str) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    split_dir = data_dir / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"Missing {split} dataset folder: {split_dir}")
    for folder in sorted(split_dir.iterdir()):
        source_class = _condition_folder(folder)
        if source_class:
            grouped[SOURCE_TO_TARGET[source_class]].extend(_images(folder))
    return dict(grouped)


def _validate_data(data_dir: Path) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Real labeled dataset not found: {data_dir}")
    resolved = data_dir.resolve()
    if resolved == LEGACY_PAINTED_DATA.resolve() or "synthetic" in str(resolved).casefold():
        raise ValueError(
            "The painted/synthetic dataset cannot be the primary training data. "
            f"Use real labeled images in {DEFAULT_DATA}, with --synthetic-data only for capped augmentation."
        )
    train = _collect_split(data_dir, "train")
    val = _collect_split(data_dir, "val")
    targets = ("resell", "refurbish", "recycle")
    if any(not train.get(label) for label in targets):
        raise ValueError(f"Primary training data must contain all mapped classes: {targets}")
    if any(not val.get(label) for label in targets):
        raise ValueError(f"Validation data must contain all mapped classes: {targets}")

    train_ids = {
        _normalized_source_path(path)
        for images in train.values()
        for path in images
    }
    val_ids = {
        _normalized_source_path(path)
        for images in val.values()
        for path in images
    }
    overlap = train_ids & val_ids
    train_hashes = {
        _image_digest(path)
        for images in train.values()
        for path in images
    }
    val_hashes = {
        _image_digest(path)
        for images in val.values()
        for path in images
    }
    if overlap or train_hashes & val_hashes:
        examples = sorted(overlap)[:5]
        raise ValueError(
            "Train/validation source leakage detected; split by source image/product "
            f"before training. Shared source examples: {examples}"
        )
    return train, val


def _copy_images(images: list[Path], destination: Path, prefix: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(images):
        target = destination / f"{prefix}_{index:05d}{source.suffix.lower()}"
        shutil.copy2(source, target)


def _stage_dataset(
    train: dict[str, list[Path]],
    val: dict[str, list[Path]],
    synthetic_data: Path | None,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = RUNS_DIR / f"condition_data_{stamp}"
    if staging.exists():
        raise FileExistsError(f"Refusing to reuse existing staged dataset: {staging}")

    train_stage = staging / "train"
    val_stage = staging / "val"
    for label, images in train.items():
        target_count = max(len(class_images) for class_images in train.values())
        _copy_images(images, train_stage / label, f"real_{label}")
        for index in range(len(images), target_count):
            source = images[(index - len(images)) % len(images)]
            destination = train_stage / label / f"oversample_{label}_{index:05d}{source.suffix.lower()}"
            shutil.copy2(source, destination)
    for label, images in val.items():
        _copy_images(images, val_stage / label, f"val_{label}")

    if synthetic_data is not None:
        synthetic_train = _collect_split(synthetic_data, "train")
        available = [(label, path) for label, paths in synthetic_train.items() for path in paths]
        balanced_real_count = sum(
            max(len(images) for images in train.values())
            for _ in train
        )
        maximum_synthetic = balanced_real_count // 4
        available.sort(key=lambda item: (item[0], item[1].name))
        selected = available[:maximum_synthetic]
        for index, (label, source) in enumerate(selected):
            target = train_stage / label / f"synthetic_{label}_{index:05d}{source.suffix.lower()}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if available and not selected:
            raise ValueError("The 20% synthetic-data cap leaves no synthetic images eligible.")
        print(
            f"Added {len(selected)} optional synthetic images "
            f"({len(selected) / max(balanced_real_count + len(selected), 1):.1%} of staged training data)."
        )
    return staging


def _evaluate(model, val_dir: Path) -> float:
    names = getattr(model, "names", {}) or {}
    class_names = [str(names[index]) for index in range(len(names))]
    matrix = [[0 for _ in class_names] for _ in class_names]
    class_to_index = {name: index for index, name in enumerate(class_names)}
    images: list[tuple[Path, int]] = []
    for true_class in class_names:
        for path in _images(val_dir / true_class):
            images.append((path, class_to_index[true_class]))
    if not images:
        raise ValueError("Validation split contains no images.")
    results = model.predict([str(path) for path, _ in images], verbose=False)
    if len(results) != len(images):
        raise RuntimeError("YOLO returned a different number of validation predictions than inputs.")
    correct = 0
    for result, (_, true_index) in zip(results, images):
        predicted_index = int(result.probs.top1)
        matrix[true_index][predicted_index] += 1
        correct += predicted_index == true_index

    accuracy = correct / len(images)
    print("Validation confusion matrix (rows=true, columns=predicted):")
    print("class," + ",".join(class_names))
    for label, row in zip(class_names, matrix):
        print(label + "," + ",".join(str(value) for value in row))
    print("Per-class precision/recall:")
    for index, label in enumerate(class_names):
        true_positive = matrix[index][index]
        predicted_count = sum(matrix[row][index] for row in range(len(class_names)))
        actual_count = sum(matrix[index])
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / actual_count if actual_count else 0.0
        print(f"  {label}: precision={precision:.3f}, recall={recall:.3f}")
    print(f"Validation top-1 accuracy: {accuracy:.3f}")
    if accuracy < 0.70:
        print("WARNING: validation top-1 is below 0.70; do not promote this candidate.")
    return accuracy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Real labeled five-class dataset.")
    parser.add_argument("--synthetic-data", type=Path, help="Optional synthetic dataset; capped at 20% of training.")
    parser.add_argument("--device", default=None, help="Ultralytics device, e.g. 0, 0,1, or cpu.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Separate candidate checkpoint output.")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()

    output = args.output.resolve()
    if output == PRODUCTION_WEIGHTS.resolve():
        raise ValueError(f"Refusing to overwrite production weights: {PRODUCTION_WEIGHTS}")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing candidate weights: {output}")
    train, val = _validate_data(args.data)
    if args.synthetic_data:
        if not args.synthetic_data.is_dir():
            raise FileNotFoundError(f"Synthetic augmentation dataset not found: {args.synthetic_data}")
        if args.synthetic_data.resolve() == args.data.resolve():
            raise ValueError("Primary and synthetic datasets must be separate directories.")

    import torch
    from ultralytics import YOLO

    device = args.device or ("0" if torch.cuda.is_available() else "cpu")
    staging = _stage_dataset(train, val, args.synthetic_data)
    model = YOLO("yolo11s-cls.pt")
    results = model.train(
        data=str(staging),
        epochs=args.epochs,
        patience=15,
        imgsz=224,
        batch=args.batch,
        workers=args.workers,
        pretrained=True,
        optimizer="AdamW",
        lr0=0.001,
        cos_lr=True,
        label_smoothing=0.1,
        degrees=10,
        translate=0.1,
        scale=0.3,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,
        erasing=0.3,
        auto_augment="randaugment",
        device=device,
        project=str(RUNS_DIR),
        name=f"condition_yolo11s_{datetime.now():%Y%m%d_%H%M%S}",
        exist_ok=False,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        raise FileNotFoundError(f"Training completed without a best checkpoint: {best}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, output)
    candidate = YOLO(str(output))
    _evaluate(candidate, staging / "val")
    print(f"Candidate weights saved to: {output}")
    print(f"Staged reproducible dataset saved to: {staging}")
    print(f"Training run saved to: {results.save_dir}")


if __name__ == "__main__":
    main()
