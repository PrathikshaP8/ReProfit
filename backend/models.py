from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    return_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    purchase_cost: Mapped[float] = mapped_column(Float, nullable=False)
    market_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_price_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_price_listing_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_price_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    condition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    demand_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sustainability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    repair_cost_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    repair_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_costs: Mapped[float | None] = mapped_column(Float, nullable=True)
    approval_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    market_demand_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    eco_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_matches: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    image_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_image_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_notes_conflict: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    min_confidence: Mapped[float] = mapped_column(Float, default=85)
    min_profit_floor: Mapped[float] = mapped_column(Float, default=500)
    min_demand_score: Mapped[float] = mapped_column(Float, default=70)
    resell_recovery_rate: Mapped[float] = mapped_column(Float, default=0.85)
    refurbish_recovery_rate: Mapped[float] = mapped_column(Float, default=0.65)
    refurbish_cost_rate: Mapped[float] = mapped_column(Float, default=0.12)
    recycle_recovery_rate: Mapped[float] = mapped_column(Float, default=0.08)
    other_costs_per_item: Mapped[float] = mapped_column(Float, default=0)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    email_on_auto_approve: Mapped[bool] = mapped_column(Boolean, default=True)
    email_on_high_value: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_analytics: Mapped[bool] = mapped_column(Boolean, default=False)
    company_name: Mapped[str] = mapped_column(String(255), default="ReProfit Demo Pvt Ltd")
    industry: Mapped[str] = mapped_column(String(120), default="E-commerce")
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str] = mapped_column(String(100), default=lambda: str(uuid4()))
