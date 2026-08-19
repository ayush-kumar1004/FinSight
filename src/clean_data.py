"""Clean the raw data into analysis-ready processed datasets.

Cleaning rules (documented in docs/ground_truth/defect_spec.md):
  - duplicate transaction rows  -> drop, keep first
  - orphan foreign keys         -> drop transactions with unknown merchant/campaign
  - invalid merchant categories -> normalise obvious typos/case, else "Unknown"
  - negative transaction amounts-> drop (a sale cannot be negative here)
  - invalid/unparseable dates   -> drop those transactions
  - missing income_band         -> fill "Unknown"
  - missing transaction city    -> back-fill from the customer's home city
  - extreme values              -> KEPT (flagged only, never auto-deleted)

Writes cleaned CSVs to data/processed/.
Run:  python src/clean_data.py
"""
from __future__ import annotations

import pandas as pd

from config import load_config, ensure_dirs, DATA_RAW, DATA_PROCESSED

# obvious typo/case fixes for merchant categories
_CATEGORY_FIX = {
    "diningg": "Dining", "travel": "Travel", "fuel": "Fuel",
    "shoping": "Shopping", "electronic": "Electronics",
}


def _normalise_category(value: str, allowed: set[str]) -> str:
    if pd.isna(value):
        return "Unknown"
    v = str(value).strip()
    if v in allowed:
        return v
    key = v.lower().strip()
    if key in _CATEGORY_FIX:
        return _CATEGORY_FIX[key]
    # title-case last-chance match (e.g. "TRAVEL" -> "Travel")
    if v.title() in allowed:
        return v.title()
    return "Unknown"


def clean(raw: dict[str, pd.DataFrame], cfg: dict) -> dict[str, pd.DataFrame]:
    allowed = set(cfg["categories"])
    start = pd.Timestamp(cfg["dates"]["start"])
    end = pd.Timestamp(cfg["dates"]["end"])

    customers = raw["customers"].copy()
    merchants = raw["merchants"].copy()
    campaigns = raw["campaigns"].copy()
    txn = raw["transactions"].copy()
    inter = raw["campaign_interactions"].copy()

    stats = {}

    # --- customers: fill missing income_band ---
    stats["income_filled"] = int(customers["income_band"].isna().sum())
    customers["income_band"] = customers["income_band"].fillna("Unknown")
    customers = customers.drop_duplicates(subset="customer_id", keep="first")

    # --- merchants: normalise categories ---
    stats["categories_normalised"] = int((~merchants["category"].isin(allowed)).sum())
    merchants["category"] = merchants["category"].apply(lambda v: _normalise_category(v, allowed))

    # --- transactions cleaning ---
    n0 = len(txn)
    txn = txn.drop_duplicates(subset="transaction_id", keep="first")
    stats["dup_txn_dropped"] = n0 - len(txn)

    # invalid dates -> drop
    parsed = pd.to_datetime(txn["transaction_date"], errors="coerce")
    in_window = parsed.notna() & (parsed >= start) & (parsed <= end)
    stats["bad_date_dropped"] = int((~in_window).sum())
    txn = txn.loc[in_window].copy()
    txn["transaction_date"] = pd.to_datetime(txn["transaction_date"]).dt.strftime("%Y-%m-%d")

    # negative amounts -> drop
    stats["negative_dropped"] = int((txn["transaction_amount"] < 0).sum())
    txn = txn.loc[txn["transaction_amount"] >= 0].copy()

    # orphan FKs -> drop
    valid_m = set(merchants["merchant_id"])
    valid_c = set(campaigns["campaign_id"])
    orphan = ~txn["merchant_id"].isin(valid_m) | (
        txn["campaign_id"].notna() & ~txn["campaign_id"].isin(valid_c))
    stats["orphan_dropped"] = int(orphan.sum())
    txn = txn.loc[~orphan].copy()

    # back-fill missing txn city from the customer's home city
    home_city = customers.set_index("customer_id")["city"]
    missing_city = txn["city"].isna()
    stats["city_backfilled"] = int(missing_city.sum())
    txn.loc[missing_city, "city"] = txn.loc[missing_city, "customer_id"].map(home_city)
    txn["city"] = txn["city"].fillna("Unknown")

    # normalise campaign flag consistency
    txn["is_campaign_transaction"] = txn["campaign_id"].notna().astype(int)
    txn.loc[txn["campaign_id"].isna(), "discount_amount"] = 0.0

    # --- interactions: keep only known customers/campaigns, enforce funnel monotonicity ---
    inter = inter.drop_duplicates(subset="interaction_id", keep="first")
    inter = inter[inter["customer_id"].isin(set(customers["customer_id"]))]
    inter = inter[inter["campaign_id"].isin(valid_c)]
    for lo, hi in [("engaged", "click"), ("redeemed", "engaged"), ("click", "impression")]:
        inter[lo] = (inter[lo] & inter[hi]).astype(int) if inter[lo].dtype == bool \
            else (inter[lo].astype(int) & inter[hi].astype(int))

    return ({
        "customers": customers, "merchants": merchants, "campaigns": campaigns,
        "transactions": txn, "campaign_interactions": inter,
    }, stats)


def main() -> None:
    ensure_dirs()
    cfg = load_config()
    raw = {n: pd.read_csv(DATA_RAW / f"{n}.csv")
           for n in ["customers", "merchants", "campaigns", "transactions", "campaign_interactions"]}
    cleaned, stats = clean(raw, cfg)

    for name, df in cleaned.items():
        df.to_csv(DATA_PROCESSED / f"{name}.csv", index=False)

    print("Cleaning summary:")
    for k, v in stats.items():
        print(f"  {k:22s} {v:>6,}")
    print("\nProcessed row counts:")
    for name, df in cleaned.items():
        print(f"  {name:24s} {len(df):>7,}")


if __name__ == "__main__":
    main()
