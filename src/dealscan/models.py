"""Core data models shared by every ad source."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional

# Units are converted to a base unit so prices compare across sizes.
_UNIT_TO_BASE = {
    "oz": ("oz", 1.0),
    "ounce": ("oz", 1.0),
    "lb": ("oz", 16.0),
    "lbs": ("oz", 16.0),
    "pound": ("oz", 16.0),
    "fl oz": ("fl oz", 1.0),
    "floz": ("fl oz", 1.0),
    "gal": ("fl oz", 128.0),
    "gallon": ("fl oz", 128.0),
    "qt": ("fl oz", 32.0),
    "pt": ("fl oz", 16.0),
    "l": ("fl oz", 33.814),
    "liter": ("fl oz", 33.814),
    "ml": ("fl oz", 0.033814),
    "ct": ("ct", 1.0),
    "count": ("ct", 1.0),
    "pk": ("ct", 1.0),
    "pack": ("ct", 1.0),
    "each": ("ct", 1.0),
    "ea": ("ct", 1.0),
}

_SIZE_RE = re.compile(
    r"(?:(?P<mult>\d+)\s*[x/]\s*)?(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>fl\.?\s?oz|[a-z]+)\b",
    re.IGNORECASE,
)


def parse_size(size: str | None) -> Optional[tuple[str, float]]:
    """Turn '1 gal', '2 x 16 oz', '24 ct' into (base_unit, quantity)."""
    if not size:
        return None
    for m in _SIZE_RE.finditer(size.lower()):
        unit = m.group("unit").replace(".", "").replace(" ", "")
        unit = "fl oz" if unit == "floz" else unit
        if unit not in _UNIT_TO_BASE:
            continue
        base, factor = _UNIT_TO_BASE[unit]
        qty = float(m.group("qty")) * factor
        if m.group("mult"):
            qty *= int(m.group("mult"))
        return base, qty
    return None


@dataclass
class Deal:
    """One advertised product at one store."""

    store: str
    name: str
    price: float                      # price you pay this cycle
    regular_price: Optional[float] = None
    size: Optional[str] = None
    brand: Optional[str] = None
    product_id: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    url: Optional[str] = None
    notes: Optional[str] = None

    @property
    def savings(self) -> float:
        if self.regular_price and self.regular_price > self.price:
            return round(self.regular_price - self.price, 2)
        return 0.0

    @property
    def on_sale(self) -> bool:
        return self.savings > 0

    @property
    def unit_price(self) -> Optional[tuple[float, str]]:
        parsed = parse_size(self.size)
        if not parsed or parsed[1] <= 0:
            return None
        unit, qty = parsed
        return round(self.price / qty, 4), unit

    def to_dict(self) -> dict:
        d = asdict(self)
        d["savings"] = self.savings
        d["on_sale"] = self.on_sale
        up = self.unit_price
        d["unit_price"] = {"value": up[0], "unit": up[1]} if up else None
        for k in ("valid_from", "valid_to"):
            if d[k]:
                d[k] = d[k].isoformat()
        return d


@dataclass
class ListItem:
    """One entry on the personal grocery list."""

    name: str
    keywords: list[str] = field(default_factory=list)   # all must appear
    exclude: list[str] = field(default_factory=list)    # none may appear
    frequency: float = 1.0                               # purchases per month
    target_price: Optional[float] = None                 # "buy if under"
    preferred_size: Optional[str] = None

    @property
    def search_term(self) -> str:
        return self.name
