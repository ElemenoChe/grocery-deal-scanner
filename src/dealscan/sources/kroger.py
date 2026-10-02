"""Kroger Public API adapter (Kroger, Ralphs, Fry's, King Soopers, Smith's, etc.).

Uses the official developer API: https://developer.kroger.com
Auth is OAuth2 client-credentials with the `product.compact` scope, so no
customer login is needed. Promo prices refresh with the weekly ad, which
starts on Wednesday for most Kroger divisions.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Optional

import requests

from ..models import Deal, ListItem
from .base import AdSource

log = logging.getLogger(__name__)

API_BASE = "https://api.kroger.com/v1"
TOKEN_URL = f"{API_BASE}/connect/oauth2/token"


class KrogerSource(AdSource):
    name = "kroger"
    cadence = "weekly (Wednesday)"

    def __init__(
        self,
        location_id: Optional[str] = None,
        zip_code: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        results_per_item: int = 10,
        session: Optional[requests.Session] = None,
    ):
        self.client_id = client_id or os.environ.get("KROGER_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("KROGER_CLIENT_SECRET")
        if not (self.client_id and self.client_secret):
            raise RuntimeError(
                "Kroger credentials missing. Set KROGER_CLIENT_ID and "
                "KROGER_CLIENT_SECRET (see README)."
            )
        self.location_id = location_id or os.environ.get("KROGER_LOCATION_ID")
        self.zip_code = zip_code
        self.results_per_item = results_per_item
        self.http = session or requests.Session()
        self._token: Optional[str] = None
        self._token_expires = 0.0

    # ---- auth -------------------------------------------------------------
    def _auth_header(self) -> dict:
        if not self._token or time.time() > self._token_expires - 60:
            basic = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            r = self.http.post(
                TOKEN_URL,
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials", "scope": "product.compact"},
                timeout=20,
            )
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._token_expires = time.time() + int(body.get("expires_in", 1800))
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    def _get(self, path: str, params: dict) -> dict:
        for attempt in range(3):
            r = self.http.get(
                f"{API_BASE}{path}", headers=self._auth_header(), params=params, timeout=20
            )
            if r.status_code == 429:  # rate limited, so back off
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return {}

    # ---- locations --------------------------------------------------------
    def resolve_location(self) -> str:
        """Use the configured store, or the nearest one to the ZIP code."""
        if self.location_id:
            return self.location_id
        if not self.zip_code:
            raise RuntimeError("Set kroger.location_id or kroger.zip_code in config.yaml")
        data = self._get(
            "/locations", {"filter.zipCode.near": self.zip_code, "filter.limit": 1}
        ).get("data", [])
        if not data:
            raise RuntimeError(f"No Kroger-family store found near {self.zip_code}")
        store = data[0]
        log.info("Using Kroger store %s (%s)", store.get("name"), store["locationId"])
        self.location_id = store["locationId"]
        return self.location_id

    # ---- products ---------------------------------------------------------
    def fetch(self, items: list[ListItem]) -> list[Deal]:
        location = self.resolve_location()
        deals: list[Deal] = []
        for item in items:
            try:
                payload = self._get(
                    "/products",
                    {
                        "filter.term": item.search_term,
                        "filter.locationId": location,
                        "filter.limit": self.results_per_item,
                    },
                )
            except requests.HTTPError as exc:
                log.warning("Kroger search failed for %r: %s", item.name, exc)
                continue
            deals.extend(self._parse_products(payload))
        return deals

    @staticmethod
    def _parse_products(payload: dict) -> list[Deal]:
        out: list[Deal] = []
        for prod in payload.get("data", []):
            for sku in prod.get("items", []):
                price = sku.get("price") or {}
                regular = price.get("regular")
                promo = price.get("promo")
                if not regular:
                    continue  # not stocked or no price at this store
                pay = promo if promo and 0 < promo < regular else regular
                out.append(
                    Deal(
                        store="Kroger",
                        name=prod.get("description", "").strip(),
                        brand=prod.get("brand"),
                        price=float(pay),
                        regular_price=float(regular),
                        size=sku.get("size"),
                        product_id=prod.get("productId"),
                        url=f"https://www.kroger.com/p/{prod.get('productId')}",
                    )
                )
        return out
