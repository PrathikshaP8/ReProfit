"""Train a YOLO11 object detector for e-waste/product categories.

Use a Roboflow object-detection export with data.yaml, train/val image splits,
and YOLO bounding-box labels. Checkpoint output is isolated under a new run
directory and is not connected to live inference.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from yolo_detection_dataset import validate_detection_dataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = ROOT / "ml" / "runs"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Path to the Roboflow YOLO data.yaml")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="product_detector_roboflow")
    parser.add_argument("--device", default=None, help="Ultralytics device, e.g. cpu or 0")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Check classes, image counts, and box annotations without training",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = validate_detection_dataset(args.data)
    print(f"Validated product detection dataset: {args.data}")
    print(f"Classes: {summary['classes']}")
    for split in ("train", "val", "test"):
        if split not in summary:
            continue
        details = summary[split]
        print(
            f"{split}: {details['images']} images, "
            f"{details['annotated_images']} annotated, {details['boxes']} objects "
            f"({details['polygons']} polygon annotations)"
        )
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
    YOLO(str(best)).val(
        data=str(args.data),
        split="val",
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
    )
    print(f"Training and validation complete. Candidate checkpoint: {best}")
    print("This detector is not connected to live inference.")


if __name__ == "__main__":
    main()
