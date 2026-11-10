from __future__ import annotations

import asyncio
import math
import os
import unittest
from unittest.mock import AsyncMock, patch

from services.profit_calculator import (
    DEFAULT_PROFIT_ASSUMPTIONS,
    ProfitAssumptions,
    calculate_profit_breakdown,
    calculate_profit_estimates,
)
from services.serpapi_client import _currency_from_price, _price_number, search_shopping


class ProfitCalculatorTests(unittest.TestCase):
    def test_hp_victus_recycle_estimate_matches_formula_and_keeps_real_loss(self):
        result = calculate_profit_breakdown("Recycle", 83495, 80000)

        self.assertEqual(result["recovery_value"], 6679.6)
        self.assertEqual(result["repair_cost"], 0)
        self.assertEqual(result["other_costs"], 0)
        self.assertEqual(result["estimated_profit"], -73320.4)

    def test_hp_victus_all_decisions_use_the_existing_planning_rates(self):
        estimates = calculate_profit_estimates(83495, 80000)

        self.assertEqual(estimates["Resell"], -9029.25)
        self.assertEqual(estimates["Refurbish"], -35747.65)
        self.assertEqual(estimates["Recycle"], -73320.4)
        refurbish = calculate_profit_breakdown("Refurbish", 83495, 80000)
        self.assertEqual(refurbish["recovery_value"], 54271.75)
        self.assertEqual(refurbish["repair_cost"], 10019.4)

    def test_configured_recovery_rates_and_other_costs_are_used(self):
        assumptions = ProfitAssumptions(
            resell_recovery_rate=0.9,
            refurbish_recovery_rate=0.7,
            refurbish_cost_rate=0.1,
            recycle_recovery_rate=0.05,
            other_costs_per_item=25,
        )

        resell = calculate_profit_breakdown("Resell", 1000, 600, assumptions)
        refurbish = calculate_profit_breakdown("Refurbish", 1000, 600, assumptions)
        recycle = calculate_profit_breakdown("Recycle", 1000, 600, assumptions)
        self.assertEqual(resell["estimated_profit"], 275)
        self.assertEqual(refurbish["estimated_profit"], -25)
        self.assertEqual(refurbish["repair_cost"], 100)
        self.assertEqual(recycle["estimated_profit"], -575)

    def test_missing_or_invalid_inputs_do_not_become_fake_zero_estimates(self):
        for market_price, purchase_cost in (
            (None, 100),
            (0, 100),
            (100, None),
            (100, math.nan),
            (math.inf, 100),
            (100, -1),
        ):
            with self.subTest(market_price=market_price, purchase_cost=purchase_cost):
                with self.assertRaises(ValueError):
                    calculate_profit_breakdown("Resell", market_price, purchase_cost)

    def test_large_prices_remain_finite_and_negative_profit_is_preserved(self):
        estimates = calculate_profit_estimates(1_000_000_000_000, 999_999_999_999)

        self.assertEqual(estimates["Resell"], -149999999999)
        self.assertTrue(all(math.isfinite(value) for value in estimates.values()))
        self.assertEqual(DEFAULT_PROFIT_ASSUMPTIONS.other_costs_per_item, 0)

    def test_serp_price_parsing_requires_unambiguous_amount_and_currency(self):
        self.assertEqual(_price_number("₹ 83,495.00"), 83495)
        self.assertEqual(_price_number("Rs. 1,23,499"), 123499)
        self.assertEqual(_currency_from_price("₹ 83,495"), "INR")
        self.assertEqual(_price_number("USD $1,000.50"), 1000.5)
        self.assertEqual(_currency_from_price("USD $1,000.50"), "USD")

        self.assertIsNone(_currency_from_price("83,495"))
        self.assertIsNone(_currency_from_price("$1,000.50"))
        self.assertIsNone(_price_number("₹83,495 - ₹87,999"))
        self.assertIsNone(_price_number("₹1.2 lakh"))
        self.assertIsNone(_price_number("₹0"))
        self.assertIsNone(_price_number("not a price"))
        self.assertIsNone(_price_number(f"₹{'9' * 400}"))

    def test_serp_search_only_returns_market_price_when_currency_is_known(self):
        class Response:
            is_error = False

            def json(self):
                return {
                    "shopping_results": [
                        {"product_id": "inr", "title": "HP Victus model", "price": "₹83,495", "link": "https://example.test/inr"},
                        {"product_id": "unknown", "title": "Unmarked price", "price": "83,495"},
                        {"product_id": "usd", "title": "Imported listing", "price": "USD $999"},
                        {"product_id": "eur", "title": "Unsupported currency", "price": "€999"},
                    ]
                }

        class Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return Response()

        with patch.dict(os.environ, {"SERPAPI_KEY": "test-key"}):
            with patch("services.serpapi_client.httpx.AsyncClient", Client):
                with patch(
                    "services.serpapi_client._get_usd_inr_rate",
                    new=AsyncMock(return_value=85),
                ):
                    results = asyncio.run(search_shopping("HP Victus"))

        by_id = {item["item_id"]: item for item in results}
        self.assertEqual(by_id["inr"]["price"], 83495)
        self.assertTrue(by_id["inr"]["price_available"])
        self.assertIsNone(by_id["unknown"]["price"])
        self.assertFalse(by_id["unknown"]["price_available"])
        self.assertEqual(by_id["usd"]["price"], 84915)
        self.assertEqual(by_id["eur"]["price"], None)


if __name__ == "__main__":
    unittest.main()
