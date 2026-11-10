"""Train an isolated YOLO11 detector for visible laptop damage.

The dataset must contain laptop-only images and YOLO bounding-box annotations.
This candidate is kept separate from product recognition and the existing
condition classifier; it is not connected to live inference.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from yolo_detection_dataset import validate_detection_dataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = ROOT / "ml" / "runs"
MOBILE_CLASS_TOKENS = {"mobile", "phone", "smartphone", "cellphone"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Path to the Roboflow YOLO data.yaml")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument(
        "--fraction",
        type=float,
        default=1.0,
        help="Fraction of the training split to use (0 < fraction <= 1)",
    )
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="laptop_damage_roboflow")
    parser.add_argument("--device", default=None, help="Ultralytics device, e.g. cpu or 0")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Check class names, image counts, and YOLO boxes without training",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not 0 < args.fraction <= 1:
        raise ValueError("--fraction must be greater than 0 and at most 1")
    summary = validate_detection_dataset(
        args.data,
        forbidden_class_tokens=MOBILE_CLASS_TOKENS,
    )
    print(f"Validated laptop damage detection dataset: {args.data}")
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
        "fraction": args.fraction,
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
        device=args.device,
        plots=False,
        project=str(args.project / "evaluations"),
        name=f"{args.name}_val",
        exist_ok=False,
    )
    print(f"Training and validation complete. Candidate checkpoint: {best}")
    print("This detector is not connected to live inference.")


if __name__ == "__main__":
    main()
