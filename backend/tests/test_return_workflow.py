from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import ReturnItem, Settings
from routes import analytics, dashboard, ebay as ebay_routes, returns, settings as settings_routes


class ReturnWorkflowTests(unittest.TestCase):
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
        cls.app.include_router(returns.router)
        cls.app.include_router(dashboard.router)
        cls.app.include_router(analytics.router)
        cls.app.include_router(ebay_routes.router)
        cls.app.include_router(settings_routes.router)

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
            session.query(Settings).delete()
            session.add(
                Settings(
                    id=1,
                    min_confidence=85,
                    min_profit_floor=500,
                    min_demand_score=70,
                )
            )
            session.commit()

    def _create_item(self, *, analyzed: bool = True) -> int:
        with self.session_factory() as session:
            item = ReturnItem(
                product_name="Test phone",
                category="Electronics",
                return_id=f"RET-TEST-{session.query(ReturnItem).count() + 1:03d}",
                purchase_cost=250,
                market_price=1000,
                status="pending",
                condition="Good" if analyzed else None,
                condition_score=76 if analyzed else None,
                condition_confidence=89.2 if analyzed else None,
                confidence_score=90 if analyzed else None,
                profit_estimate=600 if analyzed else None,
                demand_score=80 if analyzed else None,
                recommended_decision="Resell" if analyzed else None,
                image_path="verified-test-image.png" if analyzed else None,
                product_label="Mobile Phone" if analyzed else None,
                product_confidence=92 if analyzed else None,
                product_matches=True if analyzed else None,
                analyzed_at=datetime.now() if analyzed else None,
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return item.id

    def _mutate_item(self, item_id: int, **changes) -> None:
        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            for field, value in changes.items():
                setattr(item, field, value)
            session.commit()

    def _approve_item(self, item_id: int, notes: str = "Approved for processing") -> dict:
        response = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": notes},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _reject_item(self, item_id: int, notes: str = "Rejected after review") -> dict:
        response = self.client.post(
            f"/api/returns/{item_id}/reject",
            json={"notes": notes},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_approval_requires_a_nonblank_note_and_persists_trimmed_note(self):
        item_id = self._create_item()
        url = f"/api/returns/{item_id}/approve"
        with self.session_factory() as session:
            session.get(ReturnItem, item_id).return_reason = "Defective"
            session.commit()

        self.assertEqual(self.client.post(url).status_code, 422)
        self.assertEqual(
            self.client.post(url, json={"notes": "   "}).status_code,
            422,
        )

        response = self.client.post(
            url,
            json={"notes": "  Screen checked; no visible issues.  "},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["notes"], "Screen checked; no visible issues.")
        with self.session_factory() as session:
            saved = session.get(ReturnItem, item_id)
            self.assertEqual(saved.notes, "Screen checked; no visible issues.")
            self.assertEqual(saved.status, "approved")
            self.assertEqual(saved.return_reason, "Defective")
        saved_item = next(
            item for item in self.client.get("/api/returns?status=all").json()
            if item["id"] == item_id
        )
        self.assertEqual(saved_item["notes"], "Screen checked; no visible issues.")
        self.assertEqual(self.client.get("/api/dashboard/summary").status_code, 200)
        self.assertEqual(self.client.get("/api/analytics/condition-distribution").status_code, 200)

    def test_approval_requires_a_saved_assessment(self):
        item_id = self._create_item(analyzed=False)

        response = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Inspected manually."},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Analyze or manually assess", response.json()["detail"])

    def test_approval_continues_with_confidence_profit_and_demand_warnings(self):
        failures = (
            ("confidence_score", 84, "Low model confidence"),
            ("purchase_cost", 351, "Estimated profit"),
            ("demand_score", 69, "Demand score"),
        )
        for field, below_threshold, message in failures:
            item_id = self._create_item()
            with self.session_factory() as session:
                item = session.get(ReturnItem, item_id)
                if field == "profit_estimate":
                    item.purchase_cost = below_threshold
                else:
                    setattr(item, field, below_threshold)
                session.commit()
            response = self.client.post(
                f"/api/returns/{item_id}/approve",
                json={"notes": "Inspected and ready for manual review."},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "approved")
            self.assertEqual(response.json()["recommended_decision"], "Resell")
            self.assertTrue(any(message in warning for warning in response.json()["approval_warnings"]))
            refreshed = self.client.get("/api/returns?status=approved")
            persisted = next(item for item in refreshed.json() if item["id"] == item_id)
            self.assertEqual(persisted["status"], "approved")
            self.assertEqual(persisted["recommended_decision"], "Resell")
            self.assertTrue(any(message in warning for warning in persisted["approval_warnings"]))

    def test_refurbish_recommendation_is_saved_when_approved(self):
        item_id = self._create_item()
        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            item.recommended_decision = "Refurbish"
            item.confidence_score = 54
            session.commit()

        response = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Inspected and routed for refurbishment."},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "approved")
        self.assertEqual(response.json()["recommended_decision"], "Refurbish")
        with self.session_factory() as session:
            saved = session.get(ReturnItem, item_id)
            self.assertEqual(saved.status, "approved")
            self.assertEqual(saved.recommended_decision, "Refurbish")

    def test_dashboard_summary_uses_only_approved_positive_and_negative_estimates(self):
        positive_id = self._create_item()
        self._mutate_item(positive_id, purchase_cost=250, market_price=1000, recommended_decision="Resell")
        negative_id = self._create_item()
        self._mutate_item(negative_id, purchase_cost=2000, market_price=1000, recommended_decision="Resell")
        pending_id = self._create_item()
        rejected_id = self._create_item()

        self._approve_item(positive_id, "Approved profitable item")
        self._approve_item(negative_id, "Approved loss-making item")
        self._reject_item(rejected_id, "Rejected item should not affect dashboard averages")

        summary = self.client.get("/api/dashboard/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        data = summary.json()
        self.assertEqual(data["average_profit"], 600.0)
        self.assertEqual(data["average_loss"], 1150.0)

        approved_returns = self.client.get("/api/returns?status=approved").json()
        self.assertEqual({item["id"] for item in approved_returns}, {positive_id, negative_id})
        pending_returns = self.client.get("/api/returns?status=pending").json()
        self.assertIn(pending_id, {item["id"] for item in pending_returns})
        self.assertEqual(self.client.get("/api/dashboard/trend?period=weekly").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/decision-split").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/recent-decisions").status_code, 200)

    def test_dashboard_summary_returns_zero_when_a_bucket_is_empty(self):
        positive_id = self._create_item()
        self._mutate_item(positive_id, purchase_cost=250, market_price=1000, recommended_decision="Resell")
        self._approve_item(positive_id, "Approved profitable item")

        summary = self.client.get("/api/dashboard/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        data = summary.json()
        self.assertEqual(data["average_profit"], 600.0)
        self.assertEqual(data["average_loss"], 0.0)

        with self.session_factory() as session:
            session.query(ReturnItem).delete()
            session.commit()

        summary = self.client.get("/api/dashboard/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        data = summary.json()
        self.assertEqual(data["average_profit"], 0.0)
        self.assertEqual(data["average_loss"], 0.0)

    def test_hp_victus_recycling_loss_is_approved_with_persisted_warning(self):
        item_id = self._create_item()
        with self.session_factory() as session:
            settings = session.query(Settings).one()
            settings.min_profit_floor = 385
            item = session.get(ReturnItem, item_id)
            item.product_name = "HP Victus 15-fa2197TX"
            item.product_label = "Laptop"
            item.product_confidence = 92
            item.product_matches = True
            item.image_path = "verified-test-image.png"
            item.market_price = 83495
            item.purchase_cost = 80000
            item.recommended_decision = "Recycle"
            item.profit_estimate = -73320.4
            session.commit()

        listed = self.client.get("/api/returns?status=pending")
        self.assertEqual(listed.status_code, 200, listed.text)
        hp_return = next(item for item in listed.json() if item["id"] == item_id)
        self.assertEqual(hp_return["market_price"], 83495)
        self.assertEqual(hp_return["purchase_cost"], 80000)
        self.assertEqual(hp_return["recovery_rate"], 0.08)
        self.assertEqual(hp_return["recovery_value"], 6679.6)
        self.assertEqual(hp_return["repair_cost"], 0)
        self.assertEqual(hp_return["other_costs"], 0)
        self.assertEqual(hp_return["profit_estimate"], -73320.4)

        response = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Reviewed damaged HP Victus; recycling recovery does not meet profit floor."},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "approved")
        self.assertEqual(response.json()["recommended_decision"], "Recycle")
        self.assertEqual(response.json()["profit_estimate"], -73320.4)
        self.assertTrue(any("Estimated loss: ₹73,320.40" in warning for warning in response.json()["approval_warnings"]))
        self.assertTrue(any("configured minimum of ₹385.00" in warning for warning in response.json()["approval_warnings"]))
        self.assertEqual(
            response.json()["notes"],
            "Reviewed damaged HP Victus; recycling recovery does not meet profit floor.",
        )
        with self.session_factory() as session:
            saved = session.get(ReturnItem, item_id)
            self.assertEqual(saved.status, "approved")
            self.assertEqual(saved.recommended_decision, "Recycle")
            self.assertEqual(saved.profit_estimate, -73320.4)
        refreshed = self.client.get("/api/returns?status=approved")
        persisted = next(item for item in refreshed.json() if item["id"] == item_id)
        self.assertEqual(persisted["approval_warnings"], response.json()["approval_warnings"])

    def test_approval_rejects_invalid_saved_decision(self):
        item_id = self._create_item()
        with self.session_factory() as session:
            session.get(ReturnItem, item_id).recommended_decision = "Unknown"
            session.commit()

        response = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Assessment checked."},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid Resell, Refurbish, or Recycle", response.json()["detail"])

    def test_changing_recovery_settings_recalculates_pending_profit_breakdown(self):
        item_id = self._create_item()
        settings_response = self.client.get("/api/settings/thresholds")
        self.assertEqual(settings_response.status_code, 200, settings_response.text)
        payload = settings_response.json()
        payload["resell_recovery_rate"] = 0.5
        payload["other_costs_per_item"] = 10

        response = self.client.patch("/api/settings/thresholds", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            self.assertEqual(item.recovery_value, 500)
            self.assertEqual(item.other_costs, 10)
            self.assertEqual(item.profit_estimate, 240)

    def test_rejection_requires_and_persists_note_without_return_reason(self):
        item_id = self._create_item()

        response = self.client.post(
            f"/api/returns/{item_id}/reject",
            json={"notes": "Ports inspected; item does not power on."},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertEqual(response.json()["notes"], "Ports inspected; item does not power on.")

    def test_delete_still_removes_return(self):
        item_id = self._create_item(analyzed=False)

        response = self.client.delete(f"/api/returns/{item_id}")

        self.assertEqual(response.status_code, 204)
        remaining = self.client.get("/api/returns?status=all").json()
        self.assertFalse(any(item["id"] == item_id for item in remaining))

    def test_market_listing_import_preserves_provenance_without_prefilling_inspector_note(self):
        response = self.client.post(
            "/api/ebay/import",
            json={
                "ebay_item_id": "serp-product-123",
                "product_name": "HP Victus exact model listing",
                "category": "Electronics",
                "purchase_cost": 80000,
                "market_price": 83495,
                "market_price_source": "SerpAPI",
                "market_price_url": "https://example.test/listing/123",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["market_price_source"], "SerpAPI")
        self.assertEqual(response.json()["market_price_listing_id"], "serp-product-123")
        self.assertEqual(response.json()["market_price_url"], "https://example.test/listing/123")
        self.assertIsNone(response.json()["notes"])

    def test_legacy_condition_labels_are_normalized_without_changing_records(self):
        with self.session_factory() as session:
            session.add_all(
                [
                    ReturnItem(
                        product_name="Legacy item",
                        category="Electronics",
                        return_id="RET-LEGACY-001",
                        purchase_cost=100,
                        market_price=200,
                        condition="Like New",
                        condition_score=92,
                    ),
                    ReturnItem(
                        product_name="Legacy item",
                        category="Electronics",
                        return_id="RET-LEGACY-002",
                        purchase_cost=100,
                        market_price=200,
                        condition="Poor",
                        condition_score=35,
                    ),
                ]
            )
            session.commit()

        listed = self.client.get("/api/returns?status=all")
        conditions = {item["return_id"]: item["condition"] for item in listed.json()}
        distribution = {
            item["condition"]: item["count"]
            for item in self.client.get("/api/analytics/condition-distribution").json()
        }

        self.assertEqual(conditions["RET-LEGACY-001"], "Good")
        self.assertEqual(conditions["RET-LEGACY-002"], "Bad")
        self.assertEqual(distribution["Good"], 1)
        self.assertEqual(distribution["Bad"], 1)
        with self.session_factory() as session:
            self.assertEqual(session.query(ReturnItem).filter_by(return_id="RET-LEGACY-001").one().condition, "Like New")
            self.assertEqual(session.query(ReturnItem).filter_by(return_id="RET-LEGACY-002").one().condition, "Poor")

    def test_condition_prediction_accepts_valid_images_and_rejects_invalid_files(self):
        item_id = self._create_item()
        image = BytesIO()
        Image.new("RGB", (12, 12), "blue").save(image, format="PNG")
        prediction = {
            "condition": "Bad",
            "condition_score": 36,
            "confidence": 83.5,
            "model_name": "trained-test-model",
            "source": "yolo11-cls",
        }

        with patch.object(returns, "predict_condition", return_value=prediction):
            valid = self.client.post(
                "/api/returns/predict-condition",
                files={"image": ("item.png", image.getvalue(), "image/png")},
            )
        invalid = self.client.post(
            "/api/returns/predict-condition",
            files={"image": ("item.png", b"not an image", "image/png")},
        )

        self.assertEqual(valid.status_code, 200, valid.text)
        self.assertEqual(valid.json()["condition"], "Bad")
        self.assertEqual(valid.json()["condition_score"], 36)
        self.assertEqual(invalid.status_code, 400)
        listed = self.client.get("/api/returns?status=all")
        self.assertEqual(listed.status_code, 200, listed.text)
        persisted = next(item for item in listed.json() if item["id"] == item_id)
        self.assertEqual(persisted["condition_confidence"], 89.2)

    def test_analysis_saves_trimmed_note_condition_score_and_model_confidence(self):
        item_id = self._create_item(analyzed=False)
        analysis = {
            "condition": "Good",
            "ai_description": "Condition classified as good.",
            "confidence_score": 84.0,
            "condition_confidence": 88.5,
            "demand_score": 90.0,
            "sustainability_score": 82.0,
            "profit_estimate": 600.0,
            "recovery_value": 850.0,
            "repair_cost": 0.0,
            "repair_cost_rate": 0.0,
            "other_costs": 0.0,
            "recovery_rate": 0.85,
            "market_demand_percent": 90.0,
            "eco_score": 95.0,
            "recommended_decision": "Resell",
            "adjusted_condition_score": 78,
            "score_source": "yolo11-cls",
            "product_label": None,
            "product_matches": None,
        }
        form = {
            "condition": "Good",
            "condition_score": "76",
            "notes": "  Verified screen and ports.  ",
            "score_override": "false",
        }

        with patch.object(returns, "analyze_return", return_value=analysis):
            response = self.client.post(
                f"/api/returns/{item_id}/analyze",
                files={key: (None, value) for key, value in form.items()},
            )

        self.assertEqual(response.status_code, 200, response.text)
        listed = self.client.get("/api/returns?status=all")
        saved = next(item for item in listed.json() if item["id"] == item_id)
        self.assertEqual(saved["condition"], "Good")
        self.assertEqual(saved["condition_score"], 78)
        self.assertEqual(saved["condition_confidence"], 88.5)
        self.assertEqual(saved["notes"], "Verified screen and ports.")
        self.assertEqual(saved["profit_estimate"], 600.0)
        self.assertEqual(saved["product_validation"], "UNVERIFIED")

    def test_analysis_requires_current_image_and_rejects_score_override(self):
        item_id = self._create_item(analyzed=False)
        no_image = self.client.post(
            f"/api/returns/{item_id}/analyze",
            files={
                "condition": (None, "Good"),
                "condition_score": (None, "76"),
                "notes": (None, "Image required."),
            },
        )
        self.assertEqual(no_image.status_code, 400)
        self.assertIn("Upload an image", no_image.json()["detail"])

        override = self.client.post(
            f"/api/returns/{item_id}/analyze",
            files={
                "condition": (None, "Good"),
                "condition_score": (None, "1"),
                "score_override": (None, "true"),
                "image": ("item.png", self._image_bytes(), "image/png"),
            },
        )
        self.assertEqual(override.status_code, 400)
        self.assertIn("overrides are not supported", override.json()["detail"])

    @staticmethod
    def _image_bytes():
        image = BytesIO()
        Image.new("RGB", (16, 16), "blue").save(image, format="PNG")
        return image.getvalue()

    def test_prediction_api_returns_category_decision_and_blocks_nonmatches(self):
        scenarios = (
            ("Nothing Phone", "cell phone", 90, 67, "MATCH"),
            ("Nothing Phone", "mouse", 90, 64, "MISMATCH"),
            ("OnePlus N6 5G", "sandals", 90, 0, "MISMATCH"),
            ("HP laptop", "mouse", 90, 64, "MISMATCH"),
            ("Nothing Phone", "cell phone", 35.4, 67, "UNVERIFIED"),
            ("Nothing Phone", "unknown", 90, None, "UNVERIFIED"),
        )
        for index, (product_name, label, confidence, class_index, expected_validation) in enumerate(scenarios):
            with self.subTest(product_name=product_name, label=label, confidence=confidence):
                item_id = self._create_item()
                with self.session_factory() as session:
                    session.get(ReturnItem, item_id).product_name = product_name
                    session.commit()
                prediction = {
                    "condition": "Good",
                    "condition_score": 76,
                    "confidence": 90,
                    "model_name": "test-condition-model",
                    "source": "test",
                    "class_probabilities": {},
                    "product_label": label,
                    "product_raw_label": label,
                    "product_class_index": class_index,
                    "product_confidence": confidence,
                    "product_model_name": "yolo11n",
                }
                with patch.object(returns, "predict_condition", return_value=prediction):
                    response = self.client.post(
                        "/api/returns/predict-condition",
                        files={
                            "image": ("image.png", self._image_bytes(), "image/png"),
                            "item_id": (None, str(item_id)),
                        },
                    )

                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertEqual(result["product_validation"], expected_validation)
                self.assertEqual(result["product_class_index"], class_index)
                self.assertEqual(result["product_raw_label"], label)
                if expected_validation != "MATCH":
                    approval = self.client.post(
                        f"/api/returns/{item_id}/approve",
                        json={"notes": "Approval must remain blocked."},
                    )
                    self.assertEqual(approval.status_code, 400)
                    self.assertEqual(
                        approval.json()["detail"],
                        "Unable to verify product image.",
                    )

    @staticmethod
    def _analysis_for_product(label, confidence):
        validation, matches, expected = returns.validate_product_image(
            "HP laptop",
            "Electronics",
            label,
            confidence,
        )
        return {
            "condition": "Good",
            "ai_description": "Condition classified as good.",
            "confidence_score": 90,
            "condition_confidence": 90,
            "demand_score": 90,
            "sustainability_score": 95,
            "profit_estimate": 600,
            "recovery_value": 850,
            "repair_cost": 0,
            "repair_cost_rate": 0,
            "other_costs": 0,
            "recovery_rate": 0.85,
            "market_demand_percent": 90,
            "eco_score": 95,
            "recommended_decision": "Resell",
            "adjusted_condition_score": 76,
            "product_label": label,
            "product_confidence": confidence,
            "product_matches": matches,
            "product_validation": validation,
            "expected_product": expected,
        }

    def _analyze_with_product(self, item_id, label, confidence):
        form = {
            "condition": (None, "Good"),
            "condition_score": (None, "76"),
            "notes": (None, "Inspector verified product."),
            "score_override": (None, "false"),
            "image": ("item.png", self._image_bytes(), "image/png"),
        }
        return self.client.post(
            f"/api/returns/{item_id}/analyze",
            files=form,
        )

    def test_matching_laptop_image_is_saved_and_allows_approval(self):
        item_id = self._create_item(analyzed=False)
        with self.session_factory() as session:
            session.get(ReturnItem, item_id).product_name = "Gaming laptop HP Victus"
            session.commit()

        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            returns, "UPLOAD_DIR", Path(upload_dir)
        ), patch.object(
            returns,
            "analyze_return",
            return_value=self._analysis_for_product("Laptop", 96),
        ):
            analysis = self._analyze_with_product(item_id, "Laptop", 96)
            approval = self.client.post(
                f"/api/returns/{item_id}/approve",
                json={"notes": "Laptop identity confirmed."},
            )

        self.assertEqual(analysis.status_code, 200, analysis.text)
        self.assertEqual(analysis.json()["product_validation"], "MATCH")
        self.assertEqual(analysis.json()["expected_product"], "Laptop")
        self.assertEqual(approval.status_code, 200, approval.text)
        self.assertEqual(approval.json()["status"], "approved")

    def test_laptop_mouse_and_mobile_keyboard_mismatches_block_api_approval(self):
        for product_name, detected in (
            ("HP laptop", "Mouse"),
            ("Mobile phone", "Keyboard"),
            ("Mobile phone", "Laptop"),
            ("Mobile phone", "Sandals"),
        ):
            item_id = self._create_item(analyzed=False)
            with self.session_factory() as session:
                session.get(ReturnItem, item_id).product_name = product_name
                session.commit()
            result = self._analysis_for_product(detected, 96)
            validation, matches, expected = returns.validate_product_image(
                product_name,
                "Electronics",
                detected,
                96,
            )
            result.update(
                product_matches=matches,
                product_validation=validation,
                expected_product=expected,
            )

            with tempfile.TemporaryDirectory() as upload_dir, patch.object(
                returns, "UPLOAD_DIR", Path(upload_dir)
            ), patch.object(returns, "analyze_return", return_value=result):
                analyzed = self._analyze_with_product(item_id, detected, 96)
                approval = self.client.post(
                    f"/api/returns/{item_id}/approve",
                    json={"notes": "Inspector's note is present."},
                )

            self.assertEqual(analyzed.status_code, 200, analyzed.text)
            self.assertEqual(analyzed.json()["product_validation"], "MISMATCH")
            self.assertEqual(approval.status_code, 400)
            self.assertEqual(approval.json()["detail"], "Product and image mismatch")
            with self.session_factory() as session:
                self.assertEqual(session.get(ReturnItem, item_id).status, "pending")

    def test_low_confidence_and_missing_image_analysis_are_unverified_and_blocked(self):
        item_id = self._create_item(analyzed=False)
        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            item.product_name = "HP laptop"
            session.commit()

        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            returns, "UPLOAD_DIR", Path(upload_dir)
        ), patch.object(
            returns,
            "analyze_return",
            return_value=self._analysis_for_product("Laptop", 24.9),
        ):
            analyzed = self._analyze_with_product(item_id, "Laptop", 24.9)
            low_confidence_approval = self.client.post(
                f"/api/returns/{item_id}/approve",
                json={"notes": "Manual condition assessment complete."},
            )

        self.assertEqual(analyzed.json()["product_validation"], "UNVERIFIED")
        self.assertEqual(low_confidence_approval.status_code, 400)
        self.assertEqual(low_confidence_approval.json()["detail"], "Unable to verify product image.")

        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            item.product_matches = None
            item.product_confidence = None
            item.product_label = None
            item.image_path = None
            session.commit()
        missing_image_approval = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Inspector manually assessed condition."},
        )
        self.assertEqual(missing_image_approval.status_code, 400)
        self.assertEqual(missing_image_approval.json()["detail"], "Unable to verify product image.")
        with self.session_factory() as session:
            self.assertEqual(session.get(ReturnItem, item_id).status, "pending")

    def test_failed_upload_invalidates_previous_match_and_new_correct_image_revalidates(self):
        item_id = self._create_item()
        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            item.product_name = "HP laptop"
            session.commit()
        form = {"image": ("item.png", self._image_bytes(), "image/png"), "item_id": (None, str(item_id))}

        with patch.object(returns, "predict_condition", side_effect=RuntimeError("Model unavailable")):
            failed_prediction = self.client.post("/api/returns/predict-condition", files=form)
        self.assertEqual(failed_prediction.status_code, 503)
        blocked_after_failure = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Inspector's note is present."},
        )
        self.assertEqual(blocked_after_failure.status_code, 400)
        self.assertEqual(blocked_after_failure.json()["detail"], "Unable to verify product image.")

        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            returns, "UPLOAD_DIR", Path(upload_dir)
        ), patch.object(
            returns,
            "analyze_return",
            side_effect=[
                self._analysis_for_product("Mouse", 96),
                self._analysis_for_product("Laptop", 96),
            ],
        ):
            mismatch = self._analyze_with_product(item_id, "Mouse", 96)
            correct = self._analyze_with_product(item_id, "Laptop", 96)
            approved = self.client.post(
                f"/api/returns/{item_id}/approve",
                json={"notes": "Correct laptop image rechecked."},
            )

        self.assertEqual(mismatch.json()["product_validation"], "MISMATCH")
        self.assertEqual(correct.json()["product_validation"], "MATCH")
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "approved")

    def test_new_mismatched_prediction_invalidates_a_previously_analyzed_match(self):
        item_id = self._create_item()
        with self.session_factory() as session:
            session.get(ReturnItem, item_id).product_name = "HP laptop"
            session.commit()

        mismatch_prediction = {
            "condition": "Good",
            "condition_score": 76,
            "confidence": 90,
            "model_name": "test-condition",
            "source": "test",
            "class_probabilities": {},
            "product_label": "Mouse",
            "product_confidence": 96,
            "product_model_name": "yolo11n",
        }
        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            returns, "UPLOAD_DIR", Path(upload_dir)
        ), patch.object(
            returns, "analyze_return", return_value=self._analysis_for_product("Laptop", 96)
        ), patch.object(
            returns, "predict_condition", return_value=mismatch_prediction
        ):
            self._analyze_with_product(item_id, "Laptop", 96)
            prediction = self.client.post(
                "/api/returns/predict-condition",
                files={
                    "image": ("mouse.png", self._image_bytes(), "image/png"),
                    "item_id": (None, str(item_id)),
                },
            )

        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            self.assertIsNone(item.product_matches)
            self.assertIsNone(item.product_label)
            self.assertIsNone(item.image_path)
        serialized = next(
            item for item in self.client.get("/api/returns").json()
            if item["id"] == item_id
        )
        approval = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Inspector's note is present."},
        )
        self.assertEqual(prediction.status_code, 200, prediction.text)
        self.assertEqual(prediction.json()["product_validation"], "MISMATCH")
        self.assertEqual(serialized["product_validation"], "UNVERIFIED")
        self.assertEqual(approval.status_code, 400)
        self.assertEqual(approval.json()["detail"], "Unable to verify product image.")

    def test_status_filters_return_only_their_matching_items(self):
        pending_item = self._create_item(analyzed=False)
        approved_item = self._create_item()
        rejected_item = self._create_item()
        with self.session_factory() as session:
            session.get(ReturnItem, approved_item).status = "approved"
            session.get(ReturnItem, rejected_item).status = "rejected"
            session.commit()

        for status, expected_id in (
            ("pending", pending_item),
            ("approved", approved_item),
            ("rejected", rejected_item),
        ):
            response = self.client.get(f"/api/returns?status={status}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual({item["id"] for item in response.json()}, {expected_id})

    def test_product_validation_is_scoped_to_each_return_item(self):
        verified_item = self._create_item()
        other_item = self._create_item()
        with self.session_factory() as session:
            session.get(ReturnItem, verified_item).product_name = "HP laptop"
            other = session.get(ReturnItem, other_item)
            other.product_name = "HP laptop"
            other.product_matches = None
            other.product_label = None
            other.product_confidence = None
            other.image_path = None
            session.commit()

        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            returns, "UPLOAD_DIR", Path(upload_dir)
        ), patch.object(
            returns, "analyze_return", return_value=self._analysis_for_product("Laptop", 96)
        ):
            self._analyze_with_product(verified_item, "Laptop", 96)
            response = self.client.post(
                f"/api/returns/{other_item}/approve",
                json={"notes": "Inspector's note is present."},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Unable to verify product image.")
        with self.session_factory() as session:
            self.assertEqual(session.get(ReturnItem, other_item).status, "pending")

    def test_approval_recomputes_match_instead_of_trusting_saved_boolean(self):
        item_id = self._create_item()
        with self.session_factory() as session:
            session.get(ReturnItem, item_id).product_name = "HP laptop"
            session.commit()

        with tempfile.TemporaryDirectory() as upload_dir, patch.object(
            returns, "UPLOAD_DIR", Path(upload_dir)
        ), patch.object(
            returns, "analyze_return", return_value=self._analysis_for_product("Laptop", 96)
        ):
            self._analyze_with_product(item_id, "Laptop", 96)

        with self.session_factory() as session:
            item = session.get(ReturnItem, item_id)
            item.product_label = "Mouse"
            item.product_matches = True
            session.commit()

        serialized = self.client.get("/api/returns").json()
        saved_item = next(item for item in serialized if item["id"] == item_id)
        approval = self.client.post(
            f"/api/returns/{item_id}/approve",
            json={"notes": "Inspector's note is present."},
        )
        self.assertEqual(saved_item["product_validation"], "MISMATCH")
        self.assertEqual(approval.status_code, 400)
        self.assertEqual(approval.json()["detail"], "Product and image mismatch")
        with self.session_factory() as session:
            self.assertEqual(session.get(ReturnItem, item_id).status, "pending")

    def test_auto_process_skips_mismatch_and_unverified_images(self):
        mismatch_item = self._create_item()
        unverified_item = self._create_item()
        stale_match_item = self._create_item()
        with self.session_factory() as session:
            mismatch = session.get(ReturnItem, mismatch_item)
            mismatch.product_name = "HP laptop"
            mismatch.product_label = "Mouse"
            mismatch.product_matches = False
            unverified = session.get(ReturnItem, unverified_item)
            unverified.product_matches = None
            stale_match = session.get(ReturnItem, stale_match_item)
            stale_match.product_name = "HP laptop"
            stale_match.product_label = "Mouse"
            stale_match.product_confidence = 96
            stale_match.product_matches = True
            stale_match.image_path = "uploads/stale.jpg"
            stale_match.analyzed_at = datetime.utcnow()
            session.commit()

        response = self.client.post("/api/returns/auto-process", json={})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["auto_approved_count"], 0)
        with self.session_factory() as session:
            self.assertEqual(session.get(ReturnItem, mismatch_item).status, "pending")
            self.assertEqual(session.get(ReturnItem, unverified_item).status, "pending")


if __name__ == "__main__":
    unittest.main()
