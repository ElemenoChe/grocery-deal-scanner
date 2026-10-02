"""Command line entry point: `python -m dealscan` or `dealscan`."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .matching import apply_purchase_history, compare, load_list
from .report import write_reports
from .sources import CostcoSource, KrogerSource, SampleSource

log = logging.getLogger("dealscan")


def build_sources(cfg: dict, demo: bool):
    if demo:
        return [SampleSource(), CostcoSource(cfg.get("costco", {}).get("folder", "data/costco"))]
    sources = []
    kcfg = cfg.get("kroger", {})
    if kcfg.get("enabled", True):
        try:
            sources.append(
                KrogerSource(
                    location_id=kcfg.get("location_id"),
                    zip_code=kcfg.get("zip_code"),
                    results_per_item=kcfg.get("results_per_item", 10),
                )
            )
        except RuntimeError as exc:
            log.warning("Skipping Kroger: %s", exc)
    ccfg = cfg.get("costco", {})
    if ccfg.get("enabled", True):
        sources.append(CostcoSource(ccfg.get("folder", "data/costco")))
    return sources


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scan grocery ads against your list.")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-l", "--list", default=None, help="grocery list YAML")
    p.add_argument("-o", "--out", default="reports")
    p.add_argument("--demo", action="store_true", help="use bundled sample Kroger data")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    cfg = cfg or {}

    items = load_list(args.list or cfg.get("grocery_list", "grocery_list.yaml"))
    apply_purchase_history(items, cfg.get("purchase_history", "data/purchase_history.csv"))

    sources = build_sources(cfg, args.demo)
    if not sources:
        log.error("No ad sources configured.")
        return 1

    deals = []
    for src in sources:
        got = src.fetch(items)
        log.info("%s: %d products (%s)", src.name, len(got), src.cadence)
        deals.extend(got)

    results = compare(items, deals)
    md, js = write_reports(results, [s.name for s in sources], args.out)
    print(md.read_text())
    log.info("Wrote %s and %s", md, js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
