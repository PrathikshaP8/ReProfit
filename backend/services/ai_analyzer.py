from __future__ import annotations

import re

from services.condition_classifier import predict_condition, validate_product_image
from services.decision_engine import (
    recommend_decision_details,
    sustainability_score,
)
from services.profit_calculator import (
    DEFAULT_PROFIT_ASSUMPTIONS,
    ProfitAssumptions,
    calculate_profit_breakdown,
)


AI_DESCRIPTIONS = {
    "Like New": "Item appears brand new, box seal intact",
    "Good": "Minor signs of use, fully functional",
    "Fair": "Visible wear, functionality intact",
    "Poor": "Significant wear, may need repairs",
    "Bad": "Significant wear, may need repairs",
    "Damaged": "Physical damage present, repair required",
    "Low confidence": "Low confidence – manual review recommended",
}


def _demand(category: str) -> float:
    ranges = {
        "Electronics": 90.0,
        "Apparel": 78.0,
        "Accessories": 82.0,
        "Other": 68.0,
    }
    return ranges.get(category, ranges["Other"])


def _eco_score(decision: str) -> float:
    return {"Resell": 95.0, "Refurbish": 82.0, "Recycle": 62.0}.get(decision, 62.0)


def _confidence_from_score(score: int) -> float:
    if score >= 80:
        return 92.0
    if score >= 50:
        return 80.0
    return 68.0


def _normalize_note_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _condition_group(condition: str | None) -> str | None:
    normalized = _normalize_note_text(condition)
    if not normalized:
        return None
    if normalized in {"good", "excellent", "like_new", "like new"}:
        return "GOOD"
    if normalized in {"fair", "average", "moderate"}:
        return "FAIR"
    if normalized in {"poor", "bad", "not good"}:
        return "POOR"
    if normalized in {"damaged", "broken", "cracked", "heavily damaged", "severe damage"}:
        return "DAMAGED"
    return None


def _match_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = _normalize_note_text(phrase)
    if not normalized_phrase:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _analyze_inspector_note(notes: str | None) -> dict[str, str | list[str]]:
    text = _normalize_note_text(notes)
    if not text:
        return {"status": "ambiguous", "reason": "Inspector note is empty or does not include a clear condition signal."}

    positive_phrases = [
        "not damaged",
        "not bad",
        "looks good",
        "no visible damage",
        "in good condition",
        "functioning properly",
        "working properly",
        "works fine",
        "good",
        "fine",
    ]
    moderate_phrases = [
        "not working properly",
        "not functioning properly",
        "not good",
        "average condition",
        "needs repair",
        "requires repair",
        "partially working",
        "moderate",
        "performance issue",
    ]
    negative_phrases = [
        "not working at all",
        "not working",
        "not in good condition",
        "severe damage",
        "unusable",
        "heavily damaged",
        "damaged",
        "broken",
        "cracked",
        "bad",
    ]

    matches = {"positive": [], "moderate": [], "negative": []}
    matched_phrases: list[str] = []
    for category, phrases in (("positive", positive_phrases), ("moderate", moderate_phrases), ("negative", negative_phrases)):
        for phrase in sorted(set(phrases), key=lambda item: len(item), reverse=True):
            normalized_phrase = _normalize_note_text(phrase)
            if not normalized_phrase or not _match_phrase(text, phrase):
                continue
            if any(_normalize_note_text(existing) in normalized_phrase or normalized_phrase in _normalize_note_text(existing) for existing in matched_phrases):
                continue
            matches[category].append(phrase)
            matched_phrases.append(phrase)

    if matches["positive"] and (matches["negative"] or matches["moderate"]):
        return {"status": "conflict", "reason": "Inspector note contains conflicting positive and negative evidence."}
    if matches["negative"] and matches["moderate"]:
        return {"status": "conflict", "reason": "Inspector note contains conflicting repair and damage indicators."}
    if matches["positive"]:
        return {"status": "positive", "reason": "Inspector note supports positive product condition."}
    if matches["moderate"]:
        return {"status": "moderate", "reason": "Inspector note suggests repair or inspection is needed."}
    if matches["negative"]:
        return {"status": "negative", "reason": "Inspector note indicates damage or malfunction."}
    return {"status": "ambiguous", "reason": "Inspector note does not include a clear condition signal."}


