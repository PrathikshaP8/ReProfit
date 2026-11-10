from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ReturnItem, Settings
from schemas import MaskedApiKeyOut, SettingsOut, SettingsUpdate
from services.profit_calculator import ProfitAssumptions, calculate_profit_breakdown


router = APIRouter(prefix="/api/settings", tags=["settings"])


def _settings_or_404(db: Session) -> Settings:
    settings = db.query(Settings).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@router.get("/thresholds", response_model=SettingsOut)
def get_thresholds(db: Session = Depends(get_db)):
    return _settings_or_404(db)


@router.patch("/thresholds", response_model=SettingsOut)
def update_thresholds(payload: SettingsUpdate, db: Session = Depends(get_db)):
    settings = _settings_or_404(db)
    values = payload.model_dump()
    assumptions = ProfitAssumptions(
        resell_recovery_rate=values["resell_recovery_rate"],
        refurbish_recovery_rate=values["refurbish_recovery_rate"],
        refurbish_cost_rate=values["refurbish_cost_rate"],
        recycle_recovery_rate=values["recycle_recovery_rate"],
        other_costs_per_item=values["other_costs_per_item"],
    )
    assumption_fields = (
        "resell_recovery_rate",
        "refurbish_recovery_rate",
        "refurbish_cost_rate",
        "recycle_recovery_rate",
        "other_costs_per_item",
    )
    assumptions_changed = any(
        getattr(settings, field) != values[field]
        for field in assumption_fields
    )
    pending_breakdowns: list[tuple[ReturnItem, dict[str, float]]] = []
    if assumptions_changed:
        pending = (
            db.query(ReturnItem)
            .filter(
                ReturnItem.status == "pending",
                ReturnItem.recommended_decision.isnot(None),
            )
            .all()
        )
        for item in pending:
            try:
                pending_breakdowns.append(
                    (
                        item,
                        calculate_profit_breakdown(
                            item.recommended_decision,
                            item.market_price,
                            item.purchase_cost,
                            assumptions,
                        ),
                    )
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot update profit assumptions until {item.return_id} has valid market and purchase costs: {exc}",
                ) from exc

    for key, value in values.items():
        setattr(settings, key, value)
    for item, breakdown in pending_breakdowns:
        item.profit_estimate = breakdown["estimated_profit"]
        item.recovery_rate = breakdown["recovery_rate"]
        item.repair_cost_rate = breakdown["repair_cost_rate"]
        item.recovery_value = breakdown["recovery_value"]
        item.repair_cost = breakdown["repair_cost"]
        item.other_costs = breakdown["other_costs"]
    db.commit()
    db.refresh(settings)
    return settings


@router.post("/regenerate-key", response_model=MaskedApiKeyOut)
def regenerate_key(db: Session = Depends(get_db)):
    settings = _settings_or_404(db)
    settings.api_key = str(uuid4())
    db.commit()
    return MaskedApiKeyOut(api_key=settings.api_key)
