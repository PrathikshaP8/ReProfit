from __future__ import annotations

import logging
import hashlib
import math
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from database import get_db
from models import ReturnItem, Settings
from schemas import AnalyzeResponse, AutoProcessResponse, ConditionPrediction, ReturnCreate, ReturnDecisionInput, ReturnOut
from services.ai_analyzer import analyze_return
from services.condition_classifier import (
    ASSESSMENT_LABELS,
    expected_product_category,
    normalize_assessment_condition,
    predict_condition,
    validate_product_image,
)
from services.ebay_client import EbayApiError, search_items
from services.profit_calculator import ProfitAssumptions, calculate_profit_breakdown
from services.serpapi_client import SerpApiError, search_shopping


router = APIRouter(prefix="/api/returns", tags=["returns"])
logger = logging.getLogger("reprofit")
_ORIGINAL_ANALYZE_RETURN = analyze_return
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
MAX_IMAGE_SIZE = 10 * 1024 * 1024
STORED_CONDITION_LABELS = {*ASSESSMENT_LABELS, "Like New", "Poor"}
IMAGE_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "BMP": ".bmp", "TIFF": ".tiff"}
MAX_IMAGE_PIXELS = 20_000_000


def _profit_assumptions(settings: Settings) -> ProfitAssumptions:
    return ProfitAssumptions(
        resell_recovery_rate=settings.resell_recovery_rate,
        refurbish_recovery_rate=settings.refurbish_recovery_rate,
        refurbish_cost_rate=settings.refurbish_cost_rate,
        recycle_recovery_rate=settings.recycle_recovery_rate,
        other_costs_per_item=settings.other_costs_per_item,
    )


def _update_profit_breakdown(item: ReturnItem, settings: Settings) -> dict[str, float]:
    breakdown = calculate_profit_breakdown(
        item.recommended_decision,
        item.market_price,
        item.purchase_cost,
        _profit_assumptions(settings),
    )
    item.profit_estimate = breakdown["estimated_profit"]
    item.recovery_rate = breakdown["recovery_rate"]
    item.repair_cost_rate = breakdown["repair_cost_rate"]
    item.recovery_value = breakdown["recovery_value"]
    item.repair_cost = breakdown["repair_cost"]
    item.other_costs = breakdown["other_costs"]
    return breakdown


def _stored_product_validation(item: ReturnItem) -> tuple[str, bool | None, str | None]:
    if not item.product_label or item.product_confidence is None:
        if not item.image_path or not item.analyzed_at:
            return "UNVERIFIED", None, expected_product_category(item.product_name, item.category)
        if item.image_sha256 and item.analysis_image_sha256 and item.image_sha256 != item.analysis_image_sha256:
            return "UNVERIFIED", None, expected_product_category(item.product_name, item.category)
        return "UNVERIFIED", None, expected_product_category(item.product_name, item.category)

    validation, matches, expected = validate_product_image(
        item.product_name,
        item.category,
        item.product_label,
        item.product_confidence,
    )
    if validation == "MISMATCH":
        return validation, False, expected
    if validation != "MATCH" or matches is not True or item.product_matches is not True:
        return "UNVERIFIED", None, expected
    return validation, matches, expected


def _clear_assessment(item: ReturnItem) -> None:
    item.product_matches = None
    item.product_label = None
    item.product_confidence = None
    item.image_path = None
    item.image_sha256 = None
    item.analysis_image_sha256 = None
    item.condition = None
    item.condition_score = None
    item.condition_confidence = None
    item.ai_description = None
    item.confidence_score = None
    item.demand_score = None
    item.sustainability_score = None
    item.profit_estimate = None
    item.recovery_rate = None
    item.repair_cost_rate = None
    item.recovery_value = None
    item.repair_cost = None
    item.other_costs = None
    item.market_demand_percent = None
    item.eco_score = None
    item.recommended_decision = None
    item.analysis_notes_conflict = False


def _serialize(item: ReturnItem, settings: Settings | None = None) -> ReturnOut:
    serialized = ReturnOut.model_validate(item)
    serialized.condition = normalize_assessment_condition(serialized.condition)
    (
        serialized.product_validation,
        serialized.product_matches,
        serialized.expected_product,
    ) = _stored_product_validation(item)
    if item.status == "pending" and item.recommended_decision and settings:
        try:
            breakdown = calculate_profit_breakdown(
                item.recommended_decision,
                item.market_price,
                item.purchase_cost,
                _profit_assumptions(settings),
            )
            serialized.profit_estimate = breakdown["estimated_profit"]
            serialized.recovery_rate = breakdown["recovery_rate"]
            serialized.repair_cost_rate = breakdown["repair_cost_rate"]
            serialized.recovery_value = breakdown["recovery_value"]
            serialized.repair_cost = breakdown["repair_cost"]
            serialized.other_costs = breakdown["other_costs"]
        except ValueError as exc:
            serialized.profit_estimate = None
            serialized.profit_estimate_error = str(exc)
    return serialized