def _inspector_probabilities(condition: str) -> dict[str, float]:
    labels = ("Like New", "Good", "Fair", "Poor", "Damaged")
    normalized = condition.strip().casefold().replace("_", " ").replace("-", " ")
    if normalized == "bad":
        normalized = "poor"
    selected = next(
        (label for label in labels if label.casefold() == normalized),
        "Fair",
    )
    return {label: float(label == selected) for label in labels}


def analyze_return(
    *,
    product_name: str,
    category: str,
    market_price: float,
    purchase_cost: float,
    condition: str,
    condition_score: int,
    image_bytes: bytes | None,
    notes: str = "",
    score_override: bool = False,
    use_model_assessment: bool = False,
    profit_assumptions: ProfitAssumptions = DEFAULT_PROFIT_ASSUMPTIONS,
):
    prediction = None
    inspector_condition = condition
    inspector_score = max(0, min(100, int(condition_score)))
    ai_score: int | None = None
    final_score = float(inspector_score)
    score_source = "manual"

    if image_bytes:
        prediction = predict_condition(image_bytes)
        ai_score = int(prediction["condition_score"])
        ai_confidence = float(prediction["confidence"])
        if use_model_assessment:
            inspector_condition = prediction["condition"]
            inspector_score = ai_score
        product_confidence = prediction.get("product_confidence")
        product_label = prediction.get("product_label")
        product_validation, product_matches, expected_product = validate_product_image(
            product_name,
            category,
            product_label,
            float(product_confidence) if product_confidence is not None else None,
            class_index=prediction.get("product_class_index"),
            raw_label=prediction.get("product_raw_label"),
        )
        if score_override:
            raise ValueError("Inspector overrides are not supported for model-generated assessments")
        if use_model_assessment:
            final_score = float(ai_score)
        else:
            weight = max(0.3, min(0.8, ai_confidence / 100.0))
            final_score = (weight * ai_score) + ((1.0 - weight) * inspector_score)
        score_source = prediction["source"]
    else:
        ai_confidence = 100.0
        product_confidence = None
        product_label = None
        product_class_index = None
        product_raw_label = None
        product_model_name = None
        product_matches = None
        product_validation, _, expected_product = validate_product_image(
            product_name, category, None, None
        )

    inspector_probabilities = _inspector_probabilities(inspector_condition)
    if prediction is None or score_override or product_matches is False:
        decision_probabilities = inspector_probabilities
    else:
        probability_weight = max(0.3, min(0.8, ai_confidence / 100.0))
        decision_probabilities = {
            label: (
                probability_weight * prediction["class_probabilities"].get(label, 0.0)
                + (1.0 - probability_weight) * inspector_probabilities[label]
            )
            for label in inspector_probabilities
        }
    decision_score = (
        float(inspector_score)
        if product_matches is False or score_override or prediction is None
        else final_score
    )
    decision_confidence = (
        100.0
        if score_override or prediction is None or product_matches is False
        else ai_confidence
    )
    decision_details = recommend_decision_details(
        decision_score,
        decision_probabilities,
        decision_confidence,
        category,
        market_price,
        purchase_cost,
        product_matches,
        profit_assumptions,
    )
    demand = _demand(category)
    confidence = ai_confidence if prediction and not score_override else _confidence_from_score(inspector_score)
    used_condition = (
        inspector_condition
        if score_override or product_matches is False or prediction is None
        else prediction["condition"]
    )
    note_evidence = _analyze_inspector_note(notes)
    condition_group = _condition_group(used_condition)
    notes_conflict = note_evidence["status"] == "conflict" or (
        condition_group == "GOOD" and note_evidence["status"] in {"moderate", "negative"}
    ) or (
        condition_group in {"FAIR", "POOR", "DAMAGED"} and note_evidence["status"] == "positive"
    )
    decision_reason = decision_details["decision_reason"]
    base_decision = str(decision_details["recommended_decision"])
    decision = base_decision

    if condition_group is None:
        decision = "Refurbish"
        decision_reason = "Condition could not be mapped reliably; manual review is required."
    elif notes_conflict:
        actual_note = (notes or "").strip()
        if condition_group == "GOOD":
            decision_reason = (
                f'Condition conflict: the image appears Good, but the inspector reported: "{actual_note}". '
                "The product may look physically good but have an internal or functional issue. Manual inspection is required."
            )
        else:
            decision_reason = (
                f'Condition conflict: the image shows external damage or poor condition, but the inspector reported: "{actual_note}". '
                "Manual inspection is required."
            )
        decision = "Refurbish"
    elif condition_group == "GOOD" and note_evidence["status"] == "positive":
        decision = "Resell"
        decision_reason = "The image assessment and inspector observation agree that the product appears to be in good condition."
    elif condition_group in {"FAIR", "POOR"} and note_evidence["status"] in {"moderate", "negative"}:
        decision = "Refurbish"
        decision_reason = "The image indicates fair or poor condition and the inspector note suggests repair or inspection is required before resale."
    elif condition_group == "DAMAGED" and note_evidence["status"] == "negative":
        if base_decision == "Recycle" and not decision_details["needs_manual_review"]:
            decision = "Recycle"
            decision_reason = "The image and inspector note both indicate damage; the item is not suitable for economical repair and should be recycled."
        else:
            decision = "Refurbish"
            decision_reason = "Severe damage is reported; manual review is required to confirm whether the item is economical to repair before recycling."
    elif condition_group == "GOOD" and note_evidence["status"] in {"moderate", "negative"}:
        decision = "Refurbish"
        decision_reason = (
            f'Condition conflict: the image appears Good, but the inspector reported: "{(notes or "").strip()}". '
            "The product may look physically good but have an internal or functional issue. Manual inspection is required."
        )
    elif condition_group in {"FAIR", "POOR", "DAMAGED"} and note_evidence["status"] == "positive":
        decision = "Refurbish"
        decision_reason = (
            f'Condition conflict: the image shows external damage or poor condition, but the inspector reported: "{(notes or "").strip()}". '
            "Manual inspection is required."
        )
    elif prediction is not None and ai_confidence < 60.0 and not decision_details["needs_manual_review"]:
        decision_reason = f"{decision_reason} AI confidence is low; manual review is recommended."

    base_decision_for_profit = base_decision if base_decision in {"Resell", "Refurbish", "Recycle"} else "Refurbish"
    profit_breakdown = calculate_profit_breakdown(
        base_decision_for_profit,
        market_price,
        purchase_cost,
        profit_assumptions,
    )
    needs_manual_review = bool(decision_details["needs_manual_review"]) or bool(
        prediction is not None and ai_confidence < 60.0
    ) or decision == "Manual Review" or notes_conflict
    if notes_conflict:
        decision_reason = decision_reason or "Inspector notes conflict with the image assessment; manual review is required."
    ai_description = (
        AI_DESCRIPTIONS["Low confidence"]
        if needs_manual_review
        else AI_DESCRIPTIONS.get(used_condition, "Condition detected and evaluated")
    )
    result = {
        "condition": used_condition,
        "ai_description": ai_description,
        "confidence_score": confidence,
        "condition_confidence": float(prediction["confidence"]) if prediction else None,
        "demand_score": demand,
        "sustainability_score": sustainability_score(base_decision_for_profit),
        "profit_estimate": profit_breakdown["estimated_profit"],
        "recovery_value": profit_breakdown["recovery_value"],
        "repair_cost": profit_breakdown["repair_cost"],
        "other_costs": profit_breakdown["other_costs"],
        "recovery_rate": profit_breakdown["recovery_rate"],
        "market_demand_percent": demand,
        "eco_score": _eco_score(base_decision_for_profit),
        "recommended_decision": decision,
        "adjusted_condition_score": int(round(final_score)),
        "ai_score": ai_score,
        "inspector_score": inspector_score,
        "final_score": round(final_score, 2),
        "needs_manual_review": needs_manual_review,
        "alt_decision": decision_details["alt_decision"],
        "decision_reason": decision_reason,
        "score_source": score_source,
        "model_name": prediction["model_name"] if prediction else None,
        "class_probabilities": prediction["class_probabilities"] if prediction else {},
        "product_label": product_label,
        "product_confidence": product_confidence,
        "product_class_index": (
            prediction.get("product_class_index") if prediction else product_class_index
        ),
        "product_raw_label": (
            prediction.get("product_raw_label") if prediction else product_raw_label
        ),
        "product_model_name": (
            prediction.get("product_model_name") if prediction else product_model_name
        ),
        "product_matches": product_matches,
        "product_validation": product_validation,
        "expected_product": expected_product,
        "notes_conflict": notes_conflict,
    }
    return result
