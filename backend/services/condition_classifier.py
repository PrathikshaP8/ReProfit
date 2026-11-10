from __future__ import annotations

import logging
import json
import math
import re
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image


logger = logging.getLogger("reprofit")

CONDITION_LABELS = ("Like New", "Good", "Fair", "Poor", "Damaged")
ASSESSMENT_LABELS = ("Damaged", "Bad", "Fair", "Good")
ASSESSMENT_CONDITION_MAPPING = {"Like New": "Good", "Poor": "Bad"}
SCORE_BY_LABEL = {
    "Like New": 92,
    "Good": 76,
    "Fair": 55,
    "Poor": 35,
    "Damaged": 18,
}
FOLDER_TO_LABEL = {
    "like_new": "Like New",
    "like-new": "Like New",
    "likenew": "Like New",
    "good": "Good",
    "fair": "Fair",
    "poor": "Poor",
    "damaged": "Damaged",
    **{label.lower(): label for label in CONDITION_LABELS},
}

ROOT_DIR = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = ROOT_DIR / "ml" / "weights" / "condition_yolo11.pt"
TEMPERATURE_PATH = ROOT_DIR / "ml" / "weights" / "temperature.json"
PRODUCT_DETECTOR_WEIGHTS_PATH = ROOT_DIR / "yolo11n.pt"
PRODUCT_MIN_CONFIDENCE = 60.0

PRODUCT_CLASS_ALIASES = {
    "Mobile Phone": {"mobile phone", "mobile_phone", "mobile", "phone", "smartphone", "cell phone", "cellphone", "cellular phone", "cellular_phone", "cellular telephone", "iphone", "galaxy", "pixel", "oneplus", "redmi", "realme", "vivo", "oppo", "nokia", "motorola", "smart phone"},
    "Laptop": {"laptop", "laptop computer", "notebook", "notebook computer", "macbook", "chromebook", "ultrabook", "thinkpad", "xps", "gaming laptop", "hp victus", "omen"},
    "Tablet": {"tablet", "ipad", "tab", "android tablet"},
    "Mouse": {"mouse", "computer mouse", "computer mouse device", "trackball"},
    "Keyboard": {"keyboard", "keyboards", "computer keyboard"},
    "Printer": {"printer", "computer printer"},
    "Monitor": {"monitor", "computer monitor", "computer screen", "display monitor"},
    "Desktop Computer": {"desktop computer", "personal computer", "pc tower", "desktop pc"},
    "Router": {"router", "wireless router", "network router"},
    "Storage Device": {"hard disk", "hard disk drive", "external hard drive", "solid state drive", "usb flash drive", "flash drive"},
    "Headphones": {"headphone", "headset", "earbuds", "earbud", "earphones", "airpods"},
    "Camera": {"camera", "camera body", "digital camera", "dslr"},
    "Loudspeaker": {"loudspeaker", "speaker", "soundbar", "speaker system", "bluetooth speaker", "jbl", "boombox"},
    "Lighter": {"lighter"},
    "Footwear": {"footwear", "shoe", "shoes", "sandal", "sandals", "sneaker", "sneakers", "boot", "boots"},
}

_model = None
_load_attempted = False
_model_lock = threading.Lock()
_product_detector = None
_product_detector_load_attempted = False
_product_detector_lock = threading.Lock()


def _normalize_label(name: str) -> str | None:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    return FOLDER_TO_LABEL.get(key) or FOLDER_TO_LABEL.get(name.strip().lower())


def normalize_assessment_condition(condition: str | None) -> str | None:
    if condition is None:
        return None
    return ASSESSMENT_CONDITION_MAPPING.get(condition, condition)


