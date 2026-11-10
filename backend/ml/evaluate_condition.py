"""Evaluate a YOLO condition classifier and fit validation-set temperature scaling."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / "ml" / "weights" / "condition_yolo11_candidate.pt"
DEFAULT_VAL = ROOT / "ml" / "datasets" / "condition_real" / "val"
DEFAULT_TEMPERATURE = ROOT / "ml" / "weights" / "temperature.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CLASS_MAP = {
    "like_new": "resell",
    "good": "resell",
    "fair": "refurbish",
    "poor": "recycle",
    "damaged": "recycle",
}


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def _true_class(folder: str, model_classes: list[str]) -> str | None:
    normalized = _normalize(folder)
    mapped = CLASS_MAP.get(normalized, normalized)
    return mapped if mapped in model_classes else None


def _validation_samples(val_dir: Path, class_names: list[str]) -> tuple[list[Path], list[int]]:
    samples: list[tuple[Path, int]] = []
    for folder in sorted(path for path in val_dir.iterdir() if path.is_dir()):
        true_class = _true_class(folder.name, class_names)
        if true_class is None:
            continue
        true_index = class_names.index(true_class)
        for image in sorted(folder.iterdir()):
            if image.is_file() and image.suffix.lower() in IMAGE_SUFFIXES:
                samples.append((image, true_index))
    if not samples:
        raise ValueError(f"No validation images with labels matching {class_names} in {val_dir}")
    return [sample[0] for sample in samples], [sample[1] for sample in samples]


def _fit_temperature(probabilities, labels):
    import torch

    logits = torch.log(probabilities.clamp_min(1e-12))
    candidates = torch.arange(0.1, 10.001, 0.01, dtype=torch.float64)
    expanded = logits.to(torch.float64).unsqueeze(0) / candidates[:, None, None]
    calibrated = expanded.softmax(dim=2)
    targets = torch.tensor(labels, dtype=torch.long).view(1, -1, 1)
    nll_by_temperature = -calibrated.gather(2, targets.expand(len(candidates), -1, -1)).squeeze(2).clamp_min(1e-12).log().mean(dim=1)
    best_index = int(nll_by_temperature.argmin())
    return float(candidates[best_index]), float(nll_by_temperature[best_index])


def _reliability_rows(probabilities, labels, bins: int = 10) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    confidence, predictions = probabilities.max(dim=1)
    total = len(labels)
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [
            row
            for row in range(total)
            if lower <= float(confidence[row]) < upper
            or (index == bins - 1 and float(confidence[row]) == 1.0)
        ]
        if selected:
            rows.append(
                {
                    "bin_lower": lower,
                    "bin_upper": upper,
                    "count": len(selected),
                    "mean_confidence": sum(float(confidence[row]) for row in selected) / len(selected),
                    "accuracy": sum(int(predictions[row]) == labels[row] for row in selected) / len(selected),
                }
            )
        else:
            rows.append(
                {
                    "bin_lower": lower,
                    "bin_upper": upper,
                    "count": 0,
                    "mean_confidence": 0.0,
                    "accuracy": 0.0,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--val", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--device", default=None)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ml" / "runs" / "condition_eval")
    parser.add_argument("--temperature-output", type=Path, default=DEFAULT_TEMPERATURE)
    args = parser.parse_args()

    if not args.weights.is_file():
        raise FileNotFoundError(f"Model checkpoint not found: {args.weights}")
    if not args.val.is_dir():
        raise FileNotFoundError(f"Validation folder not found: {args.val}")

    import matplotlib.pyplot as plt
    import torch
    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    names = getattr(model, "names", {}) or {}
    class_names = [
        _normalize(str(names[index]))
        for index in range(len(names))
    ]
    if len(class_names) not in {3, 5}:
        raise ValueError(f"Expected a 3- or 5-class condition model, found {class_names}")
    images, labels = _validation_samples(args.val, class_names)
    results = model.predict(
        [str(image) for image in images],
        verbose=False,
        device=args.device,
    )
    if len(results) != len(images):
        raise RuntimeError("YOLO returned a different number of validation predictions than inputs.")
    probabilities = torch.tensor(
        [result.probs.data.tolist() for result in results],
        dtype=torch.float64,
    )
    temperature, fitted_nll = _fit_temperature(probabilities, labels)
    scaled_logits = torch.log(probabilities.clamp_min(1e-12)) / temperature
    calibrated = scaled_logits.softmax(dim=1)
    predictions = calibrated.argmax(dim=1).tolist()

    matrix = [[0 for _ in class_names] for _ in class_names]
    for true_index, predicted_index in zip(labels, predictions):
        matrix[true_index][predicted_index] += 1
    accuracy = sum(matrix[index][index] for index in range(len(class_names))) / len(labels)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = args.output_dir / "confusion_matrix.png"
    figure, axis = plt.subplots(figsize=(max(5, len(class_names)), max(4, len(class_names) - 1)))
    axis.imshow(matrix, cmap="Blues")
    axis.set(
        xticks=range(len(class_names)),
        yticks=range(len(class_names)),
        xticklabels=class_names,
        yticklabels=class_names,
        xlabel="Predicted",
        ylabel="Actual",
        title=f"Validation confusion matrix (accuracy {accuracy:.3f})",
    )
    plt.setp(axis.get_xticklabels(), rotation=35, ha="right", rotation_mode="anchor")
    for row in range(len(class_names)):
        for column in range(len(class_names)):
            axis.text(column, row, str(matrix[row][column]), ha="center", va="center")
    figure.tight_layout()
    figure.savefig(matrix_path, dpi=160)
    plt.close(figure)

    rows = _reliability_rows(calibrated, labels)
    reliability_path = args.output_dir / "reliability.csv"
    with reliability_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    temperature_path = args.temperature_output
    temperature_path.parent.mkdir(parents=True, exist_ok=True)
    temperature_path.write_text(
        json.dumps(
            {
                "temperature": temperature,
                "validation_nll": fitted_nll,
                "validation_samples": len(labels),
                "weights": str(args.weights.resolve()),
                "fitted_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Validation samples: {len(labels)}")
    print(f"Top-1 accuracy after calibration: {accuracy:.4f}")
    print(f"Best temperature: {temperature:.2f} (NLL={fitted_nll:.5f})")
    print("Confusion matrix (rows=true, columns=predicted):")
    print("class," + ",".join(class_names))
    for label, row in zip(class_names, matrix):
        print(label + "," + ",".join(str(value) for value in row))
    print("Reliability table (calibrated):")
    for row in rows:
        print(
            f"{row['bin_lower']:.1f}-{row['bin_upper']:.1f} "
            f"n={row['count']} confidence={row['mean_confidence']:.3f} accuracy={row['accuracy']:.3f}"
        )
    print(f"Confusion matrix image: {matrix_path}")
    print(f"Reliability CSV: {reliability_path}")
    print(f"Temperature configuration: {temperature_path}")


if __name__ == "__main__":
    main()
