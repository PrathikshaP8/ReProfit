from __future__ import annotations

import math
import os
import re
import time
from typing import Any

import httpx


class SerpApiError(RuntimeError):
    pass


_usd_inr_rate: tuple[float, float] | None = None


async def search_shopping(query: str, limit: int = 10) -> list[dict[str, Any]]:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise SerpApiError("SERPAPI_KEY is not configured")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_shopping",
                "q": query,
                "api_key": api_key,
                "num": min(max(limit, 1), 20),
                "google_domain": "google.co.in",
                "gl": "in",
                "hl": "en",
            },
        )
    if response.is_error:
        raise SerpApiError(f"Shopping search failed ({response.status_code})")

    data = response.json()
    if data.get("error"):
        raise SerpApiError(data["error"])

    shopping_results = data.get("shopping_results") or []
    if not isinstance(shopping_results, list) or any(not isinstance(item, dict) for item in shopping_results):
        raise SerpApiError("Shopping search returned invalid listing data")
    shopping_results = shopping_results[:limit]
    parsed_prices = [
        (item, _price_number(item.get("price")), _currency_from_price(item.get("price")))
        for item in shopping_results
    ]
    usd_inr_rate = await _get_usd_inr_rate() if any(
        amount is not None and currency == "USD" for _, amount, currency in parsed_prices
    ) else None
    results = []
    for item, original_price, original_currency in parsed_prices:
        converted_price = None
        if original_price is not None and original_currency == "INR":
            converted_price = original_price
        elif original_price is not None and original_currency == "USD" and usd_inr_rate is not None:
            converted_price = original_price * usd_inr_rate
        results.append(
            {
                "item_id": item.get("product_id") or item.get("position"),
                "title": item.get("title"),
                "price": round(converted_price, 2) if converted_price is not None else None,
                "currency": "INR",
                "original_price": original_price,
                "original_currency": original_currency,
                "price_available": converted_price is not None and converted_price > 0,
                "url": item.get("link"),
                "image_url": item.get("thumbnail"),
                "condition": item.get("second_hand_condition") or "New",
                "source": item.get("source") or "Market",
            }
        )
    return results


async def _get_usd_inr_rate() -> float | None:
    global _usd_inr_rate
    if _usd_inr_rate and _usd_inr_rate[1] > time.time() - 3600:
        return _usd_inr_rate[0]

    fallback = None
    configured_fallback = os.getenv("USD_INR_RATE")
    if configured_fallback:
        try:
            candidate = float(configured_fallback)
            if math.isfinite(candidate) and candidate > 0:
                fallback = candidate
        except ValueError:
            fallback = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://open.er-api.com/v6/latest/USD")
        response.raise_for_status()
        rate = float(response.json()["rates"]["INR"])
        if not math.isfinite(rate) or rate <= 0:
            rate = fallback
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        rate = fallback
    if rate is None:
        return None
    _usd_inr_rate = (rate, time.time())
    return rate


def _currency_from_price(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    value = str(value)
    upper_value = value.upper()
    if "USD" in upper_value:
        return "USD"
    if "₹" in value or "INR" in upper_value or re.search(r"\bRS\.?\b", upper_value):
        return "INR"
    for currency, markers in {
        "EUR": ("€", "EUR"),
        "GBP": ("£", "GBP"),
        "JPY": ("JPY",),
        "CNY": ("CNY", "RMB"),
        "CAD": ("CAD",),
        "AUD": ("AUD",),
    }.items():
        if any(marker in value for marker in markers):
            return currency
    return None


def _price_number(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    value = str(value)
    cleaned = value.strip()
    cleaned = re.sub(r"(?i)\b(?:INR|USD|EUR|GBP|JPY|CNY|RMB|CAD|AUD)\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bRS\.?\s*", "", cleaned)
    cleaned = re.sub(r"[₹$€£¥]", "", cleaned).strip()
    if not re.fullmatch(r"(?:\d+|\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", cleaned):
        return None
    try:
        amount = float(cleaned.replace(",", ""))
        return amount if math.isfinite(amount) and amount > 0 else None
    except (OverflowError, ValueError):
        return None