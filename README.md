# 🛒 dealscan: Grocery Ad Scanner

> She couldn't keep a sourdough starter alive, but she can run a cron job in the cloud.

`dealscan` checks grocery ads every time a store releases a new one, compares them to your grocery list, and gives you **one report**: the lowest price for each item, starting with the things you buy most.

| Store | Source | Release cadence | How it's read |
|---|---|---|---|
| Kroger family (Kroger, Ralphs, Fry's, King Soopers, Smith's…) | [Kroger Public API](https://developer.kroger.com) | Weekly, Wednesdays | OAuth2 client-credentials, `product.compact` scope |
| Costco | Monthly *Warehouse Savings* coupon book | About every 4 weeks | CSV you drop in `data/costco/` (Costco has no public API, and this project doesn't scrape) |

## How it works

```
grocery_list.yaml ─┐
purchase_history ──┼─► matching (keywords / excludes / plurals)
                   │        │
Kroger API ────────┤        ▼
Costco CSV ────────┘   rank by unit price ─► reports/latest.md  (human)
                                          └► reports/latest.json (website / API)
GitHub Actions cron (Wed 7am CT) ─► runs it ─► commits the report
```

* **Most-bought first.** Each item gets a `frequency` (purchases per month). If you add `data/purchase_history.csv`, that number is calculated from what you've actually bought.
* **Fair comparisons.** Sizes like `1 gal`, `3 x 0.5 gal`, `24 ct` and `16 oz` are converted to a unit price, so a Costco bulk pack and a Kroger single are compared on the same basis.
* **Estimated monthly savings** = (regular − sale) × how often you buy it.
* **🎯 targets.** Set `target_price` on an item to flag it when it drops to that price or lower.
* **Pluggable.** Each store is an `AdSource` subclass in `src/dealscan/sources/`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml     # set your ZIP code
dealscan --demo                        # runs offline with sample data
```

### Kroger API keys (free)
1. Create an account at <https://developer.kroger.com>, then **Register an App** with the *Product* (public) API.
2. Export the keys:
   ```bash
   export KROGER_CLIENT_ID=...
   export KROGER_CLIENT_SECRET=...
   dealscan
   ```

### Costco coupon book
Each month, copy `data/costco/EXAMPLE_coupon_book.csv` to something like `data/costco/2026-10.csv` and fill it in from the official book. Rows outside their `valid_from`/`valid_to` dates are ignored automatically, so old books can stay in the folder. **Delete the EXAMPLE file once you have real data.** The rows in it are placeholders, not real Costco prices.

## Running it in the cloud (GitHub Actions)
1. Push this repo to GitHub.
2. **Settings → Secrets and variables → Actions**: add `KROGER_CLIENT_ID` and `KROGER_CLIENT_SECRET`.
3. **Actions → Weekly grocery ad scan → Run workflow** to test it.

The workflow runs the tests, scans the ads, posts the report to the job summary, and commits `reports/latest.md`, `reports/latest.json` and a dated copy in `reports/history/`, which builds up price history for future trend analysis.

## Project layout
```
src/dealscan/
  models.py        Deal / ListItem, size → unit-price parsing
  matching.py      list loading, purchase-history frequency, matching, ranking
  report.py        Markdown + JSON output
  cli.py           entry point (`dealscan`)
  sources/         kroger.py · costco.py · sample.py · base.py
tests/             pytest suite (no network needed)
.github/workflows/ scheduled scan
```

## Roadmap
- [ ] Price-trend chart from `reports/history/` (best week to stock up)
- [ ] More stores via the `AdSource` interface
- [ ] Publish `latest.json` to the portfolio site
- [ ] Notify by email or SMS when a 🎯 target hits
