from __future__ import annotations

import re
from collections.abc import Mapping

from services.profit_calculator import DEFAULT_PROFIT_ASSUMPTIONS, ProfitAssumptions, calculate_profit_estimates


CONDITION_LABELS = ("Like New", "Good", "Fair", "Poor", "Damaged")
DECISIONS = ("Resell", "Refurbish", "Recycle")


def _clamp_percentage(value: int | float | None, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, numeric))


def _normalized_probabilities(
    class_probabilities: Mapping[str, float] | None,
) -> dict[str, float]:
    probabilities = {label: 0.0 for label in CONDITION_LABELS}
    aliases = {
        re.sub(r"[^a-z]", "", label.lower()): label
        for label in CONDITION_LABELS
    }
    if class_probabilities:
        for name, raw_value in class_probabilities.items():
            key = re.sub(r"[^a-z]", "", str(name).lower())
            label = aliases.get(key)
            if label is None:
                continue
            try:
                probabilities[label] += max(0.0, float(raw_value))
            except (TypeError, ValueError):
                continue
    total = sum(probabilities.values())
    if total > 0:
        return {label: value / total for label, value in probabilities.items()}
    return probabilities


def _probabilities_from_score(score: float) -> dict[str, float]:
    if score >= 80:
        return {"Like New": 1.0, "Good": 0.0, "Fair": 0.0, "Poor": 0.0, "Damaged": 0.0}
    if score >= 50:
        return {"Like New": 0.0, "Good": 0.0, "Fair": 1.0, "Poor": 0.0, "Damaged": 0.0}
    return {"Like New": 0.0, "Good": 0.0, "Fair": 0.0, "Poor": 1.0, "Damaged": 0.0}


def recommend_decision_details(
    condition_score: int | float,
    class_probabilities: Mapping[str, float] | None,
    confidence: float,
    category: str,
    market_price: float,
    purchase_cost: float,
    product_matches: bool | None,
    profit_assumptions: ProfitAssumptions = DEFAULT_PROFIT_ASSUMPTIONS,
) -> dict[str, str | bool | None]:
    score = _clamp_percentage(condition_score)
    model_confidence = _clamp_percentage(confidence)
    needs_manual_review = model_confidence < 60.0

    probabilities = _normalized_probabilities(class_probabilities)
    if product_matches is False:
        probabilities = _probabilities_from_score(score)

    p_good = probabilities["Like New"] + probabilities["Good"]
    p_bad = probabilities["Poor"] + probabilities["Damaged"]

    if needs_manual_review and product_matches is not False:
        decision = "Refurbish"
        reason = "Low AI confidence; defaulted to Refurbish pending manual review."
    elif p_good >= 0.5 or score >= 80:
        decision = "Resell"
        reason = "Condition evidence supports resale."
    elif p_bad >= 0.6 and (product_matches is False or model_confidence >= 60.0):
        high_value_electronics = category.strip().casefold() == "electronics" and market_price >= 5000
        if high_value_electronics and p_bad < 0.75:
            decision = "Refurbish"
            reason = "High-value electronics require stronger damage evidence before recycling."
        else:
            decision = "Recycle"
            reason = "High damage probability supports recycling."
    else:
        decision = "Refurbish"
        reason = "Condition evidence supports refurbishment."

    profits = calculate_profit_estimates(market_price, purchase_cost, profit_assumptions)
    best_profit_decision = max(DECISIONS, key=profits.__getitem__)
    alternative = best_profit_decision if best_profit_decision != decision else None
    if alternative:
        reason = (
            f"{reason} {alternative} has higher estimated profit; "
            f"the condition-based {decision} recommendation is retained."
        )

    return {
        "recommended_decision": decision,
        "needs_manual_review": needs_manual_review,
        "alt_decision": alternative,
        "decision_reason": reason,
    }


def recommend_decision(
    condition_score: int | float,
    class_probabilities: Mapping[str, float] | None,
    confidence: float,
    category: str,
    market_price: float,
    purchase_cost: float,
    product_matches: bool | None,
    profit_assumptions: ProfitAssumptions = DEFAULT_PROFIT_ASSUMPTIONS,
) -> str:
    return str(
        recommend_decision_details(
            condition_score,
            class_probabilities,
            confidence,
            category,
            market_price,
            purchase_cost,
            product_matches,
            profit_assumptions,
        )["recommended_decision"]
    )


def sustainability_score(decision: str) -> float:
    normalized = str(decision).strip().lower()
    mapping = {"resell": 95.0, "refurbish": 80.0, "recycle": 60.0}
    return mapping.get(normalized, 60.0)
