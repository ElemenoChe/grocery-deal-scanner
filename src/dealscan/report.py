"""Render results to Markdown (readable on GitHub) and JSON (for a website)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .matching import ItemResult


def _money(v) -> str:
    return f"${v:,.2f}" if v is not None else "n/a"


def _unit(d) -> str:
    up = d.unit_price
    if not up:
        return "n/a"
    value = f"${up[0]:.3f}" if up[0] < 0.10 else _money(up[0])
    return f"{value}/{up[1]}"


def to_markdown(results: list[ItemResult], generated: datetime, stores: list[str]) -> str:
    found = [r for r in results if r.best]
    missing = [r.item.name for r in results if not r.best]
    total = sum(r.monthly_savings for r in found)

    lines = [
        "# Grocery Deal Report",
        "",
        f"Generated {generated:%Y-%m-%d %H:%M} · Stores: {', '.join(stores)}",
        "",
        f"**{len(found)}/{len(results)} list items found · "
        f"est. savings {_money(total)}/month at your usual buying rate**",
        "",
        "## Best price for each list item (most-bought first)",
        "",
        "| Item | Buys/mo | Best store | Product | Size | Price | Reg. | Unit price | Saves/mo |",
        "|---|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for r in found:
        d = r.best
        flag = " 🎯" if r.hits_target else ""
        lines.append(
            f"| **{r.item.name}**{flag} | {r.item.frequency:g} | {d.store} | {d.name} | "
            f"{d.size or ''} | {_money(d.price)} | {_money(d.regular_price)} | "
            f"{_unit(d)} | {_money(r.monthly_savings)} |"
        )

    by_store: dict[str, list[ItemResult]] = {}
    for r in found:
        by_store.setdefault(r.best.store, []).append(r)
    lines += ["", "## Shopping trip by store", ""]
    for store, rs in sorted(by_store.items()):
        subtotal = sum(r.best.price for r in rs)
        lines.append(f"**{store}** ({len(rs)} items, {_money(subtotal)})")
        lines += [f"- [ ] {r.item.name}: {r.best.name} @ {_money(r.best.price)}" for r in rs]
        lines.append("")

    if missing:
        lines += ["## Not found in this cycle's ads", "", ", ".join(missing), ""]
    lines += ["", "🎯 means at or below your target price."]
    return "\n".join(lines) + "\n"


def to_json(results: list[ItemResult], generated: datetime, stores: list[str]) -> str:
    return json.dumps(
        {
            "generated": generated.isoformat(timespec="seconds"),
            "stores": stores,
            "estimated_monthly_savings": round(sum(r.monthly_savings for r in results), 2),
            "items": [
                {
                    "item": r.item.name,
                    "frequency_per_month": r.item.frequency,
                    "target_price": r.item.target_price,
                    "hits_target": r.hits_target,
                    "monthly_savings": r.monthly_savings,
                    "best": r.best.to_dict() if r.best else None,
                    "alternatives": [a.to_dict() for a in r.alternatives],
                }
                for r in results
            ],
        },
        indent=2,
    )


def write_reports(results, stores, out_dir: str | Path = "reports") -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    md, js = out / "latest.md", out / "latest.json"
    md.write_text(to_markdown(results, now, stores), encoding="utf-8")
    js.write_text(to_json(results, now, stores), encoding="utf-8")
    (out / "history").mkdir(exist_ok=True)
    (out / "history" / f"{now:%Y-%m-%d}.json").write_text(js.read_text(), encoding="utf-8")
    return md, js
