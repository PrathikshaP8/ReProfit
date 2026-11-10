from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from services import ai_analyzer
from services.condition_classifier import (
    _class_probabilities,
    _is_condition_classifier,
    _yolo_product_predict,
    validate_product_image,
)
from services.decision_engine import recommend_decision_details


class DecisionEngineTests(unittest.TestCase):
    def test_low_confidence_good_laptop_defaults_to_refurbish(self):
        probabilities = {
            "Like New": 0.20,
            "Good": 0.25,
            "Fair": 0.35,
            "Poor": 0.10,
            "Damaged": 0.10,
        }

        result = recommend_decision_details(
            60,
            probabilities,
            54,
            "Electronics",
            35000,
            10000,
            True,
        )

        self.assertEqual(result["recommended_decision"], "Refurbish")
        self.assertTrue(result["needs_manual_review"])

    def test_high_confidence_damaged_item_can_be_recycled(self):
        result = recommend_decision_details(
            25,
            {"Poor": 0.5, "Damaged": 0.3, "Fair": 0.2},
            80,
            "Apparel",
            3000,
            1000,
            True,
        )

        self.assertEqual(result["recommended_decision"], "Recycle")

    def test_high_confidence_like_new_item_is_resold(self):
        result = recommend_decision_details(
            92,
            {"Like New": 0.9, "Good": 0.1},
            95,
            "Electronics",
            15000,
            7000,
            True,
        )

        self.assertEqual(result["recommended_decision"], "Resell")

    def test_product_mismatch_uses_inspector_decision_only(self):
        with patch.object(
            ai_analyzer,
            "predict_condition",
            return_value={
                "condition": "Like New",
                "condition_score": 96,
                "confidence": 95,
                "model_name": "test-condition",
                "source": "test",
                "class_probabilities": {
                    "Like New": 1.0,
                    "Good": 0.0,
                    "Fair": 0.0,
                    "Poor": 0.0,
                    "Damaged": 0.0,
                },
                "product_label": "Mobile Phone",
                "product_confidence": 90,
                "product_model_name": "test-product",
            },
        ):
            result = ai_analyzer.analyze_return(
                product_name="HP Laptop 840 G5",
                category="Electronics",
                market_price=12000,
                purchase_cost=4000,
                condition="Good",
                condition_score=75,
                image_bytes=b"image",
            )

        self.assertIs(result["product_matches"], False)
        self.assertEqual(result["recommended_decision"], "Refurbish")

    def test_low_confidence_ai_score_is_blended_toward_inspector(self):
        with patch.object(
            ai_analyzer,
            "predict_condition",
            return_value={
                "condition": "Good",
                "condition_score": 75,
                "confidence": 54,
                "model_name": "test-condition",
                "source": "test",
                "class_probabilities": {
                    "Like New": 0.0,
                    "Good": 0.45,
                    "Fair": 0.35,
                    "Poor": 0.1,
                    "Damaged": 0.1,
                },
            },
        ):
            result = ai_analyzer.analyze_return(
                product_name="HP Laptop 840 G5",
                category="Electronics",
                market_price=35000,
                purchase_cost=12000,
                condition="Good",
                condition_score=79,
                image_bytes=b"image",
            )

        self.assertEqual(result["inspector_score"], 79)
        self.assertEqual(result["ai_score"], 75)
        self.assertEqual(result["final_score"], 76.84)
        self.assertLess(abs(result["final_score"] - result["inspector_score"]), 5)
        self.assertTrue(result["needs_manual_review"])
        self.assertIn("manual review", result["ai_description"].lower())

    def test_high_value_electronics_need_strong_damage_probability(self):
        result = recommend_decision_details(
            35,
            {"Poor": 0.4, "Damaged": 0.3, "Fair": 0.3},
            90,
            "Electronics",
            8000,
            2000,
            True,
        )

        self.assertEqual(result["recommended_decision"], "Refurbish")

    def test_condition_classifier_accepts_three_and_five_class_models(self):
        self.assertTrue(_is_condition_classifier({0: "resell", 1: "refurbish", 2: "recycle"}))
        self.assertTrue(
            _is_condition_classifier(
                {0: "Like New", 1: "Good", 2: "Fair", 3: "Poor", 4: "Damaged"}
            )
        )

    def test_three_class_probabilities_map_without_changing_decision_groups(self):
        probabilities = _class_probabilities(
            [0.8, 0.1, 0.1],
            {0: "resell", 1: "refurbish", 2: "recycle"},
        )

        self.assertAlmostEqual(probabilities["Like New"] + probabilities["Good"], 0.8)
        self.assertAlmostEqual(probabilities["Fair"], 0.1)
        self.assertAlmostEqual(probabilities["Poor"] + probabilities["Damaged"], 0.1)

    def test_low_product_confidence_is_treated_as_unknown(self):
        with patch.object(
            ai_analyzer,
            "predict_condition",
            return_value={
                "condition": "Good",
                "condition_score": 76,
                "confidence": 80,
                "model_name": "test-condition",
                "source": "test",
                "class_probabilities": {"Good": 1.0},
                "product_label": "Mobile Phone",
                "product_confidence": 24.9,
                "product_model_name": "test-product",
            },
        ):
            result = ai_analyzer.analyze_return(
                product_name="HP Laptop 840 G5",
                category="Electronics",
                market_price=12000,
                purchase_cost=4000,
                condition="Good",
                condition_score=75,
                image_bytes=b"image",
            )

        self.assertIsNone(result["product_matches"])
        self.assertEqual(result["product_validation"], "UNVERIFIED")

    def test_conflicting_inspector_note_requires_manual_review(self):
        with patch.object(
            ai_analyzer,
            "predict_condition",
            return_value={
                "condition": "Good",
                "condition_score": 76,
                "confidence": 90,
                "model_name": "test-condition",
                "source": "test",
                "class_probabilities": {"Good": 1.0},
                "product_label": "Mobile Phone",
                "product_confidence": 95,
            },
        ):
            result = ai_analyzer.analyze_return(
                product_name="Mobile phone",
                category="Electronics",
                market_price=12000,
                purchase_cost=4000,
                condition="Good",
                condition_score=76,
                image_bytes=b"image",
                notes="Cracked screen reported by inspector.",
            )

        self.assertTrue(result["notes_conflict"])
        self.assertTrue(result["needs_manual_review"])
        self.assertEqual(result["recommended_decision"], "Refurbish")
        self.assertIn("conflict", result["decision_reason"].lower())

    def test_note_analysis_handles_negations_and_positive_good_condition(self):
        self.assertEqual(ai_analyzer._analyze_inspector_note("not damaged")["status"], "positive")
        self.assertEqual(ai_analyzer._analyze_inspector_note("not bad")["status"], "positive")
        self.assertEqual(ai_analyzer._analyze_inspector_note("not working")["status"], "negative")

        with patch.object(
            ai_analyzer,
            "predict_condition",
            return_value={
                "condition": "Good",
                "condition_score": 92,
                "confidence": 96,
                "model_name": "test-condition",
                "source": "test",
                "class_probabilities": {"Good": 1.0},
                "product_label": "Mobile Phone",
                "product_confidence": 95,
            },
        ):
            result = ai_analyzer.analyze_return(
                product_name="Mobile phone",
                category="Electronics",
                market_price=12000,
                purchase_cost=4000,
                condition="Good",
                condition_score=92,
                image_bytes=b"image",
                notes="Looks good and working properly.",
            )

        self.assertEqual(result["recommended_decision"], "Resell")
        self.assertFalse(result["notes_conflict"])

    def test_product_categories_normalize_variations_and_detect_cross_category_images(self):
        self.assertEqual(
            validate_product_image("Gaming laptop", "Electronics", "notebook computer", 92),
            ("MATCH", True, "Laptop"),
        )
        self.assertEqual(
            validate_product_image("HP laptop", "Electronics", "computer mouse", 93),
            ("MISMATCH", False, "Laptop"),
        )
        self.assertEqual(
            validate_product_image("Mobile phone", "Electronics", "computer keyboard", 90),
            ("MISMATCH", False, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("Mobile phone", "Electronics", "sandal", 90),
            ("MISMATCH", False, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("Mobile phone", "Electronics", "suitcase", 90),
            ("UNVERIFIED", None, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("Nothing Phone", "Electronics", "cell phone", 90),
            ("MATCH", True, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("Nothing Phone", "Electronics", "computer mouse", 90),
            ("MISMATCH", False, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("OnePlus N6 5G", "Electronics", "sandals", 90),
            ("MISMATCH", False, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("Gaming laptop", "Electronics", "mouse", 90),
            ("MISMATCH", False, "Laptop"),
        )

    def test_unsupported_and_low_confidence_product_predictions_are_unverified(self):
        self.assertEqual(
            validate_product_image("Unknown appliance", "Electronics", "toaster", 97),
            ("UNVERIFIED", None, None),
        )
        self.assertEqual(
            validate_product_image("Nothing Phone", "Electronics", "unsupported object", 97),
            ("UNVERIFIED", None, "Mobile Phone"),
        )
        self.assertEqual(
            validate_product_image("HP laptop", "Electronics", "notebook computer", 24.9),
            ("UNVERIFIED", None, "Laptop"),
        )
        self.assertEqual(
            validate_product_image("HP laptop", "Electronics", "laptop", 100.1),
            ("UNVERIFIED", None, "Laptop"),
        )

    def test_product_prediction_requires_high_confidence_from_the_object_detector(self):
        def box(class_index, confidence):
            return SimpleNamespace(
                cls=SimpleNamespace(item=lambda: class_index),
                conf=SimpleNamespace(item=lambda: confidence),
            )

        def make_detector(boxes):
            def predict(image, verbose=False, conf=0.01):
                self.assertEqual(image.size, (32, 32))
                self.assertFalse(verbose)
                self.assertEqual(conf, 0.01)
                return [SimpleNamespace(boxes=boxes, names={63: "laptop", 64: "mouse", 67: "cell phone"})]

            return SimpleNamespace(predict=predict)

        with patch(
            "services.condition_classifier._load_product_detector",
            return_value=make_detector([box(67, 0.35), box(64, 0.75)]),
        ):
            prediction = _yolo_product_predict(Image.new("RGB", (32, 32)))

        self.assertEqual(prediction["product_label"], "Mouse")
        self.assertEqual(prediction["product_confidence"], 75.0)
        self.assertEqual(prediction["product_class_index"], 64)
        self.assertEqual(prediction["product_raw_label"], "mouse")
        self.assertEqual(prediction["product_model_name"], "yolo11n")

        with (
            patch("services.condition_classifier._load_product_detector", return_value=make_detector([])),
        ):
            self.assertIsNone(_yolo_product_predict(Image.new("RGB", (32, 32))))

    def test_low_confidence_phone_detection_remains_unverified(self):
        image = Image.new("RGB", (32, 32))
        with patch(
            "services.condition_classifier._load_product_detector",
            return_value=SimpleNamespace(
                predict=lambda image, verbose=False, conf=0.01: [
                    SimpleNamespace(
                        boxes=[SimpleNamespace(
                            cls=SimpleNamespace(item=lambda: 67),
                            conf=SimpleNamespace(item=lambda: 0.35),
                        )],
                        names={67: "cell phone"},
                    )
                ]
            ),
        ):
            prediction = _yolo_product_predict(image)
        self.assertEqual(prediction["product_label"], "Mobile Phone")
        self.assertEqual(prediction["product_confidence"], 35.0)
        validation, matches, expected = validate_product_image(
            "Nothing Phone",
            "Electronics",
            prediction["product_label"],
            prediction["product_confidence"],
            class_index=prediction["product_class_index"],
            raw_label=prediction["product_raw_label"],
        )
        self.assertEqual(validation, "UNVERIFIED")
        self.assertIsNone(matches)
        self.assertEqual(expected, "Mobile Phone")

    def test_inspector_condition_influences_blended_class_probabilities(self):
        prediction = {
            "condition": "Poor",
            "condition_score": 35,
            "confidence": 80,
            "model_name": "test-condition",
            "source": "test",
            "class_probabilities": {
                "Like New": 0.0,
                "Good": 0.0,
                "Fair": 0.3,
                "Poor": 0.7,
                "Damaged": 0.0,
            },
        }
        with patch.object(ai_analyzer, "predict_condition", return_value=prediction):
            likely_good = ai_analyzer.analyze_return(
                product_name="HP Laptop 840 G5",
                category="Apparel",
                market_price=3000,
                purchase_cost=1000,
                condition="Like New",
                condition_score=35,
                image_bytes=b"image",
            )
            likely_damaged = ai_analyzer.analyze_return(
                product_name="HP Laptop 840 G5",
                category="Apparel",
                market_price=3000,
                purchase_cost=1000,
                condition="Damaged",
                condition_score=35,
                image_bytes=b"image",
            )

        self.assertEqual(likely_good["recommended_decision"], "Refurbish")
        self.assertEqual(likely_damaged["recommended_decision"], "Recycle")


if __name__ == "__main__":
    unittest.main()
