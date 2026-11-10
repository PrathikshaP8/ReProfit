"""Shared validation for Ultralytics YOLO object-detection datasets."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _names_by_id(names: Any) -> dict[int, str]:
    if isinstance(names, list):
        return dict(enumerate(str(name) for name in names))
    if isinstance(names, dict):
        try:
            return {int(index): str(name) for index, name in names.items()}
        except (TypeError, ValueError) as error:
            raise ValueError("Detection class names must have integer indices") from error
    raise ValueError("Detection dataset YAML must define class names as a list or mapping")


def _resolve_split(data: dict[str, Any], data_yaml: Path, split: str) -> Path:
    split_value = data.get(split)
    if not isinstance(split_value, str) or not split_value.strip():
        raise ValueError(f"{data_yaml} must define a non-empty {split}: image path")
    dataset_root = data.get("path", data_yaml.parent)
    if not isinstance(dataset_root, (str, Path)):
        raise ValueError(f"{data_yaml} has an invalid 'path' value")
    root = Path(dataset_root)
    if not root.is_absolute():
        root = (data_yaml.parent / root).resolve()

    image_path = Path(split_value)
    if image_path.is_absolute():
        candidates = [image_path]
    else:
        candidates = [(root / image_path).resolve()]
        if image_path.parts and image_path.parts[0] == "..":
            candidates.append((data_yaml.parent / Path(*image_path.parts[1:])).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"{split} image path from {data_yaml} does not exist; checked {candidates}"
    )


def _image_files(split_path: Path) -> list[Path]:
    if split_path.is_dir():
        return sorted(
            path
            for path in split_path.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
    if split_path.is_file() and split_path.suffix.lower() == ".txt":
        image_paths = []
        for line in split_path.read_text(encoding="utf-8").splitlines():
            entry = line.strip()
            if not entry:
                continue
            path = Path(entry)
            if not path.is_absolute():
                path = (split_path.parent / path).resolve()
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                raise FileNotFoundError(f"Invalid image entry in {split_path}: {entry}")
            image_paths.append(path)
        return image_paths
    raise ValueError(f"Expected an image directory or image-list .txt file: {split_path}")


def _labels_path(image: Path) -> Path:
    parts = list(image.parts)
    image_parts = [part.lower() for part in parts]
    if "images" in image_parts:
        index = image_parts.index("images")
        parts[index] = "labels"
        return Path(*parts).with_suffix(".txt")
    return image.with_suffix(".txt")


def _validate_labels(
    images: list[Path],
    class_names: dict[int, str],
    split: str,
) -> tuple[int, int, int]:
    annotated_images = 0
    box_count = 0
    polygon_count = 0
    for image in images:
        label_file = _labels_path(image)
        if not label_file.is_file():
            raise FileNotFoundError(f"Missing {split} YOLO label file for {image}: {label_file}")
        lines = [
            line.split()
            for line in label_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        annotation_types: set[str] = set()
        if lines:
            annotated_images += 1
        for line_number, values in enumerate(lines, start=1):
            if len(values) == 5:
                annotation_type = "box"
            elif len(values) >= 7 and (len(values) - 1) % 2 == 0:
                annotation_type = "polygon"
            else:
                raise ValueError(
                    f"{label_file}:{line_number}: expected a YOLO box row "
                    "'class_id x_center y_center width height' or a polygon row "
                    "'class_id x1 y1 x2 y2 ...' with at least 3 points"
                )
            try:
                class_id = int(values[0])
                coords = [float(value) for value in values[1:]]
            except ValueError as error:
                raise ValueError(f"{label_file}:{line_number}: non-numeric annotation") from error
            if class_id not in class_names:
                raise ValueError(f"{label_file}:{line_number}: unknown class id {class_id}")
            if any(
                not math.isfinite(coordinate) or not -0.01 <= coordinate <= 1.01
                for coordinate in coords
            ):
                raise ValueError(
                    f"{label_file}:{line_number}: normalized coordinates must be "
                    "finite and within Ultralytics' [-0.01, 1.01] tolerance"
                )
            if annotation_type == "box" and (coords[2] <= 0 or coords[3] <= 0):
                raise ValueError(f"{label_file}:{line_number}: box width and height must be positive")
            if annotation_type == "polygon":
                x_coordinates = coords[::2]
                y_coordinates = coords[1::2]
                if (
                    max(x_coordinates) <= min(x_coordinates)
                    or max(y_coordinates) <= min(y_coordinates)
                ):
                    raise ValueError(f"{label_file}:{line_number}: polygon must have positive area")
                polygon_count += 1
            annotation_types.add(annotation_type)
            box_count += 1
        if len(annotation_types) > 1:
            raise ValueError(
                f"{label_file}: mixes YOLO box and polygon rows; Ultralytics "
                "detection training does not support mixed annotation formats "
                "within one label file"
            )
    if not images:
        raise FileNotFoundError(f"No images found in the {split} split")
    if box_count == 0:
        raise ValueError(f"The {split} split has no annotated detection boxes")
    return annotated_images, box_count, polygon_count


def validate_detection_dataset(
    data_yaml: Path,
    *,
    forbidden_class_tokens: set[str] | None = None,
) -> dict[str, Any]:
    """Validate YOLO detection data and return class names and split counts."""
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Detection dataset YAML does not exist: {data_yaml}")

    import yaml

    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {data_yaml}")
    class_names = _names_by_id(data.get("names"))
    if not class_names:
        raise ValueError(f"{data_yaml} defines no detection classes")

    forbidden_tokens = {token.lower() for token in forbidden_class_tokens or set()}
    forbidden = [
        name
        for name in class_names.values()
        if forbidden_tokens.intersection(
            name.lower().replace("-", " ").replace("_", " ").split()
        )
    ]
    if forbidden:
        raise ValueError(
            f"Dataset contains forbidden class names {forbidden}; "
            "use a dataset with the intended product taxonomy"
        )

    summary: dict[str, Any] = {"classes": class_names}
    for split in ("train", "val"):
        image_paths = _image_files(_resolve_split(data, data_yaml, split))
        annotated_images, boxes, polygons = _validate_labels(image_paths, class_names, split)
        summary[split] = {
            "images": len(image_paths),
            "annotated_images": annotated_images,
            "boxes": boxes,
            "polygons": polygons,
        }
    if data.get("test"):
        image_paths = _image_files(_resolve_split(data, data_yaml, "test"))
        annotated_images, boxes, polygons = _validate_labels(image_paths, class_names, "test")
        summary["test"] = {
            "images": len(image_paths),
            "annotated_images": annotated_images,
            "boxes": boxes,
            "polygons": polygons,
        }
    return summary
