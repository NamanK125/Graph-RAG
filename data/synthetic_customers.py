"""
Generate 50,000 synthetic Walmart customer profiles.

Output: data/raw/customers/customers.csv

Each customer is pegged to one of the 10 M5 stores (CA_1..CA_4, TX_1..TX_3, WI_1..WI_3)
and gets a geographically plausible lat/lon within that store's state.

clv_score and churn_risk columns are left null — filled by Phase 3 analytics models.
"""
import csv
import random
from pathlib import Path
from typing import List, Dict, Any

from faker import Faker

# ── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "raw" / "customers"
OUTPUT_FILE = OUTPUT_DIR / "customers.csv"

# ── Constants ─────────────────────────────────────────────────────────────────
N_CUSTOMERS = 50_000
SEED = 42

LOYALTY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
TIER_WEIGHTS = [0.45, 0.30, 0.18, 0.07]

CHANNELS = ["in-store", "online", "pickup", "delivery"]
CHANNEL_WEIGHTS = [0.50, 0.25, 0.15, 0.10]

# All 10 M5 stores
M5_STORES = (
    [f"CA_{i}" for i in range(1, 5)]
    + [f"TX_{i}" for i in range(1, 4)]
    + [f"WI_{i}" for i in range(1, 4)]
)

# Approximate bounding boxes: (lat_min, lat_max, lon_min, lon_max)
STATE_BOUNDS: Dict[str, tuple] = {
    "CA": (32.5, 42.0, -124.5, -114.1),
    "TX": (25.8, 36.5, -106.6, -93.5),
    "WI": (42.5, 47.1, -92.9, -86.8),
}


def _random_latlon(state: str) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = STATE_BOUNDS[state]
    return (
        round(random.uniform(lat_min, lat_max), 6),
        round(random.uniform(lon_min, lon_max), 6),
    )


def generate(n: int = N_CUSTOMERS, seed: int = SEED) -> List[Dict[str, Any]]:
    fake = Faker("en_US")
    Faker.seed(seed)
    random.seed(seed)

    records = []
    for i in range(n):
        store_id = random.choice(M5_STORES)
        state = store_id.split("_")[0]
        lat, lon = _random_latlon(state)

        records.append({
            "customer_id": f"CUST_{i + 1:06d}",
            "name": fake.name(),
            "email": fake.email(),
            "age": random.randint(18, 80),
            "city": fake.city(),
            "state": state,
            "latitude": lat,
            "longitude": lon,
            "loyalty_tier": random.choices(LOYALTY_TIERS, weights=TIER_WEIGHTS, k=1)[0],
            "preferred_channel": random.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0],
            "nearest_store_id": store_id,
            "signup_date": fake.date_between(start_date="-5y", end_date="-30d").isoformat(),
            "clv_score": "",
            "churn_risk": "",
        })

    return records


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating {N_CUSTOMERS:,} synthetic customer profiles ...")

    records = generate()

    fieldnames = list(records[0].keys())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Saved {len(records):,} customers → {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