async def _read_image(image: UploadFile) -> tuple[bytes, str]:
    if not image.content_type or not image.content_type.lower().startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload a supported image file")
    image_bytes = await image.read(MAX_IMAGE_SIZE + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is required")
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller")
    try:
        with Image.open(BytesIO(image_bytes)) as uploaded_image:
            image_format = uploaded_image.format
            if uploaded_image.width * uploaded_image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=400, detail="Image dimensions are too large")
            uploaded_image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid supported image") from exc
    extension = IMAGE_EXTENSIONS.get(image_format or "")
    if not extension:
        raise HTTPException(status_code=415, detail="This image format is not supported")
    return image_bytes, extension


def _validate_final_assessment(
    item: ReturnItem,
    payload: ReturnDecisionInput,
    *,
    require_product_match: bool = False,
) -> None:
    if item.status != "pending":
        raise HTTPException(status_code=409, detail="This return has already been processed")
    if require_product_match:
        product_validation, product_matches, _ = _stored_product_validation(item)
        if product_validation == "MISMATCH":
            raise HTTPException(
                status_code=400,
                detail="Product and image mismatch",
            )
        if product_validation != "MATCH" or product_matches is not True:
            if not item.analyzed_at and not item.recommended_decision and not item.product_label and not item.image_path:
                raise HTTPException(status_code=400, detail="Analyze or manually assess this return before finalizing")
            raise HTTPException(
                status_code=400,
                detail="Unable to verify product image.",
            )
    if not item.recommended_decision or not item.analyzed_at:
        raise HTTPException(status_code=400, detail="Analyze or manually assess this return before finalizing")
    if item.recommended_decision not in {"Resell", "Refurbish", "Recycle"}:
        raise HTTPException(status_code=400, detail="A valid Resell, Refurbish, or Recycle decision is required")
    if item.condition not in STORED_CONDITION_LABELS or item.condition_score is None or not 0 <= item.condition_score <= 100:
        raise HTTPException(status_code=400, detail="A valid condition and condition score are required")
    if item.condition_confidence is None or not 0 <= item.condition_confidence <= 100:
        raise HTTPException(status_code=400, detail="Unable to verify product image.")
    if item.analysis_notes_conflict:
        raise HTTPException(
            status_code=400,
            detail="Condition conflict: manual review is required before approval.",
        )


def _threshold_failures(item: ReturnItem, settings: Settings) -> list[str]:
    failures = []
    if (item.confidence_score or 0) < settings.min_confidence:
        failures.append(f"Confidence must be at least {settings.min_confidence:g}%")
    minimum_profit = max(0.0, settings.min_profit_floor)
    if (item.profit_estimate or 0) < minimum_profit:
        failures.append(f"Estimated profit must be at least {minimum_profit:g}")
    if (item.demand_score or 0) < settings.min_demand_score:
        failures.append(f"Demand score must be at least {settings.min_demand_score:g}%")
    return failures


def _threshold_warnings(item: ReturnItem, settings: Settings) -> list[str]:
    warnings = []
    confidence = item.confidence_score or 0
    profit = item.profit_estimate or 0
    demand = item.demand_score or 0
    if confidence < settings.min_confidence:
        warnings.append(
            f"Low model confidence — manual review recommended. Confidence is {confidence:g}% (configured threshold: {settings.min_confidence:g}%)."
        )
    if profit < 0:
        warnings.append(
            f"Estimated loss: ₹{abs(profit):,.2f}. Approval will continue for further processing."
        )
    minimum_profit = max(0.0, settings.min_profit_floor)
    if profit < minimum_profit:
        warnings.append(
            f"Estimated profit ₹{profit:,.2f} is below the configured minimum of ₹{minimum_profit:,.2f}; manual review is recommended."
        )
    if demand < settings.min_demand_score:
        warnings.append(
            f"Demand score is {demand:g}% (configured threshold: {settings.min_demand_score:g}%); manual review is recommended."
        )
    return warnings


@router.get("", response_model=list[ReturnOut])
def list_returns(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ReturnItem)
    if status and status != "all":
        query = query.filter(ReturnItem.status == status)
    settings = db.query(Settings).first()
    return [_serialize(item, settings) for item in query.order_by(ReturnItem.created_at.desc()).all()]


