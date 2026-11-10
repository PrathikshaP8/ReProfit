from __future__ import annotations

from dataclasses import dataclass
import math

RESELL_RECOVERY_RATE = 0.85
REFURBISH_RECOVERY_RATE = 0.65
REFURBISH_COST_RATE = 0.12
RECYCLE_RECOVERY_RATE = 0.08


@dataclass(frozen=True)
class ProfitAssumptions:
    resell_recovery_rate: float = RESELL_RECOVERY_RATE
    refurbish_recovery_rate: float = REFURBISH_RECOVERY_RATE
    refurbish_cost_rate: float = REFURBISH_COST_RATE
    recycle_recovery_rate: float = RECYCLE_RECOVERY_RATE
    other_costs_per_item: float = 0.0


DEFAULT_PROFIT_ASSUMPTIONS = ProfitAssumptions()


def _validated_amount(value: float | None, name: str, *, allow_zero: bool) -> float:
    if value is None:
        raise ValueError(f"{name} is required to estimate profit")
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid INR amount") from exc
    if not math.isfinite(amount) or amount < 0 or (not allow_zero and amount == 0):
        qualifier = "non-negative" if allow_zero else "greater than zero"
        raise ValueError(f"{name} must be a finite {qualifier} INR amount")
    return amount


def _validated_rate(value: float, name: str) -> float:
    rate = float(value)
    if not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return rate


def calculate_profit_breakdown(
    decision: str,
    market_price: float | None,
    purchase_cost: float | None,
    assumptions: ProfitAssumptions = DEFAULT_PROFIT_ASSUMPTIONS,
) -> dict[str, float]:
    market = _validated_amount(market_price, "Market reference price", allow_zero=False)
    cost = _validated_amount(purchase_cost, "Purchase cost", allow_zero=True)
    other_costs = _validated_amount(assumptions.other_costs_per_item, "Other costs", allow_zero=True)

    recovery_rates = {
        "Resell": _validated_rate(assumptions.resell_recovery_rate, "Resell recovery rate"),
        "Refurbish": _validated_rate(assumptions.refurbish_recovery_rate, "Refurbish recovery rate"),
        "Recycle": _validated_rate(assumptions.recycle_recovery_rate, "Recycle recovery rate"),
    }
    repair_cost_rate = _validated_rate(assumptions.refurbish_cost_rate, "Refurbish cost rate")
    if decision not in recovery_rates:
        raise ValueError(f"Unsupported recovery decision: {decision}")

    recovery_rate = recovery_rates[decision]
    recovery_value = market * recovery_rate
    repair_cost = market * repair_cost_rate if decision == "Refurbish" else 0.0
    estimated_profit = recovery_value - cost - repair_cost - other_costs
    if not all(math.isfinite(value) for value in (recovery_value, repair_cost, estimated_profit)):
        raise ValueError("Profit estimate exceeds the supported numeric range")
    return {
        "recovery_rate": recovery_rate,
        "repair_cost_rate": repair_cost_rate if decision == "Refurbish" else 0.0,
        "recovery_value": round(recovery_value, 2),
        "repair_cost": round(repair_cost, 2),
        "other_costs": round(other_costs, 2),
        "estimated_profit": round(estimated_profit, 2),
    }


def calculate_profit_estimates(
    market_price: float | None,
    purchase_cost: float | None,
    assumptions: ProfitAssumptions = DEFAULT_PROFIT_ASSUMPTIONS,
) -> dict[str, float]:
    return {
        decision: calculate_profit_breakdown(decision, market_price, purchase_cost, assumptions)["estimated_profit"]
        for decision in ("Resell", "Refurbish", "Recycle")
    }


def calculate_profit_estimate(
    decision: str,
    market_price: float | None,
    purchase_cost: float | None,
    assumptions: ProfitAssumptions = DEFAULT_PROFIT_ASSUMPTIONS,
) -> float:
    return calculate_profit_breakdown(decision, market_price, purchase_cost, assumptions)["estimated_profit"]
