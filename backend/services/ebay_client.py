from __future__ import annotations

import base64
import os
import time
from typing import Any

import httpx


class EbayApiError(RuntimeError):
    pass


_token: dict[str, Any] = {}


def _config() -> tuple[str, str, str, str]:
    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    environment = os.getenv("EBAY_ENVIRONMENT", "production").lower()
    marketplace = os.getenv("EBAY_MARKETPLACE", "EBAY_US")
    if not client_id or not client_secret:
        raise EbayApiError("eBay API credentials are not configured")
    if environment not in {"production", "sandbox"}:
        raise EbayApiError("EBAY_ENVIRONMENT must be production or sandbox")
    return client_id, client_secret, environment, marketplace


async def _access_token() -> tuple[str, str]:
    client_id, client_secret, environment, marketplace = _config()
    if _token.get("value") and _token.get("expires_at", 0) > time.time() + 60:
        return _token["value"], marketplace

    host = "api.sandbox.ebay.com" if environment == "sandbox" else "api.ebay.com"
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://{host}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
        )
    if response.is_error:
        raise EbayApiError(f"eBay authentication failed ({response.status_code})")
    token = response.json()
    _token.update(value=token["access_token"], expires_at=time.time() + token["expires_in"])
    return _token["value"], marketplace


async def search_items(query: str, limit: int = 10) -> list[dict[str, Any]]:
    token, marketplace = await _access_token()
    environment = os.getenv("EBAY_ENVIRONMENT", "production").lower()
    host = "api.sandbox.ebay.com" if environment == "sandbox" else "api.ebay.com"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"https://{host}/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Language": "en-US",
                "X-EBAY-C-MARKETPLACE-ID": marketplace,
            },
            params={"q": query, "limit": min(max(limit, 1), 50)},
        )
    if response.is_error:
        raise EbayApiError(f"eBay search failed ({response.status_code})")

    items = []
    for item in response.json().get("itemSummaries", []):
        price = item.get("price", {})
        items.append(
            {
                "item_id": item.get("itemId"),
                "title": item.get("title"),
                "price": float(price["value"]) if price.get("value") else None,
                "currency": price.get("currency"),
                "url": item.get("itemWebUrl"),
                "image_url": (item.get("image") or {}).get("imageUrl"),
                "condition": item.get("condition"),
            }
        )
    return items