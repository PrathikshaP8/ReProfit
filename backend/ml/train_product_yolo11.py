"""Train and validate the product image classifier.

The dataset must use Ultralytics classification folders:

    <dataset>/train/<class>/*.{jpg,png,...}
    <dataset>/val/<class>/*.{jpg,png,...}

Run from the backend directory. Training artifacts, including best.pt, are
written to a new run directory and are not copied over live model weights.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "ml" / "datasets" / "product"
DEFAULT_PROJECT = ROOT / "ml" / "runs"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _classes(data_dir: Path, split: str) -> dict[str, int]:
    split_dir = data_dir / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"Missing {split} split directory: {split_dir}")
    result = {}
    for folder in sorted(path for path in split_dir.iterdir() if path.is_dir()):
        count = sum(
            1
            for image in folder.iterdir()
            if image.is_file() and image.suffix.lower() in IMAGE_SUFFIXES
        )
        if count:
            result[folder.name] = count
    if not result:
        raise FileNotFoundError(f"No class folders with images found in {split_dir}")
    return result


def validate_dataset(data_dir: Path) -> dict[str, dict[str, int]]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {data_dir}")
    train = _classes(data_dir, "train")
    val = _classes(data_dir, "val")
    if len(train) < 2:
        raise ValueError("Product classification requires at least two train classes")
    if set(train) != set(val):
        raise ValueError(
            "Train and val class names must match; "
            f"train={sorted(train)}, val={sorted(val)}"
        )
    return {"train": train, "val": val}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--model", default="yolo11n-cls.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="product_roboflow")
    parser.add_argument("--device", default=None, help="Ultralytics device, e.g. cpu or 0")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Check and count the dataset without starting training",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    counts = validate_dataset(args.data)
    print(f"Validated product classification dataset: {args.data}")
    for split, classes in counts.items():
        print(f"{split}: " + ", ".join(f"{name}={count}" for name, count in classes.items()))
    if args.validate_only:
        return

    from ultralytics import YOLO

    model = YOLO(args.model)
    train_options = {
        "data": str(args.data),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "workers": args.workers,
        "project": str(args.project),
        "name": args.name,
        "exist_ok": False,
    }
    if args.device is not None:
        train_options["device"] = args.device
    results = model.train(**train_options)
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        raise FileNotFoundError(f"Training did not produce the expected checkpoint: {best}")

    print(f"Evaluating best checkpoint on validation data: {best}")
    best_model = YOLO(str(best))
    best_model.val(
        data=str(args.data),
        split="val",
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
    )
    print(f"Training and validation complete. Candidate checkpoint: {best}")
    print("This checkpoint is not connected to live inference.")


if __name__ == "__main__":
    main()
