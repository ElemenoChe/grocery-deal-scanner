from datetime import date

from dealscan.matching import apply_purchase_history, compare, matches, pick_best
from dealscan.models import Deal, ListItem, parse_size
from dealscan.sources.costco import CostcoSource
from dealscan.sources.kroger import KrogerSource


def test_parse_size():
    assert parse_size("1 gal") == ("fl oz", 128.0)
    assert parse_size("2 x 16 oz") == ("oz", 32.0)
    assert parse_size("12 ct") == ("ct", 12.0)
    assert parse_size("1 lb") == ("oz", 16.0)
    assert parse_size("") is None


def test_matching_keywords_and_excludes():
    milk = ListItem("milk", keywords=["milk"], exclude=["chocolate"])
    assert matches(milk, Deal("K", "2% Reduced Fat Milk", 2.0))
    assert not matches(milk, Deal("K", "Chocolate Milk", 2.0))
    eggs = ListItem("eggs", keywords=["egg"])
    assert matches(eggs, Deal("K", "Large White Eggs", 2.0))  # plural handled


def test_pick_best_uses_unit_price():
    small = Deal("A", "Milk", 2.00, size="0.5 gal")   # $0.031/fl oz
    big = Deal("B", "Milk", 3.00, size="1 gal")        # $0.023/fl oz
    assert pick_best([small, big])[0] is big


def test_compare_orders_by_frequency():
    items = [ListItem("coffee", frequency=1), ListItem("milk", frequency=4)]
    deals = [Deal("K", "Coffee", 8.0, 10.0), Deal("K", "Milk", 3.0, 3.5)]
    res = compare(items, deals)
    assert [r.item.name for r in res] == ["milk", "coffee"]
    assert res[0].monthly_savings == 2.0


def test_purchase_history(tmp_path):
    csv = tmp_path / "h.csv"
    csv.write_text("date,item\n2026-01-01,milk\n2026-01-15,milk\n2026-01-31,milk\n")
    items = [ListItem("milk", frequency=1)]
    apply_purchase_history(items, csv)
    assert items[0].frequency == 3.0


def test_costco_csv_and_date_window(tmp_path):
    (tmp_path / "book.csv").write_text(
        "item,brand,size,discount,sale_price,regular_price,valid_from,valid_to,notes\n"
        "Paper Towels,KS,12 ct,$4 OFF,,24.99,2026-09-24,2026-10-19,\n"
        "Old Deal,KS,1 ct,$1 OFF,,5.00,2026-01-01,2026-01-31,\n"
    )
    deals = CostcoSource(tmp_path, today=date(2026, 10, 2)).fetch([])
    assert len(deals) == 1
    assert deals[0].price == 20.99 and deals[0].savings == 4.0


def test_kroger_parse_promo():
    payload = {"data": [{
        "productId": "0001", "description": "Kroger 2% Milk", "brand": "Kroger",
        "items": [{"size": "1 gal", "price": {"regular": 3.49, "promo": 2.79}}],
    }, {
        "productId": "0002", "description": "Out of stock", "items": [{"price": {}}],
    }]}
    deals = KrogerSource._parse_products(payload)
    assert len(deals) == 1
    assert deals[0].price == 2.79 and deals[0].savings == 0.7
