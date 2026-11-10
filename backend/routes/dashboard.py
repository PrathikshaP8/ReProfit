from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ReturnItem
from schemas import DashboardSummary, DecisionSplit, RecentDecision, TrendPoint


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _safe_pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)):
    items = db.query(ReturnItem).all()
    approved = [item for item in items if item.status == "approved"]
    processed = [item for item in items if item.status != "pending"]
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    approved_profit = sum(item.profit_estimate or 0 for item in approved)
    approved_positive_profits = [item.profit_estimate or 0 for item in approved if (item.profit_estimate or 0) > 0]
    approved_negative_losses = [abs(item.profit_estimate or 0) for item in approved if (item.profit_estimate or 0) < 0]
    approved_market = sum(item.market_price or 0 for item in approved)
    items_today = sum(1 for item in processed if item.processed_at and item.processed_at.date() == today)
    items_yesterday = sum(1 for item in processed if item.processed_at and item.processed_at.date() == yesterday)

    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    this_month_profit = sum(
        (item.profit_estimate or 0)
        for item in approved
        if item.processed_at and item.processed_at.date() >= this_month_start
    )
    last_month_profit = sum(
        (item.profit_estimate or 0)
        for item in approved
        if item.processed_at and last_month_start <= item.processed_at.date() <= last_month_end
    )

    analyzed = [item for item in processed if item.recommended_decision]
    return DashboardSummary(
        total_profit_recovered=round(approved_profit, 2),
        avg_profit_per_return=round(approved_profit / len(approved), 2) if approved else 0.0,
        average_profit=_average(approved_positive_profits),
        average_loss=_average(approved_negative_losses),
        decision_accuracy=_safe_pct(len(approved), len(analyzed)),
        loss_reduction_percent=_safe_pct(sum((item.market_price or 0) - (item.profit_estimate or 0) for item in approved), approved_market),
        total_items_processed=len(processed),
        items_today=items_today,
        profit_change_percent=_safe_pct(this_month_profit - last_month_profit, last_month_profit) if last_month_profit else (100.0 if this_month_profit else 0.0),
        items_change_vs_yesterday=round(items_today - items_yesterday, 2),
    )


@router.get("/trend", response_model=list[TrendPoint])
def get_trend(period: str = "weekly", db: Session = Depends(get_db)):
    if period not in {"weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="period must be weekly or monthly")
    approved = db.query(ReturnItem).filter(ReturnItem.status == "approved").all()
    days = 7 if period == "weekly" else 30
    start = datetime.utcnow().date() - timedelta(days=days - 1)
    grouped: dict[str, float] = defaultdict(float)
    for item in approved:
        if item.processed_at:
            key = item.processed_at.date().isoformat()
            grouped[key] += item.profit_estimate or 0
    return [
        TrendPoint(date=(start + timedelta(days=i)).strftime("%d %b"), profit_recovered=round(grouped.get((start + timedelta(days=i)).isoformat(), 0), 2))
        for i in range(days)
    ]


@router.get("/decision-split", response_model=DecisionSplit)
def decision_split(db: Session = Depends(get_db)):
    items = db.query(ReturnItem).filter(ReturnItem.recommended_decision.isnot(None)).all()
    total = len(items)
    resell = sum(1 for item in items if item.recommended_decision == "Resell")
    refurbish = sum(1 for item in items if item.recommended_decision == "Refurbish")
    recycle = sum(1 for item in items if item.recommended_decision == "Recycle")
    return DecisionSplit(
        resell_percent=_safe_pct(resell, total),
        refurbish_percent=_safe_pct(refurbish, total),
        recycle_percent=_safe_pct(recycle, total),
    )


@router.get("/recent-decisions", response_model=list[RecentDecision])
def recent_decisions(db: Session = Depends(get_db)):
    items = (
        db.query(ReturnItem)
        .filter(ReturnItem.status.in_(["approved", "rejected"]))
        .order_by(ReturnItem.processed_at.desc())
        .limit(10)
        .all()
    )
    return [
        RecentDecision(
            id=item.id,
            return_id=item.return_id,
            product_name=item.product_name,
            category=item.category,
            recommended_decision=item.recommended_decision,
            status=item.status,
            profit_estimate=item.profit_estimate,
            processed_at=item.processed_at,
            confidence_score=item.confidence_score,
        )
        for item in items
    ]
