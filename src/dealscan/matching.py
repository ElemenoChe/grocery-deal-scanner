"""Load the grocery list, figure out what you buy most, and match ads to it."""
from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .models import Deal, ListItem

_WORD = re.compile(r"[a-z0-9]+")


def _stem(w: str) -> str:
    # small plural normalizer: "eggs"->"egg", "berries"->"berry", "tomatoes"->"tomato"
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def tokens(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall((text or "").lower())}


# ---------------------------------------------------------------- list loading
def load_list(path: str | Path) -> list[ListItem]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    items = []
    for entry in raw.get("items", []):
        if isinstance(entry, str):
            entry = {"name": entry}
        items.append(
            ListItem(
                name=entry["name"],
                keywords=[k.lower() for k in entry.get("keywords", [])],
                exclude=[k.lower() for k in entry.get("exclude", [])],
                frequency=float(entry.get("frequency", 1)),
                target_price=entry.get("target_price"),
                preferred_size=entry.get("preferred_size"),
            )
        )
    return items


def apply_purchase_history(items: list[ListItem], history_csv: str | Path) -> None:
    """Replace each item's frequency with how often you *actually* buy it.

    CSV columns: date,item  (one row per purchase, date as YYYY-MM-DD).
    `item` should match a grocery-list name (case-insensitive).
    """
    path = Path(history_csv)
    if not path.exists():
        return
    counts: Counter[str] = Counter()
    dates = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("item") or "").strip().lower()
            if not name:
                continue
            counts[name] += 1
            try:
                dates.append(datetime.strptime(row["date"].strip(), "%Y-%m-%d"))
            except (KeyError, ValueError):
                pass
    if not counts:
        return
    months = 1.0
    if len(dates) >= 2:
        months = max((max(dates) - min(dates)).days / 30.44, 1.0)
    for item in items:
        n = counts.get(item.name.lower())
        if n:
            item.frequency = round(n / months, 2)


# ---------------------------------------------------------------- matching
def matches(item: ListItem, deal: Deal) -> bool:
    hay = tokens(f"{deal.brand or ''} {deal.name}")
    required = {_stem(k) for k in (item.keywords or _WORD.findall(item.name.lower()))}
    if not required <= hay:
        return False
    return not any(_stem(x) in hay for x in item.exclude)


@dataclass
class ItemResult:
    item: ListItem
    best: Optional[Deal]
    alternatives: list[Deal] = field(default_factory=list)

    @property
    def monthly_savings(self) -> float:
        return round(self.best.savings * self.item.frequency, 2) if self.best else 0.0

    @property
    def hits_target(self) -> bool:
        return bool(
            self.best and self.item.target_price is not None
            and self.best.price <= self.item.target_price
        )


def _rank_key(d: Deal):
    up = d.unit_price
    return (0, up[0]) if up else (1, d.price)


def pick_best(candidates: list[Deal]) -> list[Deal]:
    """Cheapest first, by unit price when sizes are known, then shelf price."""
    if not candidates:
        return []
    with_units = [d for d in candidates if d.unit_price]
    if with_units:
        # compare only within the most common unit (oz vs fl oz vs ct)
        unit = Counter(d.unit_price[1] for d in with_units).most_common(1)[0][0]
        same = sorted((d for d in with_units if d.unit_price[1] == unit), key=_rank_key)
        rest = sorted((d for d in candidates if d not in same), key=lambda d: d.price)
        return same + rest
    return sorted(candidates, key=lambda d: d.price)


def compare(items: list[ListItem], deals: list[Deal], keep: int = 3) -> list[ItemResult]:
    results = []
    for item in items:
        ranked = pick_best([d for d in deals if matches(item, d)])
        results.append(ItemResult(item, ranked[0] if ranked else None, ranked[1:keep]))
    # most-purchased first, then biggest savings
    results.sort(key=lambda r: (-r.item.frequency, -r.monthly_savings, r.item.name))
    return results
