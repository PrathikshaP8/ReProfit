from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReturnCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    purchase_cost: float = Field(ge=0, allow_inf_nan=False)
    market_price: float = Field(gt=0, allow_inf_nan=False)
    market_price_source: str | None = Field(default=None, max_length=100)
    market_price_listing_id: str | None = Field(default=None, max_length=255)
    market_price_url: str | None = Field(default=None, max_length=1000)


class EbayImport(BaseModel):
    ebay_item_id: str
    product_name: str
    category: str = "Electronics"
    purchase_cost: float = Field(ge=0, allow_inf_nan=False)
    market_price: float = Field(gt=0, allow_inf_nan=False)
    market_price_source: str = Field(default="SerpAPI", max_length=100)
    market_price_listing_id: str | None = Field(default=None, max_length=255)
    market_price_url: str | None = Field(default=None, max_length=1000)


class ReturnAnalyzeInput(BaseModel):
    condition: str | None = None
    condition_score: int | None = None
    notes: str | None = None


class ReturnDecisionInput(BaseModel):
    notes: str = Field(min_length=1)

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Inspector's Note is required")
        return trimmed


class ReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_name: str
    category: str
    return_id: str
    purchase_cost: float
    market_price: float
    market_price_source: str | None = None
    market_price_listing_id: str | None = None
    market_price_url: str | None = None
    status: str
    condition: str | None = None
    return_reason: str | None = None
    condition_score: int | None = None
    condition_confidence: float | None = None
    notes: str | None = None
    image_path: str | None = None
    ai_description: str | None = None
    confidence_score: float | None = None
    demand_score: float | None = None
    sustainability_score: float | None = None
    profit_estimate: float | None = None
    recovery_rate: float | None = None
    repair_cost_rate: float | None = None
    recovery_value: float | None = None
    repair_cost: float | None = None
    other_costs: float | None = None
    approval_warnings: list[str] | None = None
    profit_estimate_error: str | None = None
    market_demand_percent: float | None = None
    eco_score: float | None = None
    recommended_decision: str | None = None
    product_label: str | None = None
    product_confidence: float | None = None
    product_matches: bool | None = None
    product_validation: Literal["MATCH", "MISMATCH", "UNVERIFIED"] = "UNVERIFIED"
    expected_product: str | None = None
    image_sha256: str | None = None
    analysis_image_sha256: str | None = None
    analysis_notes_conflict: bool = False
    created_at: datetime
    analyzed_at: datetime | None = None
    processed_at: datetime | None = None


class AnalyzeResponse(BaseModel):
    condition: str
    ai_description: str
    confidence_score: float
    condition_confidence: float | None = None
    demand_score: float
    sustainability_score: float
    profit_estimate: float
    recovery_value: float | None = None
    repair_cost: float | None = None
    other_costs: float | None = None
    recovery_rate: float | None = None
    repair_cost_rate: float | None = None
    market_demand_percent: float
    eco_score: float
    recommended_decision: str
    adjusted_condition_score: int
    score_source: str = "manual"
    model_name: str | None = None
    class_probabilities: dict[str, float] = Field(default_factory=dict)
    product_label: str | None = None
    product_class_index: int | None = None
    product_raw_label: str | None = None
    product_confidence: float | None = None
    product_model_name: str | None = None
    product_matches: bool | None = None
    product_validation: Literal["MATCH", "MISMATCH", "UNVERIFIED"] = "UNVERIFIED"
    expected_product: str | None = None
    ai_score: float | None = None
    inspector_score: float | None = None
    final_score: float | None = None
    needs_manual_review: bool = False
    alt_decision: str | None = None
    decision_reason: str | None = None
    notes_conflict: bool = False


class ConditionPrediction(BaseModel):
    condition: str
    condition_score: int
    confidence: float
    model_name: str
    source: str
    class_probabilities: dict[str, float] = Field(default_factory=dict)
    product_label: str | None = None
    product_class_index: int | None = None
    product_raw_label: str | None = None
    product_confidence: float | None = None
    product_model_name: str | None = None
    product_matches: bool | None = None
    product_validation: Literal["MATCH", "MISMATCH", "UNVERIFIED"] = "UNVERIFIED"
    expected_product: str | None = None


class DashboardSummary(BaseModel):
    total_profit_recovered: float
    avg_profit_per_return: float
    average_profit: float
    average_loss: float
    decision_accuracy: float
    loss_reduction_percent: float
    total_items_processed: int
    items_today: int
    profit_change_percent: float
    items_change_vs_yesterday: float


class TrendPoint(BaseModel):
    date: str
    profit_recovered: float


class DecisionSplit(BaseModel):
    resell_percent: float
    refurbish_percent: float
    recycle_percent: float


class RecentDecision(BaseModel):
    id: int
    return_id: str
    product_name: str
    category: str
    recommended_decision: str | None
    status: str
    profit_estimate: float | None
    processed_at: datetime | None
    confidence_score: float | None = None


class DailyProfitPoint(BaseModel):
    date: str
    profit_recovered: float
    item_count: int
    resell_count: int
    refurbish_count: int
    recycle_count: int


class CategoryBreakdownItem(BaseModel):
    category: str
    count: int
    total_profit: float


class ConditionDistributionItem(BaseModel):
    condition: str
    count: int


class SettingsUpdate(BaseModel):
    min_confidence: float
    min_profit_floor: float = Field(ge=0, allow_inf_nan=False)
    min_demand_score: float
    resell_recovery_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    refurbish_recovery_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    refurbish_cost_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    recycle_recovery_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    other_costs_per_item: float = Field(ge=0, allow_inf_nan=False)
    auto_approve: bool
    email_on_auto_approve: bool
    email_on_high_value: bool
    daily_summary: bool
    weekly_analytics: bool
    company_name: str
    industry: str
    webhook_url: str | None = None


class SettingsOut(SettingsUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    api_key: str


class MaskedApiKeyOut(BaseModel):
    api_key: str


class AutoProcessResponse(BaseModel):
    auto_approved_count: int
    items: list[int]


DecisionLiteral = Literal["approved", "rejected", "pending"]
