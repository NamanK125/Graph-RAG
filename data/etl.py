"""
ETL: Transform Walmart raw CSVs → Neo4j knowledge graph.

Run order:
  1. python data/download_datasets.py    (get raw CSVs)
  2. python data/synthetic_customers.py  (generate customers)
  3. python data/etl.py                  (load everything into Neo4j)

Optional flags:
  --skip-transactions   Load schema + customers only (fast, for testing)
  --days N              How many trailing days of M5 data to use (default 365)
"""
import argparse
import os
import random
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# ── Neo4j ─────────────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "graphrag_password")
NEO4J_DB = os.getenv("NEO4J_DATABASE", "neo4j")

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent
M5_DIR = DATA_DIR / "raw" / "m5-forecasting-accuracy"
STORE_SALES_DIR = DATA_DIR / "raw" / "walmart-recruiting-store-sales-forecasting"
CUSTOMERS_FILE = DATA_DIR / "raw" / "customers" / "customers.csv"

BATCH_SIZE = 500  # rows per UNWIND batch

# ── Static store metadata ─────────────────────────────────────────────────────
M5_STORE_META: Dict[str, Dict[str, Any]] = {
    "CA_1": {"location": "Los Angeles, CA",   "region": "West",    "size_sqft": 185_000, "type": "Supercenter"},
    "CA_2": {"location": "San Francisco, CA", "region": "West",    "size_sqft": 150_000, "type": "Supercenter"},
    "CA_3": {"location": "San Diego, CA",     "region": "West",    "size_sqft": 160_000, "type": "Supercenter"},
    "CA_4": {"location": "Sacramento, CA",    "region": "West",    "size_sqft": 140_000, "type": "Neighborhood Market"},
    "TX_1": {"location": "Houston, TX",       "region": "South",   "size_sqft": 190_000, "type": "Supercenter"},
    "TX_2": {"location": "Dallas, TX",        "region": "South",   "size_sqft": 175_000, "type": "Supercenter"},
    "TX_3": {"location": "Austin, TX",        "region": "South",   "size_sqft": 155_000, "type": "Supercenter"},
    "WI_1": {"location": "Milwaukee, WI",     "region": "Midwest", "size_sqft": 145_000, "type": "Supercenter"},
    "WI_2": {"location": "Madison, WI",       "region": "Midwest", "size_sqft": 135_000, "type": "Supercenter"},
    "WI_3": {"location": "Green Bay, WI",     "region": "Midwest", "size_sqft": 130_000, "type": "Neighborhood Market"},
}


def _clean(row: Dict) -> Dict:
    """Replace float NaN with None for Neo4j compatibility."""
    return {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in row.items()}


