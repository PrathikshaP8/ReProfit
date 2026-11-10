from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import ReturnItem
from routes import analytics


class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine)
        cls.app = FastAPI()
        cls.app.include_router(analytics.router)

        def override_get_db():
            with cls.session_factory() as session:
                yield session

        cls.app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.engine.dispose()

    def setUp(self):
        with self.session_factory() as session:
            session.query(ReturnItem).delete()
            session.commit()

    def _add_item(
        self,
        *,
        category: str,
        status: str,
        profit: float | None,
        processed_days_ago: int | None,
        created_days_ago: int = 0,
        decision: str | None = "Resell",
        condition: str | None = "Good",
    ) -> None:
        now = datetime.utcnow()
        processed_at = now - timedelta(days=processed_days_ago) if processed_days_ago is not None else None
        with self.session_factory() as session:
            session.add(
                ReturnItem(
                    product_name=f"{category} item",
                    category=category,
                    return_id=f"RET-{session.query(ReturnItem).count() + 1}",
                    purchase_cost=100,
                    market_price=200,
                    status=status,
                    profit_estimate=profit,
                    processed_at=processed_at,
                    created_at=now - timedelta(days=created_days_ago),
                    recommended_decision=decision,
                    condition=condition,
                )
            )
            session.commit()

    def test_financial_analytics_share_the_range_and_only_count_realized_approved_items(self):
        self._add_item(category="Alpha", status="approved", profit=100, processed_days_ago=0)
        self._add_item(category="Beta", status="approved", profit=-150, processed_days_ago=0, decision="Recycle")
        self._add_item(category="Beta", status="approved", profit=40, processed_days_ago=0, decision="Refurbish")
        self._add_item(category="Old", status="approved", profit=-80, processed_days_ago=8)
        self._add_item(category="Older", status="approved", profit=60, processed_days_ago=31)
        self._add_item(category="Outside", status="approved", profit=500, processed_days_ago=91)
        self._add_item(category="Rejected", status="rejected", profit=1000, processed_days_ago=0)
        self._add_item(category="Pending", status="pending", profit=2000, processed_days_ago=0)
        self._add_item(category="Missing estimate", status="approved", profit=None, processed_days_ago=0)
        self._add_item(category="Unprocessed", status="approved", profit=3000, processed_days_ago=None)

        expected = {
            7: (-10.0, 3, {"Alpha": (100.0, 1), "Beta": (-110.0, 2)}),
            30: (-90.0, 4, {"Alpha": (100.0, 1), "Beta": (-110.0, 2), "Old": (-80.0, 1)}),
            90: (-30.0, 5, {"Alpha": (100.0, 1), "Beta": (-110.0, 2), "Old": (-80.0, 1), "Older": (60.0, 1)}),
        }

        for period, (total, count, category_results) in expected.items():
            with self.subTest(period=period):
                daily = self.client.get(f"/api/analytics/daily-profit?range={period}")
                categories = self.client.get(f"/api/analytics/category-breakdown?range={period}")
                self.assertEqual(daily.status_code, 200, daily.text)
                self.assertEqual(categories.status_code, 200, categories.text)
                self.assertEqual(round(sum(day["profit_recovered"] for day in daily.json()), 2), total)
                self.assertEqual(sum(day["item_count"] for day in daily.json()), count)
                self.assertEqual(
                    {
                        row["category"]: (row["total_profit"], row["count"])
                        for row in categories.json()
                    },
                    category_results,
                )

    def test_empty_range_returns_no_categories_or_best_day_candidates(self):
        self._add_item(category="Old", status="approved", profit=50, processed_days_ago=100)

        self.assertEqual(self.client.get("/api/analytics/category-breakdown?range=7").json(), [])
        days = self.client.get("/api/analytics/daily-profit?range=7").json()
        self.assertEqual(len(days), 7)
        self.assertTrue(all(day["profit_recovered"] == 0 and day["item_count"] == 0 for day in days))

    def test_condition_chart_uses_selected_intake_date_window_and_returns_supported_categories(self):
        self._add_item(category="Current pending", status="pending", profit=None, processed_days_ago=None)
        self._add_item(category="Current like new", status="pending", profit=None, processed_days_ago=None, condition="Like New")
        self._add_item(category="Current poor", status="pending", profit=None, processed_days_ago=None, condition="Poor")
        self._add_item(
            category="Old rejected",
            status="rejected",
            profit=None,
            processed_days_ago=None,
            created_days_ago=8,
            condition="Fair",
        )

        conditions = self.client.get("/api/analytics/condition-distribution?range=7")
        self.assertEqual(conditions.status_code, 200, conditions.text)
        self.assertEqual(
            conditions.json(),
            [
                {"condition": "Damaged", "count": 0},
                {"condition": "Bad", "count": 1},
                {"condition": "Fair", "count": 0},
                {"condition": "Good", "count": 2},
            ],
        )

    def test_invalid_period_is_rejected_by_each_range_aware_endpoint(self):
        self.assertEqual(self.client.get("/api/analytics/daily-profit?range=14").status_code, 400)
        self.assertEqual(self.client.get("/api/analytics/category-breakdown?range=14").status_code, 400)
        self.assertEqual(self.client.get("/api/analytics/condition-distribution?range=14").status_code, 400)


if __name__ == "__main__":
    unittest.main()
