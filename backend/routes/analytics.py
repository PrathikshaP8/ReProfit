from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import ReturnItem
from schemas import CategoryBreakdownItem, ConditionDistributionItem, DailyProfitPoint
from services.condition_classifier import ASSESSMENT_LABELS, normalize_assessment_condition


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _range_bounds(range_days: int) -> tuple[datetime, datetime]:
    if range_days not in {7, 30, 90}:
        raise HTTPException(status_code=400, detail="range must be 7, 30 or 90")

    today = datetime.utcnow().date()
    start = today - timedelta(days=range_days - 1)
    return datetime.combine(start, time.min), datetime.combine(today + timedelta(days=1), time.min)


def _realized_items(db: Session, start: datetime, end: datetime) -> list[ReturnItem]:
    return (
        db.query(ReturnItem)
        .filter(
            ReturnItem.status == "approved",
            ReturnItem.processed_at.isnot(None),
            ReturnItem.processed_at >= start,
            ReturnItem.processed_at < end,
            ReturnItem.profit_estimate.isnot(None),
        )
        .all()
    )


@router.get("/daily-profit", response_model=list[DailyProfitPoint])
def daily_profit(range_days: int = Query(30, alias="range"), db: Session = Depends(get_db)):
    start, end = _range_bounds(range_days)
    grouped: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"profit": 0.0, "item_count": 0, "resell": 0, "refurbish": 0, "recycle": 0}
    )

    for item in _realized_items(db, start, end):
        day = item.processed_at.date()
        key = day.isoformat()
        grouped[key]["profit"] += item.profit_estimate or 0
        grouped[key]["item_count"] += 1
        decision = (item.recommended_decision or "").lower()
        if decision == "resell":
            grouped[key]["resell"] += 1
        elif decision == "refurbish":
            grouped[key]["refurbish"] += 1
        elif decision == "recycle":
            grouped[key]["recycle"] += 1

    rows = []
    for i in range(range_days):
        day = start.date() + timedelta(days=i)
        key = day.isoformat()
        entry = grouped[key]
        rows.append(
            DailyProfitPoint(
                date=day.strftime("%d %b"),
                profit_recovered=round(entry["profit"], 2),
                item_count=entry["item_count"],
                resell_count=entry["resell"],
                refurbish_count=entry["refurbish"],
                recycle_count=entry["recycle"],
            )
        )
    return rows


@router.get("/category-breakdown", response_model=list[CategoryBreakdownItem])
def category_breakdown(range_days: int = Query(30, alias="range"), db: Session = Depends(get_db)):
    start, end = _range_bounds(range_days)
    items = _realized_items(db, start, end)
    grouped: dict[str, dict[str, float | int]] = defaultdict(lambda: {"count": 0, "profit": 0.0})
    for item in items:
        grouped[item.category]["count"] += 1
        grouped[item.category]["profit"] += item.profit_estimate or 0
    return [
        CategoryBreakdownItem(category=category, count=values["count"], total_profit=round(values["profit"], 2))
        for category, values in sorted(grouped.items())
    ]


@router.get("/condition-distribution", response_model=list[ConditionDistributionItem])
def condition_distribution(range_days: int = Query(30, alias="range"), db: Session = Depends(get_db)):
    start, end = _range_bounds(range_days)
    items = (
        db.query(ReturnItem)
        .filter(
            ReturnItem.condition.isnot(None),
            ReturnItem.created_at >= start,
            ReturnItem.created_at < end,
        )
        .all()
    )
    grouped = dict.fromkeys(ASSESSMENT_LABELS, 0)
    for item in items:
        condition = normalize_assessment_condition(item.condition)
        if condition in grouped:
            grouped[condition] += 1
    return [ConditionDistributionItem(condition=condition, count=grouped[condition]) for condition in ASSESSMENT_LABELS]