def _normalize_product_key(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _canonical_product_label(value: str | None) -> str | None:
    if value is None:
        return None
    text = _normalize_product_key(value)
    if not text:
        return None
    padded_text = f" {text} "
    matches: list[tuple[int, int, str]] = []
    for canonical, aliases in PRODUCT_CLASS_ALIASES.items():
        normalized_aliases = {_normalize_product_key(alias) for alias in aliases}
        for alias in normalized_aliases:
            location = padded_text.find(f" {alias} ")
            if location >= 0:
                matches.append((location, -len(alias), canonical))
    return min(matches)[2] if matches else None


def expected_product_category(product_name: str, category: str) -> str | None:
    return _canonical_product_label(category) or _canonical_product_label(product_name)


def validate_product_image(
    product_name: str,
    category: str,
    detected_label: str | None,
    confidence: float | None,
    *,
    class_index: int | None = None,
    raw_label: str | None = None,
) -> tuple[str, bool | None, str | None]:
    expected = expected_product_category(product_name, category)
    detected = _canonical_product_label(detected_label)
    if (
        expected is None
        or confidence is None
        or not math.isfinite(confidence)
        or confidence < 0
        or confidence < PRODUCT_MIN_CONFIDENCE
        or confidence > 100
    ):
        validation, matches = "UNVERIFIED", None
    elif not detected_label or detected_label.strip().lower() in {"unknown", "unknown product"}:
        validation, matches = "UNVERIFIED", None
    elif detected is None:
        validation, matches = "UNVERIFIED", None
    else:
        matches = expected == detected
        validation = "MATCH" if matches else "MISMATCH"
    logger.info(
        "Product-image validation: product_name=%r category=%r expected=%r "
        "class_index=%r raw_label=%r mapped_label=%r confidence=%r "
        "threshold=%.2f validation=%s product_matches=%r",
        product_name,
        category,
        expected,
        class_index,
        raw_label,
        detected_label,
        confidence,
        PRODUCT_MIN_CONFIDENCE,
        validation,
        matches,
    )
    return validation, matches, expected


def _score_from_probs(probs: dict[str, float]) -> tuple[str, int, float]:
    condition = max(probs, key=probs.get)
    expected = sum(SCORE_BY_LABEL[label] * probs.get(label, 0.0) for label in CONDITION_LABELS)
    score = int(round(max(0.0, min(100.0, expected))))
    confidence = round(probs[condition] * 100.0, 2)
    return condition, score, confidence


def _is_condition_classifier(names: dict) -> bool:
    labels = {str(name).strip().lower().replace("-", "_").replace(" ", "_") for name in names.values()}
    five_class_names = {label.lower().replace(" ", "_") for label in CONDITION_LABELS}
    return labels == five_class_names or _is_three_class_classifier(names)


def _is_three_class_classifier(names: dict) -> bool:
    labels = {str(name).strip().lower().replace("-", "_").replace(" ", "_") for name in names.values()}
    return labels == {"resell", "refurbish", "recycle"}


def _class_probabilities(values: list[float], names: dict) -> dict[str, float]:
    probabilities = {label: 0.0 for label in CONDITION_LABELS}
    decision_groups = {
        "resell": ("Like New", "Good"),
        "refurbish": ("Fair",),
        "recycle": ("Poor", "Damaged"),
    }
    for index, value in enumerate(values):
        raw_name = str(names.get(index, ""))
        condition_label = _normalize_label(raw_name)
        if condition_label:
            probabilities[condition_label] += value
            continue
        group = raw_name.strip().lower().replace("-", "_").replace(" ", "_")
        labels = decision_groups.get(group)
        if labels:
            share = value / len(labels)
            for label in labels:
                probabilities[label] += share
    total = sum(probabilities.values())
    if total:
        probabilities = {label: value / total for label, value in probabilities.items()}
    return probabilities


def _temperature() -> float:
    try:
        configuration = json.loads(TEMPERATURE_PATH.read_text(encoding="utf-8"))
        value = float(configuration["temperature"])
        if math.isfinite(value) and value > 0:
            return value
        logger.warning("Ignoring invalid temperature value in %s", TEMPERATURE_PATH)
    except FileNotFoundError:
        return 1.5
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Unable to read temperature calibration from %s: %s", TEMPERATURE_PATH, exc)
    return 1.5


def _temperature_scale(values: list[float], temperature: float) -> list[float]:
    # TODO: fit the temperature on the held-out validation set.
    positive = [max(float(value), 1e-12) ** (1.0 / temperature) for value in values]
    total = sum(positive)
    return [value / total for value in positive] if total else values


def _crop_white_background(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    scale = min(1.0, 128.0 / max(width, height))
    sample_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    sample = rgb.resize(sample_size)
    pixels = list(sample.getdata())
    white_ratio = sum(1 for pixel in pixels if min(pixel) > 240) / max(len(pixels), 1)
    if white_ratio <= 0.5:
        return rgb

    mask = Image.new("L", sample.size)
    mask.putdata([255 if min(pixel) <= 240 else 0 for pixel in pixels])
    bounds = mask.getbbox()
    if not bounds:
        return rgb
    left, top, right, bottom = bounds
    left = int(left / scale)
    top = int(top / scale)
    right = min(width, math.ceil(right / scale))
    bottom = min(height, math.ceil(bottom / scale))
    padding_x = max(1, round((right - left) * 0.04))
    padding_y = max(1, round((bottom - top) * 0.04))
    return rgb.crop(
        (
            max(0, left - padding_x),
            max(0, top - padding_y),
            min(width, right + padding_x),
            min(height, bottom + padding_y),
        )
    )


def _load_yolo_model():
    global _model, _load_attempted
    if _load_attempted:
        return _model
    with _model_lock:
        if _load_attempted:
            return _model
        _load_attempted = True
        if not WEIGHTS_PATH.exists():
            logger.info("YOLO11 condition weights not found at %s", WEIGHTS_PATH)
            return None
        try:
            from ultralytics import YOLO

            candidate = YOLO(str(WEIGHTS_PATH))
            names = getattr(candidate, "names", {}) or {}
            if not _is_condition_classifier(names):
                logger.warning("Skipping %s because it has unsupported condition classes", WEIGHTS_PATH)
                return None
            _model = candidate
            logger.info("Loaded YOLO11 condition classifier from %s", WEIGHTS_PATH)
            return _model
        except Exception:
            logger.exception("Failed to load YOLO11 condition classifier")
            return None


def _yolo_predict(image: Image.Image) -> dict | None:
    model = _load_yolo_model()
    if model is None:
        raise RuntimeError("The trained condition classifier is unavailable")
    width, height = image.size
    if width > 2 and height > 2:
        inset_x = max(1, round(width * 0.05))
        inset_y = max(1, round(height * 0.05))
        center_crop = image.crop((inset_x, inset_y, width - inset_x, height - inset_y))
    else:
        center_crop = image
    views = (image, image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), center_crop)
    calibrated_views: list[dict[str, float]] = []
    for view in views:
        results = model.predict(view, verbose=False)
        if not results or results[0].probs is None:
            raise RuntimeError("The condition classifier did not return class probabilities")
        result = results[0]
        raw_probs = [float(value) for value in result.probs.data.tolist()]
        scaled_probs = _temperature_scale(raw_probs, _temperature())
        calibrated_views.append(_class_probabilities(scaled_probs, result.names))
    probs = {
        label: sum(view[label] for view in calibrated_views) / len(calibrated_views)
        for label in CONDITION_LABELS
    }
    condition, score, _ = _score_from_probs(probs)
    confidence = round(max(probs.values()) * 100.0, 2)
    return {
        "condition": normalize_assessment_condition(condition),
        "condition_score": score,
        "confidence": confidence,
        "model_name": "yolo11-cls",
        "source": "yolo11-cls",
        "class_probabilities": {label: round(probs[label], 6) for label in CONDITION_LABELS},
    }


def _product_label(name: str) -> str:
    canonical = _canonical_product_label(name)
    if canonical:
        return canonical
    fallback = name.split(",")[0].strip().replace("_", " ")
    return fallback.title() if fallback else "Unknown product"


def _load_product_detector():
    global _product_detector, _product_detector_load_attempted
    if _product_detector_load_attempted:
        return _product_detector
    with _product_detector_lock:
        if _product_detector_load_attempted:
            return _product_detector
        _product_detector_load_attempted = True

        if not PRODUCT_DETECTOR_WEIGHTS_PATH.exists():
            logger.info(
                "YOLO11 product detection weights not found at %s",
                PRODUCT_DETECTOR_WEIGHTS_PATH,
            )
            return None
        try:
            from ultralytics import YOLO

            _product_detector = YOLO(str(PRODUCT_DETECTOR_WEIGHTS_PATH))
            logger.info(
                "Loaded YOLO11 product detector from %s",
                PRODUCT_DETECTOR_WEIGHTS_PATH,
            )
        except Exception:
            logger.exception("Failed to load YOLO11 product detector")
        return _product_detector


def _yolo_product_predict(image: Image.Image) -> dict | None:
    model = _load_product_detector()
    if model is None:
        logger.warning("Product image identity unavailable: COCO detector is not loaded")
        return None
    try:
        results = model.predict(image, verbose=False, conf=0.01)
    except Exception:
        logger.exception("YOLO11 product detection failed")
        return None
    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        logger.info("YOLO11 product detector returned no object detections")
        return None

    result = results[0]
    boxes = sorted(result.boxes, key=lambda box: float(box.conf.item()), reverse=True)
    observed = []
    for box in boxes[:5]:
        class_index = int(box.cls.item())
        raw_name = str(result.names.get(class_index, ""))
        confidence = float(box.conf.item()) * 100.0
        observed.append({
            "class_index": class_index,
            "raw_label": raw_name,
            "mapped_label": _product_label(raw_name),
            "confidence": round(confidence, 2),
        })
    logger.info("YOLO11 product detector raw outputs: %s", observed)

    top_box = boxes[0]
    class_index = int(top_box.cls.item())
    raw_name = str(result.names.get(class_index, ""))
    if not raw_name.strip() or raw_name.strip().lower() in {"unknown", "unknown product"}:
        return None
    confidence = float(top_box.conf.item()) * 100.0
    if not math.isfinite(confidence) or confidence < 0.0 or confidence > 100.0:
        logger.warning(
            "YOLO11 returned invalid product confidence: class_index=%s raw_label=%s confidence=%r",
            class_index,
            raw_name,
            confidence,
        )
        return None
    if confidence < PRODUCT_MIN_CONFIDENCE:
        logger.info(
            "YOLO11 top object below product identity threshold; retaining it as unverified evidence: class_index=%s raw_label=%s confidence=%.2f threshold=%.2f",
            class_index,
            raw_name,
            confidence,
            PRODUCT_MIN_CONFIDENCE,
        )
    return {
        "product_class_index": class_index,
        "product_raw_label": raw_name,
        "product_label": _product_label(raw_name),
        "product_confidence": round(confidence, 2),
        "product_model_name": "yolo11n",
    }


def predict_condition(image_bytes: bytes) -> dict:
    if not image_bytes:
        raise ValueError("Image bytes are required")
    with Image.open(BytesIO(image_bytes)) as opened_image:
        image = _crop_white_background(opened_image.convert("RGB"))
    result = _yolo_predict(image)
    product_prediction = _yolo_product_predict(image)
    if product_prediction:
        result.update(product_prediction)
    return result