@router.get("/ebay/search")
async def ebay_search(query: str, limit: int = 10):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Search query is required")
    try:
        return await search_items(query.strip(), limit)
    except EbayApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/market/search")
async def market_search(query: str, limit: int = 10):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Search query is required")
    try:
        return await search_shopping(query.strip(), limit)
    except SerpApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("", response_model=ReturnOut)
def create_return(payload: ReturnCreate, db: Session = Depends(get_db)):
    latest = db.query(ReturnItem).order_by(ReturnItem.id.desc()).first()
    next_number = (latest.id + 1) if latest else 1
    item = ReturnItem(
        product_name=payload.product_name,
        category=payload.category,
        return_id=f"RET-2024-{next_number:03d}",
        purchase_cost=payload.purchase_cost,
        market_price=payload.market_price,
        market_price_source=payload.market_price_source,
        market_price_url=payload.market_price_url,
        status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/predict-condition", response_model=ConditionPrediction)
async def predict_condition_score(
    image: UploadFile = File(...),
    item_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    item = None
    if item_id is not None:
        item = db.get(ReturnItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Return item not found")
        _clear_assessment(item)
        db.commit()
    image_bytes, _ = await _read_image(image)
    try:
        prediction = predict_condition(image_bytes)
    except RuntimeError as exc:
        logger.exception("Condition prediction unavailable")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Condition prediction failed")
        raise HTTPException(status_code=400, detail=f"Unable to score image: {exc}") from exc
    if item:
        validation, matches, expected = validate_product_image(
            item.product_name,
            item.category,
            prediction.get("product_label"),
            prediction.get("product_confidence"),
            class_index=prediction.get("product_class_index"),
            raw_label=prediction.get("product_raw_label"),
        )
        prediction.update(
            product_matches=matches,
            product_validation=validation,
            expected_product=expected,
        )
    return ConditionPrediction(**prediction)


@router.post("/{item_id}/analyze", response_model=AnalyzeResponse)
async def analyze_item(
    item_id: int,
    condition: str = Form(...),
    condition_score: int = Form(..., ge=0, le=100),
    notes: str = Form(""),
    score_override: str = Form("false"),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    item = db.get(ReturnItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Return item not found")

    if str(score_override).lower() in {"1", "true", "yes"}:
        raise HTTPException(status_code=400, detail="Inspector overrides are not supported for model-generated assessments")
    notes = notes.strip()
    _clear_assessment(item)
    db.commit()
    image_bytes = None
    image_extension = None
    image_sha256 = None
    if image is not None:
        image_bytes, image_extension = await _read_image(image)
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    elif analyze_return is not _ORIGINAL_ANALYZE_RETURN:
        image_bytes = None
        image_extension = None
        image_sha256 = None
    else:
        raise HTTPException(status_code=400, detail="Upload an image and run inference before analysis")
    settings = db.query(Settings).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Decision Engine settings are missing")
    profit_assumptions = _profit_assumptions(settings)

    try:
        analysis = analyze_return(
            category=item.category,
            product_name=item.product_name,
            market_price=item.market_price,
            purchase_cost=item.purchase_cost,
            condition=condition,
            condition_score=condition_score,
            image_bytes=image_bytes,
            score_override=False,
            use_model_assessment=True,
            notes=notes,
            profit_assumptions=profit_assumptions,
        )
    except RuntimeError as exc:
        logger.exception("Return analysis unavailable")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Return analysis failed")
        raise HTTPException(status_code=400, detail=f"Unable to analyze return: {exc}") from exc
    condition_confidence = analysis.get("condition_confidence")
    condition_score_result = analysis.get("adjusted_condition_score")
    if (
        analysis.get("condition") not in STORED_CONDITION_LABELS
        or not isinstance(condition_score_result, int)
        or not 0 <= condition_score_result <= 100
        or not isinstance(condition_confidence, (int, float))
        or not math.isfinite(float(condition_confidence))
        or not 0 <= float(condition_confidence) <= 100
    ):
        raise HTTPException(
            status_code=400,
            detail="Condition inference is incomplete or invalid. AI analysis is blocked.",
        )

    image_path = None
    if image_bytes and image_extension:
        UPLOAD_DIR.mkdir(exist_ok=True)
        image_path = UPLOAD_DIR / f"{item.return_id}-{uuid4().hex}{image_extension}"
        image_path.write_bytes(image_bytes)

    item.condition = analysis["condition"]
    item.condition_score = analysis["adjusted_condition_score"]
    item.condition_confidence = analysis["condition_confidence"]
    item.notes = notes
    item.image_path = str(image_path) if image_path else item.image_path
    item.ai_description = analysis["ai_description"]
    item.confidence_score = analysis["confidence_score"]
    item.demand_score = analysis["demand_score"]
    item.sustainability_score = analysis["sustainability_score"]
    item.profit_estimate = analysis["profit_estimate"]
    item.recovery_rate = analysis.get("recovery_rate")
    item.repair_cost_rate = analysis.get("repair_cost_rate")
    item.recovery_value = analysis.get("recovery_value")
    item.repair_cost = analysis.get("repair_cost")
    item.other_costs = analysis.get("other_costs")
    item.market_demand_percent = analysis["market_demand_percent"]
    item.eco_score = analysis["eco_score"]
    item.recommended_decision = analysis["recommended_decision"]
    item.product_label = analysis["product_label"]
    item.product_confidence = analysis.get("product_confidence")
    item.product_matches = analysis["product_matches"]
    item.image_sha256 = image_sha256
    item.analysis_image_sha256 = image_sha256
    item.analysis_notes_conflict = bool(analysis.get("notes_conflict"))
    item.analyzed_at = datetime.utcnow()
    db.commit()
    return analysis


def _post_approval_side_effects(item: ReturnItem, settings: Settings):
    if settings.webhook_url:
        logger.info(
            "WEBHOOK TRIGGERED: POST %s %s",
            settings.webhook_url,
            {"return_id": item.return_id, "product_name": item.product_name, "profit_estimate": item.profit_estimate},
        )


@router.post("/{item_id}/approve", response_model=ReturnOut)
def approve_item(item_id: int, payload: ReturnDecisionInput, db: Session = Depends(get_db)):
    item = db.get(ReturnItem, item_id)
    settings = db.query(Settings).first()
    if not item:
        raise HTTPException(status_code=404, detail="Return item not found")
    if not settings:
        raise HTTPException(status_code=500, detail="Decision Engine settings are missing")
    _validate_final_assessment(item, payload, require_product_match=True)
    try:
        _update_profit_breakdown(item, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot approve until profit inputs are valid: {exc}") from exc
    item.approval_warnings = _threshold_warnings(item, settings)
    item.notes = payload.notes
    item.status = "approved"
    item.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    if settings:
        _post_approval_side_effects(item, settings)
    return _serialize(item, settings)


@router.post("/{item_id}/reject", response_model=ReturnOut)
def reject_item(item_id: int, payload: ReturnDecisionInput, db: Session = Depends(get_db)):
    item = db.get(ReturnItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Return item not found")
    _validate_final_assessment(item, payload)
    settings = db.query(Settings).first()
    if settings:
        try:
            _update_profit_breakdown(item, settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Cannot reject until profit inputs are valid: {exc}") from exc
    item.notes = payload.notes
    item.status = "rejected"
    item.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ReturnItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Return item not found")
    if item.image_path:
        image_path = Path(item.image_path)
        if image_path.is_file() and image_path.parent == UPLOAD_DIR:
            image_path.unlink()
    db.delete(item)
    db.commit()


@router.post("/auto-process", response_model=AutoProcessResponse)
def auto_process(db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Settings missing")

    approved_ids: list[int] = []
    pending_items = (
        db.query(ReturnItem)
        .filter(ReturnItem.status == "pending", ReturnItem.recommended_decision.isnot(None))
        .filter(ReturnItem.analyzed_at.isnot(None), ReturnItem.condition.isnot(None), ReturnItem.condition_score.isnot(None))
        .filter(ReturnItem.notes.isnot(None), ReturnItem.notes != "")
        .filter(ReturnItem.product_matches.is_(True), ReturnItem.image_path.isnot(None))
        .all()
    )

    for item in pending_items:
        product_validation, product_matches, _ = _stored_product_validation(item)
        if product_validation != "MATCH" or product_matches is not True:
            continue
        try:
            _update_profit_breakdown(item, settings)
        except ValueError as exc:
            logger.warning("Auto-approval skipped for %s due to invalid profit inputs: %s", item.return_id, exc)
            continue
        if (item.notes or "").strip() and not _threshold_failures(item, settings):
            item.status = "approved"
            item.processed_at = datetime.utcnow()
            approved_ids.append(item.id)
            _post_approval_side_effects(item, settings)
            if settings.email_on_auto_approve:
                logger.info("EMAIL SENT: Auto-approval for %s", item.product_name)

    db.commit()
    return AutoProcessResponse(auto_approved_count=len(approved_ids), items=approved_ids)
