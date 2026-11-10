from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect, text
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from database import Base, SessionLocal, engine
from models import ReturnItem, Settings
from routes.analytics import router as analytics_router
from routes.dashboard import router as dashboard_router
from routes.ebay import router as ebay_router
from routes.returns import router as returns_router
from routes.settings import router as settings_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
load_dotenv()

app = FastAPI(title="ReProfit API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174","http://localhost:8000", "https://re-profit-web-app.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=Path(__file__).resolve().parent / "uploads"), name="uploads")

app.include_router(dashboard_router)
app.include_router(returns_router)
app.include_router(ebay_router)
app.include_router(analytics_router)
app.include_router(settings_router)


SEED_ITEMS = [
    ("iPhone 13 Pro 128GB", "Electronics", 72000, 88000, "approved", "Like New", 93, "Other", "Resell", 74800, 95, 92, 95, 97, 92, 5),
    ("Samsung Galaxy A54", "Electronics", 26000, 32999, "pending", None, None, None, None, None, None, None, None, None, None, 1),
    ("Nike Air Max 270", "Apparel", 8500, 12999, "approved", "Good", 78, "Found better price", "Refurbish", 6749, 84, 79, 80, 82, 80, 3),
    ("Sony WH-1000XM4", "Electronics", 18000, 24990, "approved", "Good", 89, "Other", "Resell", 21242, 96, 91, 95, 96, 91, 9),
    ("Dell XPS 13 Battery", "Electronics", 4200, 6999, "rejected", "Poor", 42, "Defective", "Recycle", 420, 66, 72, 60, 62, 60, 2),
    ("Boat Rockerz 450", "Electronics", 1100, 1999, "pending", None, None, None, None, None, None, None, None, None, None, 0),
    ("Realme Watch 3", "Electronics", 2200, 3799, "approved", "Good", 82, "Not as described", "Resell", 3229, 94, 88, 95, 95, 88, 7),
    ("Puma Running Shoes", "Apparel", 3200, 5999, "pending", None, None, None, None, None, None, None, None, None, None, 0),
    ("Apple Watch SE", "Electronics", 18500, 29999, "approved", "Fair", 74, "Other", "Refurbish", 15899, 86, 90, 80, 81, 80, 12),
    ("OnePlus Nord Buds", "Electronics", 1800, 2999, "rejected", "Damaged", 31, "Defective", "Recycle", 180, 61, 86, 60, 59, 60, 6),
    ("Levi's 511 Jeans", "Apparel", 1800, 3499, "approved", "Good", 77, "Wrong item", "Refurbish", 1914, 81, 78, 80, 80, 80, 11),
    ("Canon EF 50mm Lens", "Accessories", 6500, 9999, "pending", None, None, None, None, None, None, None, None, None, None, 0),
    ("JBL Charge 5", "Electronics", 8200, 12999, "approved", "Like New", 91, "Found better price", "Resell", 11049, 97, 89, 95, 97, 95, 4),
    ("Fitbit Inspire 3", "Accessories", 5200, 8999, "pending", None, None, None, None, None, None, None, None, None, None, 0),
    ("HP 65W Laptop Chargertesting", "Accessories", 900, 1799, "approved", "Fair", 55, "Other", "Refurbish", 989, 73, 76, 80, 78, 80, 8)
    
]


def init_db():
    Base.metadata.create_all(bind=engine)
    existing_columns = {column["name"] for column in inspect(engine).get_columns("return_items")}
    existing_settings_columns = {column["name"] for column in inspect(engine).get_columns("settings")}
    with engine.begin() as connection:
        if "product_label" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN product_label VARCHAR(100)"))
        if "product_matches" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN product_matches BOOLEAN"))
        if "product_confidence" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN product_confidence FLOAT"))
        if "condition_confidence" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN condition_confidence FLOAT"))
        if "image_sha256" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN image_sha256 VARCHAR(64)"))
        if "analysis_image_sha256" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN analysis_image_sha256 VARCHAR(64)"))
        if "analysis_notes_conflict" not in existing_columns:
            connection.execute(text("ALTER TABLE return_items ADD COLUMN analysis_notes_conflict BOOLEAN DEFAULT 0 NOT NULL"))
        for column in ("market_price_source", "market_price_listing_id", "market_price_url", "recovery_rate", "repair_cost_rate", "recovery_value", "repair_cost", "other_costs", "approval_warnings"):
            if column not in existing_columns:
                column_type = (
                    "VARCHAR(1000)" if column == "market_price_url"
                    else "VARCHAR(255)" if column == "market_price_listing_id"
                    else "JSON" if column == "approval_warnings"
                    else "VARCHAR(100)" if column == "market_price_source"
                    else "FLOAT"
                )
                connection.execute(text(f"ALTER TABLE return_items ADD COLUMN {column} {column_type}"))
        for column, default in (
            ("resell_recovery_rate", 0.85),
            ("refurbish_recovery_rate", 0.65),
            ("refurbish_cost_rate", 0.12),
            ("recycle_recovery_rate", 0.08),
            ("other_costs_per_item", 0),
        ):
            if column not in existing_settings_columns:
                connection.execute(
                    text(f"ALTER TABLE settings ADD COLUMN {column} FLOAT NOT NULL DEFAULT {default}")
                )
    db = SessionLocal()
    try:
        if not db.query(Settings).first():
            db.add(Settings(api_key=str(uuid4())))
            db.commit()

        if db.query(ReturnItem).count() == 0:
            now = datetime.utcnow()
            for idx, item in enumerate(SEED_ITEMS, start=1):
                (
                    product_name,
                    category,
                    purchase_cost,
                    market_price,
                    status,
                    condition,
                    condition_score,
                    return_reason,
                    decision,
                    profit,
                    confidence,
                    demand,
                    sustainability,
                    eco,
                    market_demand,
                    days_ago,
                ) = item
                processed_at = now - timedelta(days=days_ago) if status != "pending" else None
                analyzed_at = processed_at - timedelta(hours=2) if processed_at else None
                db.add(
                    ReturnItem(
                        product_name=product_name,
                        category=category,
                        return_id=f"RET-2024-{idx:03d}",
                        purchase_cost=purchase_cost,
                        market_price=market_price,
                        status=status,
                        condition=condition,
                        return_reason=return_reason,
                        condition_score=condition_score,
                        notes="Seeded demo return item",
                        ai_description=(
                            "Item appears brand new, box seal intact"
                            if condition == "Like New"
                            else "Minor signs of use, fully functional"
                            if condition == "Good"
                            else "Visible wear, functionality intact"
                            if condition == "Fair"
                            else "Significant wear, may need repairs"
                            if condition == "Poor"
                            else "Physical damage present, repair required"
                            if condition == "Damaged"
                            else None
                        ),
                        confidence_score=confidence,
                        demand_score=demand,
                        sustainability_score=sustainability,
                        profit_estimate=profit,
                        market_demand_percent=market_demand,
                        eco_score=eco,
                        recommended_decision=decision,
                        created_at=now - timedelta(days=days_ago + 3),
                        analyzed_at=analyzed_at,
                        processed_at=processed_at,
                    )
                )
            db.commit()
    finally:
        db.close()


@app.get("/")
def health():
    return {"status": "ok", "service": "ReProfit API"}


@app.on_event("startup")
def on_startup():
    init_db()


if __name__ == "__main__":
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
