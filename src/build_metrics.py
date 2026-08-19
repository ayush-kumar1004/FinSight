"""Assemble the verified metrics that the AI summary is allowed to use.

Every number here is computed by Python/SQL from the database and the analytics
outputs. This file is the single source of truth: ai_insights.py may ONLY narrate
these values, never compute its own.

Output: outputs/metrics.json
Run:  python src/build_metrics.py
"""
from __future__ import annotations

import json
import sqlite3
import pandas as pd

from config import DB_PATH, OUTPUTS


def _read_csv(name: str) -> pd.DataFrame | None:
    p = OUTPUTS / name
    return pd.read_csv(p) if p.exists() else None


def build() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        txn = pd.read_sql("SELECT * FROM transactions", conn)
        inter = pd.read_sql("SELECT * FROM campaign_interactions", conn)
        merch = pd.read_sql("SELECT merchant_id, category FROM merchants", conn)
    finally:
        conn.close()

    # ---- headline totals ----
    total_revenue = float(txn["transaction_amount"].sum())
    total_transactions = int(len(txn))
    active_customers = int(txn["customer_id"].nunique())
    avg_txn_value = float(txn["transaction_amount"].mean())

    # ---- overall redemption rate ----
    engaged = int(inter["engaged"].sum())
    redeemed = int(inter["redeemed"].sum())
    redemption_rate = round(redeemed / engaged, 4) if engaged else None

    # ---- monthly revenue + latest MoM growth ----
    t = txn.copy()
    t["month"] = pd.to_datetime(t["transaction_date"]).dt.strftime("%Y-%m")
    monthly = t.groupby("month")["transaction_amount"].sum().sort_index()
    if len(monthly) >= 2 and monthly.iloc[-2] > 0:
        mom_growth = round(100 * (monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2], 2)
    else:
        mom_growth = None

    # ---- top category by revenue ----
    cat_rev = (txn.merge(merch, on="merchant_id")
                  .groupby("category")["transaction_amount"].sum().sort_values(ascending=False))
    top_category = str(cat_rev.index[0])
    top_category_revenue = round(float(cat_rev.iloc[0]), 2)

    # ---- best / worst campaign from campaign_performance.csv ----
    perf = _read_csv("campaign_performance.csv")
    top_campaign = lowest_campaign = None
    if perf is not None and not perf.empty:
        top = perf.sort_values("campaign_revenue", ascending=False).iloc[0]
        top_campaign = {
            "campaign_id": str(top["campaign_id"]),
            "campaign_name": str(top["campaign_name"]),
            "revenue": round(float(top["campaign_revenue"]), 2),
            "redemption_rate": None if pd.isna(top["redemption_rate"]) else float(top["redemption_rate"]),
        }
        # lowest redemption among campaigns with a meaningful engaged base
        eligible = perf[perf["engaged"] >= 30].copy()
        if not eligible.empty:
            low = eligible.sort_values("redemption_rate").iloc[0]
            lowest_campaign = {
                "campaign_id": str(low["campaign_id"]),
                "campaign_name": str(low["campaign_name"]),
                "redemption_rate": None if pd.isna(low["redemption_rate"]) else float(low["redemption_rate"]),
            }

    # ---- top RFM segment by revenue ----
    rfm = _read_csv("rfm_segments.csv")
    top_segment = None
    if rfm is not None and not rfm.empty:
        seg_rev = (txn.merge(rfm[["customer_id", "rfm_segment"]], on="customer_id")
                      .groupby("rfm_segment")["transaction_amount"].sum().sort_values(ascending=False))
        top_segment = {"segment": str(seg_rev.index[0]), "revenue": round(float(seg_rev.iloc[0]), 2)}

    # ---- repeat customer rate ----
    per_cust = txn.groupby("customer_id").size()
    repeat_rate = round(100 * (per_cust > 1).mean(), 1)

    # ---- anomalies flagged ----
    anomalies = _read_csv("anomalies.csv")
    n_anomalies = int(len(anomalies)) if anomalies is not None else 0

    return {
        "as_of": t["month"].max() if len(monthly) else None,
        "currency": "INR",
        "note": "All figures are computed by Python/SQL from synthetic data. "
                "The AI summary may only narrate these values.",
        "total_revenue": round(total_revenue, 2),
        "total_transactions": total_transactions,
        "active_customers": active_customers,
        "avg_transaction_value": round(avg_txn_value, 2),
        "campaign_redemption_rate": redemption_rate,
        "latest_month_revenue_growth_pct": mom_growth,
        "top_category": top_category,
        "top_category_revenue": top_category_revenue,
        "top_campaign": top_campaign,
        "lowest_redemption_campaign": lowest_campaign,
        "top_customer_segment": top_segment,
        "repeat_customer_rate_pct": repeat_rate,
        "anomalies_flagged": n_anomalies,
    }


def main() -> None:
    metrics = build()
    OUTPUTS.mkdir(exist_ok=True)
    with open(OUTPUTS / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print("Verified metrics written to outputs/metrics.json\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
