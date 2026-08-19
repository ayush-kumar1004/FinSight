"""Export clean, Power BI-ready CSVs into outputs/powerbi/.

Power BI works best with a small star schema plus a few pre-aggregated helper
tables. We export:

  fact_transactions.csv   -- one row per transaction, enriched with category,
                             customer attributes, rfm_segment, month (the main
                             table to build most visuals on)
  dim_customers.csv       -- customers + their rfm_segment
  dim_campaigns.csv       -- campaigns
  kpi_summary.csv         -- single-row headline KPIs for card visuals (Page 1)
  monthly_revenue.csv     -- Page 1 line chart
  category_revenue.csv    -- Page 1 / Page 2
  rfm_summary.csv         -- Page 2 segment table
  campaign_performance.csv-- Page 3 (copied from analytics output)
  merchant_performance.csv-- Page 3 (copied)
  anomalies.csv           -- Page 3 alerts (copied)
  recommendations.csv     -- Page 3 / opportunities (copied)

Run:  python src/export_powerbi.py
"""
from __future__ import annotations

import shutil
import sqlite3
import pandas as pd

from config import DB_PATH, OUTPUTS, OUTPUTS_PBI


def _load(conn):
    txn = pd.read_sql("SELECT * FROM transactions", conn)
    cust = pd.read_sql("SELECT * FROM customers", conn)
    merch = pd.read_sql("SELECT * FROM merchants", conn)
    camp = pd.read_sql("SELECT * FROM campaigns", conn)
    inter = pd.read_sql("SELECT * FROM campaign_interactions", conn)
    rfm = pd.read_sql("SELECT customer_id, rfm_segment, recency_days, frequency, monetary "
                      "FROM rfm_segments", conn)
    return txn, cust, merch, camp, inter, rfm


def build_fact(txn, cust, merch, rfm) -> pd.DataFrame:
    fact = (txn
            .merge(merch[["merchant_id", "category", "merchant_name", "merchant_size"]],
                   on="merchant_id", how="left")
            .merge(cust[["customer_id", "income_band", "city", "account_type"]],
                   on="customer_id", how="left", suffixes=("", "_cust"))
            .merge(rfm[["customer_id", "rfm_segment"]], on="customer_id", how="left"))
    fact["rfm_segment"] = fact["rfm_segment"].fillna("Unsegmented")
    fact["month"] = pd.to_datetime(fact["transaction_date"]).dt.strftime("%Y-%m")
    fact["is_campaign_transaction"] = fact["campaign_id"].notna().astype(int)
    keep = ["transaction_id", "customer_id", "merchant_id", "campaign_id",
            "transaction_date", "month", "transaction_amount", "discount_amount",
            "is_campaign_transaction", "payment_channel",
            "category", "merchant_name", "merchant_size",
            "income_band", "city", "account_type", "rfm_segment"]
    return fact[keep]


def build_kpis(txn, inter, rfm) -> pd.DataFrame:
    engaged = int(inter["engaged"].sum())
    redeemed = int(inter["redeemed"].sum())
    per_cust = txn.groupby("customer_id").size()
    return pd.DataFrame([{
        "total_revenue": round(float(txn["transaction_amount"].sum()), 2),
        "total_transactions": int(len(txn)),
        "active_customers": int(txn["customer_id"].nunique()),
        "avg_transaction_value": round(float(txn["transaction_amount"].mean()), 2),
        "campaign_redemption_rate": round(redeemed / engaged, 4) if engaged else None,
        "repeat_customer_rate_pct": round(100 * (per_cust > 1).mean(), 1),
        "total_campaigns": int(inter["campaign_id"].nunique()),
    }])


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        txn, cust, merch, camp, inter, rfm = _load(conn)
    finally:
        conn.close()

    OUTPUTS_PBI.mkdir(parents=True, exist_ok=True)

    fact = build_fact(txn, cust, merch, rfm)
    fact.to_csv(OUTPUTS_PBI / "fact_transactions.csv", index=False)

    cust.merge(rfm, on="customer_id", how="left").to_csv(
        OUTPUTS_PBI / "dim_customers.csv", index=False)
    camp.to_csv(OUTPUTS_PBI / "dim_campaigns.csv", index=False)

    build_kpis(txn, inter, rfm).to_csv(OUTPUTS_PBI / "kpi_summary.csv", index=False)

    monthly = fact.groupby("month").agg(
        revenue=("transaction_amount", "sum"),
        transactions=("transaction_id", "count"),
    ).round(2).reset_index()
    monthly.to_csv(OUTPUTS_PBI / "monthly_revenue.csv", index=False)

    cat = fact.groupby("category").agg(
        revenue=("transaction_amount", "sum"),
        transactions=("transaction_id", "count"),
    ).round(2).reset_index().sort_values("revenue", ascending=False)
    cat.to_csv(OUTPUTS_PBI / "category_revenue.csv", index=False)

    if not rfm.empty:
        seg = (fact.groupby("rfm_segment").agg(
                    customers=("customer_id", "nunique"),
                    revenue=("transaction_amount", "sum"),
                    transactions=("transaction_id", "count"))
                   .round(2).reset_index())
        seg["avg_customer_value"] = (seg["revenue"] / seg["customers"]).round(2)
        seg.to_csv(OUTPUTS_PBI / "rfm_summary.csv", index=False)

    # copy the analytics outputs Power BI's Page 3 uses
    for name in ["campaign_performance.csv", "merchant_performance.csv",
                 "anomalies.csv", "recommendations.csv"]:
        src = OUTPUTS / name
        if src.exists():
            shutil.copy(src, OUTPUTS_PBI / name)

    print("Power BI-ready CSVs written to outputs/powerbi/:")
    for p in sorted(OUTPUTS_PBI.glob("*.csv")):
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
