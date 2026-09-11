"""NovaMart batch pipeline: CSV -> PostgreSQL, JSONL -> MongoDB, KPI mart -> ClickHouse."""
from __future__ import annotations

import json
import os
from pathlib import Path

import clickhouse_connect
import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
OUTPUTS = ROOT / "outputs"
PG_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://novamart:novamart_local@localhost:5433/novamart")

CSV_TABLES = {
    "customers_raw.csv": "customers_raw",
    "products.csv": "products",
    "stores.csv": "stores",
    "orders_raw.csv": "orders_raw",
    "order_items_raw.csv": "order_items_raw",
    "returns.csv": "returns_raw",
    "marketing_spend.csv": "marketing_spend_raw",
}


def load_postgres() -> None:
    engine = create_engine(PG_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
    for filename, table in CSV_TABLES.items():
        frame = pd.read_csv(DATA / filename, low_memory=False)
        frame.columns = [c.lower() for c in frame.columns]
        frame.to_sql(table, engine, schema="staging", if_exists="replace", index=False, chunksize=5000, method="multi")
        print(f"loaded staging.{table}: {len(frame):,}")
    sql = (ROOT / "sql" / "postgres" / "warehouse.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)


def load_mongodb() -> None:
    client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27018"))
    collection = client.novamart.web_events
    collection.drop()
    batch: list[dict] = []
    with (DATA / "web_events.jsonl").open(encoding="utf-8") as source:
        for line in source:
            batch.append(json.loads(line))
            if len(batch) == 5000:
                collection.insert_many(batch)
                batch.clear()
    if batch:
        collection.insert_many(batch)
    collection.create_index("event_id", unique=True)
    collection.create_index([("event_date", 1), ("event_type", 1)])
    print(f"loaded MongoDB web_events: {collection.count_documents({}):,}")


def publish_clickhouse() -> None:
    pg = create_engine(PG_URL)
    monthly = pd.read_sql("SELECT * FROM marts.monthly_kpi ORDER BY month", pg)
    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8124")),
        username=os.getenv("CLICKHOUSE_USER", "novamart"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "novamart_local"),
    )
    client.command("CREATE DATABASE IF NOT EXISTS analytics")
    client.command("DROP TABLE IF EXISTS analytics.monthly_kpi")
    client.command("""CREATE TABLE analytics.monthly_kpi (
        month Date, country LowCardinality(String), sales_channel LowCardinality(String),
        orders UInt64, customers UInt64, revenue_eur Decimal(18,2), cost_eur Decimal(18,2),
        gross_margin_pct Float64, average_order_value_eur Float64
    ) ENGINE=MergeTree ORDER BY (month, country, sales_channel)""")
    client.insert_df("analytics.monthly_kpi", monthly)
    OUTPUTS.mkdir(exist_ok=True)
    monthly.to_csv(OUTPUTS / "tableau_monthly_kpi.csv", index=False)
    print(f"published ClickHouse analytics.monthly_kpi: {len(monthly):,}")


if __name__ == "__main__":
    load_postgres()
    load_mongodb()
    publish_clickhouse()
    print("NovaMart pipeline completed successfully")

