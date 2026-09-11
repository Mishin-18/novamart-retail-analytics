import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

def read_csv(name):
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def test_expected_source_volumes():
    orders = read_csv("orders_raw.csv")
    assert len(orders) == 55250
    assert len({r["order_id"] for r in orders}) == 55000
    assert sum(1 for r in read_csv("order_items_raw.csv") if int(r["quantity"]) <= 0) == 90

def test_foreign_keys_are_valid():
    order_ids = {r["order_id"] for r in read_csv("orders_raw.csv")}
    product_ids = {r["product_id"] for r in read_csv("products.csv")}
    for row in read_csv("order_items_raw.csv"):
        assert row["order_id"] in order_ids
        assert row["product_id"] in product_ids

def test_jsonl_is_valid_and_unique():
    ids = set()
    with (DATA / "web_events.jsonl").open(encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            assert event["event_id"] not in ids
            ids.add(event["event_id"])
    assert len(ids) == 80000