class WalmartETL:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    def close(self):
        self.driver.close()

    def _batch(self, query: str, rows: List[Dict]):
        with self.driver.session(database=NEO4J_DB) as session:
            for i in range(0, len(rows), BATCH_SIZE):
                session.run(query, {"rows": rows[i: i + BATCH_SIZE]})

    # ── Loaders ───────────────────────────────────────────────────────────────

    def load_stores(self):
        print("Loading Store nodes ...")
        rows = [{"id": sid, **meta} for sid, meta in M5_STORE_META.items()]
        self._batch("""
            UNWIND $rows AS r
            MERGE (s:Store {id: r.id})
            SET s.location   = r.location,
                s.region     = r.region,
                s.size_sqft  = r.size_sqft,
                s.type       = r.type
        """, rows)
        print(f"  {len(rows)} stores.")

    def load_categories(self):
        print("Loading Category nodes ...")
        df = pd.read_csv(M5_DIR / "sales_train_validation.csv", usecols=["cat_id", "dept_id"])
        dept_rows = (
            df.drop_duplicates()
              .rename(columns={"cat_id": "parent", "dept_id": "name"})
              .to_dict("records")
        )
        # Dept-level categories
        self._batch("""
            UNWIND $rows AS r
            MERGE (c:Category {name: r.name})
            SET c.parent_category = r.parent
        """, dept_rows)
        # Top-level categories
        top_rows = [{"name": n} for n in df["cat_id"].unique()]
        self._batch("""
            UNWIND $rows AS r
            MERGE (c:Category {name: r.name})
        """, top_rows)
        print(f"  {len(dept_rows)} dept + {len(top_rows)} top-level categories.")

    def load_products(self):
        print("Loading Product nodes ...")
        usecols = ["item_id", "dept_id", "cat_id"]
        df = pd.read_csv(
            M5_DIR / "sales_train_validation.csv", usecols=usecols
        ).drop_duplicates(subset=["item_id"])

        # Median price per item across all stores / weeks
        prices = (
            pd.read_csv(M5_DIR / "sell_prices.csv")
              .groupby("item_id")["sell_price"]
              .median()
              .reset_index()
              .rename(columns={"sell_price": "price"})
        )
        df = df.merge(prices, on="item_id", how="left")
        df["price"] = df["price"].fillna(0.0)
        df["name"] = df["item_id"].str.replace("_", " ").str.title()
        df = df.rename(columns={"item_id": "id", "dept_id": "dept", "cat_id": "category"})

        rows = [_clean(r) for r in df.to_dict("records")]
        self._batch("""
            UNWIND $rows AS r
            MERGE (p:Product {id: r.id})
            SET p.name     = r.name,
                p.dept     = r.dept,
                p.category = r.category,
                p.price    = r.price
        """, rows)
        self._batch("""
            UNWIND $rows AS r
            MATCH (p:Product {id: r.id})
            MATCH (c:Category {name: r.dept})
            MERGE (p)-[:IN_CATEGORY]->(c)
        """, rows)
        print(f"  {len(rows)} products.")

    def load_holidays(self):
        print("Loading Holiday nodes ...")
        cal = pd.read_csv(M5_DIR / "calendar.csv")
        events = (
            cal[cal["event_name_1"].notna()][["date", "event_name_1", "event_type_1"]]
              .drop_duplicates()
              .rename(columns={"event_name_1": "name", "event_type_1": "type"})
        )
        rows = events.to_dict("records")
        self._batch("""
            UNWIND $rows AS r
            MERGE (h:Holiday {name: r.name})
            SET h.date = r.date, h.type = r.type
        """, rows)
        print(f"  {len(rows)} holiday events.")

    def load_customers(self):
        print("Loading Customer nodes ...")
        df = pd.read_csv(CUSTOMERS_FILE)
        # Empty string → None for optional numeric columns
        for col in ["clv_score", "churn_risk"]:
            df[col] = df[col].replace("", None)

        rows = [_clean(r) for r in df.to_dict("records")]
        self._batch("""
            UNWIND $rows AS r
            MERGE (c:Customer {id: r.customer_id})
            SET c.name               = r.name,
                c.email              = r.email,
                c.age                = r.age,
                c.city               = r.city,
                c.state              = r.state,
                c.latitude           = r.latitude,
                c.longitude          = r.longitude,
                c.loyalty_tier       = r.loyalty_tier,
                c.preferred_channel  = r.preferred_channel,
                c.signup_date        = r.signup_date,
                c.clv_score          = r.clv_score,
                c.churn_risk         = r.churn_risk
        """, rows)
        self._batch("""
            UNWIND $rows AS r
            MATCH (c:Customer {id: r.customer_id})
            MATCH (s:Store {id: r.nearest_store_id})
            MERGE (c)-[:LIVES_NEAR]->(s)
        """, rows)
        print(f"  {len(rows):,} customers.")

    def load_transactions(self, n_days: int = 365, max_rows: int = 500_000):
        """
        Build transactions from M5 daily sales data.

        Each (item_id, store_id, day) row where qty > 0 is a sale.
        We assign each sale to a random customer near that store, then group
        by (customer, store, date) to form Transaction nodes.
        """
        print(f"Loading Transactions (last {n_days} days, cap {max_rows:,} line-items) ...")

        cal = pd.read_csv(M5_DIR / "calendar.csv")
        cal_slice = cal.tail(n_days)[["d", "date", "event_name_1"]].copy()
        day_cols = cal_slice["d"].tolist()
        date_map = dict(zip(cal_slice["d"], cal_slice["date"]))
        holiday_map = dict(zip(cal_slice["d"], cal_slice["event_name_1"]))

        sales = pd.read_csv(
            M5_DIR / "sales_train_validation.csv",
            usecols=["item_id", "store_id"] + day_cols,
        )
        long = sales.melt(
            id_vars=["item_id", "store_id"],
            value_vars=day_cols,
            var_name="d",
            value_name="qty",
        )
        long = long[long["qty"] > 0].copy()
        long["date"] = long["d"].map(date_map)
        long["holiday"] = long["d"].map(holiday_map)

        # Attach median sell price
        prices = (
            pd.read_csv(M5_DIR / "sell_prices.csv")
              .groupby(["store_id", "item_id"])["sell_price"]
              .median()
              .reset_index()
        )
        long = long.merge(prices, on=["store_id", "item_id"], how="left")
        long["sell_price"] = long["sell_price"].fillna(0.0)

        if len(long) > max_rows:
            long = long.sample(max_rows, random_state=42)

        # Assign customers
        print("  Assigning line-items to customers ...")
        customers = pd.read_csv(CUSTOMERS_FILE, usecols=["customer_id", "nearest_store_id"])
        store_to_customers: Dict[str, List[str]] = (
            customers.groupby("nearest_store_id")["customer_id"].apply(list).to_dict()
        )
        random.seed(42)

        def _pick(store_id: str):
            pool = store_to_customers.get(store_id, [])
            return random.choice(pool) if pool else None

        long["customer_id"] = long["store_id"].map(_pick)
        long = long.dropna(subset=["customer_id"])

        long["txn_id"] = long["customer_id"] + "_" + long["store_id"] + "_" + long["date"]

        # ── Transaction header nodes ──────────────────────────────────────────
        txns = (
            long.groupby(["txn_id", "customer_id", "store_id", "date"])
                .apply(lambda g: (g["qty"] * g["sell_price"]).sum(), include_groups=False)
                .reset_index(name="total")
        )
        txn_rows = txns.to_dict("records")
        print(f"  Writing {len(txn_rows):,} Transaction nodes ...")
        self._batch("""
            UNWIND $rows AS r
            MERGE (t:Transaction {id: r.txn_id})
            SET t.date    = r.date,
                t.total   = r.total,
                t.channel = 'in-store'
        """, txn_rows)

        self._batch("""
            UNWIND $rows AS r
            MATCH (c:Customer  {id: r.customer_id})
            MATCH (t:Transaction {id: r.txn_id})
            MERGE (c)-[:MADE]->(t)
        """, txn_rows)

        self._batch("""
            UNWIND $rows AS r
            MATCH (t:Transaction {id: r.txn_id})
            MATCH (s:Store {id: r.store_id})
            MERGE (t)-[:AT]->(s)
        """, txn_rows)

        # ── Holiday links ─────────────────────────────────────────────────────
        h_rows = (
            long[long["holiday"].notna()][["txn_id", "holiday"]]
              .drop_duplicates()
              .to_dict("records")
        )
        if h_rows:
            self._batch("""
                UNWIND $rows AS r
                MATCH (t:Transaction {id: r.txn_id})
                MATCH (h:Holiday {name: r.holiday})
                MERGE (t)-[:DURING]->(h)
            """, h_rows)

        # ── CONTAINS edges ────────────────────────────────────────────────────
        contains_rows = long[["txn_id", "item_id", "qty", "sell_price"]].to_dict("records")
        print(f"  Writing {len(contains_rows):,} CONTAINS edges ...")
        self._batch("""
            UNWIND $rows AS r
            MATCH (t:Transaction {id: r.txn_id})
            MATCH (p:Product {id: r.item_id})
            MERGE (t)-[rel:CONTAINS]->(p)
            SET rel.qty   = r.qty,
                rel.price = r.sell_price
        """, contains_rows)

        print(f"  Done — {len(txn_rows):,} transactions, {len(contains_rows):,} line-items.")

    # ── Orchestration ──────────────────────────────────────────────────────────

    def run_all(self, skip_transactions: bool = False, n_days: int = 365):
        print("\n=== Walmart ETL ===\n")
        self.load_stores()
        self.load_categories()
        self.load_products()
        self.load_holidays()
        self.load_customers()
        if not skip_transactions:
            self.load_transactions(n_days=n_days)
        print("\n=== ETL complete ===")


def main():
    parser = argparse.ArgumentParser(description="Walmart GraphRAG ETL pipeline")
    parser.add_argument(
        "--skip-transactions", action="store_true",
        help="Load schema + customers only (fast schema test)"
    )
    parser.add_argument(
        "--days", type=int, default=365,
        help="How many trailing days of M5 data to ingest (default 365)"
    )
    args = parser.parse_args()

    etl = WalmartETL()
    try:
        etl.run_all(skip_transactions=args.skip_transactions, n_days=args.days)
    finally:
        etl.close()


if __name__ == "__main__":
    main()
