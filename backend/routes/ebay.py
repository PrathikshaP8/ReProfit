from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import ReturnItem
from schemas import EbayImport, ReturnOut


router = APIRouter(prefix="/api/ebay", tags=["ebay"])


@router.post("/import", response_model=ReturnOut)
def import_ebay_item(payload: EbayImport, db: Session = Depends(get_db)):
    latest = db.query(ReturnItem).order_by(ReturnItem.id.desc()).first()
    next_number = (latest.id + 1) if latest else 1
    item = ReturnItem(
        product_name=payload.product_name,
        category=payload.category,
        return_id=f"RET-2024-{next_number:03d}",
        purchase_cost=payload.purchase_cost,
        market_price=payload.market_price,
        status="pending",
        notes=None,
        market_price_source=payload.market_price_source,
        market_price_listing_id=payload.market_price_listing_id or payload.ebay_item_id,
        market_price_url=payload.market_price_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item