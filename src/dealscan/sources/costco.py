"""Costco monthly coupon book ("Warehouse Savings") adapter.

Costco has no public API, and costco.com blocks automated scraping, so this
adapter reads the *released* coupon book from a CSV you drop into
data/costco/. Costco publishes a new book roughly every 4 weeks. You can
transcribe it from the official book at costco.com/warehouse-savings or the
mailer, which takes about 5 minutes a month.

CSV columns (header row required):
    item,brand,size,discount,sale_price,regular_price,valid_from,valid_to,notes

`discount` is the instant-savings amount ("$4 OFF"). Fill in either
`sale_price` or `regular_price` + `discount`. Dates are YYYY-MM-DD.
Only rows whose date window includes today are used.
"""
from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..models import Deal, ListItem
from .base import AdSource

log = logging.getLogger(__name__)


def _money(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    v = v.strip().replace("$", "").replace(",", "").lower().replace("off", "").strip()
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _date(v: Optional[str]) -> Optional[date]:
    v = (v or "").strip()
    return datetime.strptime(v, "%Y-%m-%d").date() if v else None


class CostcoSource(AdSource):
    name = "costco"
    cadence = "monthly coupon book (~every 4 weeks)"

    def __init__(self, folder: str | Path = "data/costco", today: Optional[date] = None):
        self.folder = Path(folder)
        self.today = today or date.today()

    def fetch(self, items: list[ListItem]) -> list[Deal]:
        deals: list[Deal] = []
        files = sorted(self.folder.glob("*.csv"))
        if not files:
            log.warning("No Costco coupon book CSVs in %s", self.folder)
        for path in files:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    deal = self._row_to_deal(row)
                    if deal and self._active(deal):
                        deals.append(deal)
        return deals

    def _active(self, d: Deal) -> bool:
        if d.valid_from and self.today < d.valid_from:
            return False
        if d.valid_to and self.today > d.valid_to:
            return False
        return True

    @staticmethod
    def _row_to_deal(row: dict) -> Optional[Deal]:
        name = (row.get("item") or "").strip()
        if not name:
            return None
        sale = _money(row.get("sale_price"))
        regular = _money(row.get("regular_price"))
        discount = _money(row.get("discount"))
        if sale is None and regular is not None and discount is not None:
            sale = round(regular - discount, 2)
        if regular is None and sale is not None and discount is not None:
            regular = round(sale + discount, 2)
        if sale is None:
            return None
        return Deal(
            store="Costco",
            name=name,
            brand=(row.get("brand") or "").strip() or None,
            size=(row.get("size") or "").strip() or None,
            price=sale,
            regular_price=regular,
            valid_from=_date(row.get("valid_from")),
            valid_to=_date(row.get("valid_to")),
            notes=(row.get("notes") or "").strip() or None,
        )
