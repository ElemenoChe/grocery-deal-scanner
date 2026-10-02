"""Offline demo source so the project runs without API keys (`--demo`)."""
from __future__ import annotations

from ..models import Deal, ListItem
from .base import AdSource

_SAMPLE = [
    ("Kroger 2% Reduced Fat Milk", "Kroger", 2.79, 3.49, "1 gal"),
    ("Simple Truth Organic Whole Milk", "Simple Truth", 4.99, 5.49, "0.5 gal"),
    ("Large Grade A White Eggs", "Kroger", 2.49, 2.99, "12 ct"),
    ("Boneless Skinless Chicken Breast", None, 2.49, 3.99, "1 lb"),
    ("Banana", None, 0.59, 0.59, "1 lb"),
    ("Nature's Own Honey Wheat Bread", "Nature's Own", 2.50, 3.79, "20 oz"),
    ("Jif Creamy Peanut Butter", "Jif", 2.99, 3.99, "16 oz"),
    ("Barilla Spaghetti Pasta", "Barilla", 1.25, 1.99, "16 oz"),
    ("Chobani Greek Yogurt Vanilla", "Chobani", 4.49, 5.99, "32 oz"),
]


class SampleSource(AdSource):
    name = "sample"
    cadence = "n/a"

    def fetch(self, items: list[ListItem]) -> list[Deal]:
        return [
            Deal(store="Kroger (demo)", name=n, brand=b, price=p, regular_price=r, size=s)
            for n, b, p, r, s in _SAMPLE
        ]
