"""Campaign analytics — funnel + revenue + ROI, with safe division.

Metric definitions (also in docs/metrics_definitions.md):
  CTR             = clicks / impressions
  Conversion rate = redeemed / clicks
  Redemption rate = redeemed / engaged
  Campaign revenue= SUM(transaction_amount) on that campaign's transactions
  Discount cost   = SUM(discount_amount) on that campaign's transactions
  Margin revenue  = margin_rate * campaign revenue         (params.yaml: margin_rate)
  ROI             = (margin revenue - discount cost) / discount cost

ROI is deliberately measured at the offer level (margin earned vs discount paid),
which surfaces a real insight: deep-discount campaigns can be revenue-positive but
margin-negative. campaign_budget is reported alongside but not used in ROI.

Merchant performance is included here (grouped from the same joined data) rather
than as a separate system.

Run:  python src/campaign_analytics.py
"""
from __future__ import annotations

import sqlite3
import numpy as np
import pandas as pd

from config import load_config, DB_PATH, OUTPUTS


def safe_div(num, den):
    """Element-wise divide returning NaN where the denominator is 0."""
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    out = np.full(num.shape, np.nan)
    np.divide(num, den, out=out, where=den != 0)
    return out


def _load(conn) -> dict:
    q = {
        "campaigns": "SELECT * FROM campaigns",
        "interactions": "SELECT * FROM campaign_interactions",
        "txn": "SELECT * FROM transactions WHERE campaign_id IS NOT NULL",
        "merchants": "SELECT merchant_id, merchant_name, category, merchant_size FROM merchants",
        "rfm": "SELECT customer_id, rfm_segment FROM rfm_segments",
        "all_txn": "SELECT * FROM transactions",
    }
    return {k: pd.read_sql(v, conn) for k, v in q.items()}


def campaign_summary(data: dict, margin_rate: float) -> pd.DataFrame:
    camp = data["campaigns"]
    inter = data["interactions"]
    txn = data["txn"]

    funnel = inter.groupby("campaign_id").agg(
        impressions=("impression", "sum"),
        clicks=("click", "sum"),
        engaged=("engaged", "sum"),
        redeemed=("redeemed", "sum"),
    ).reset_index()

    rev = txn.groupby("campaign_id").agg(
        campaign_transactions=("transaction_id", "count"),
        campaign_revenue=("transaction_amount", "sum"),
        discount_cost=("discount_amount", "sum"),
    ).reset_index()

    df = camp.merge(funnel, on="campaign_id", how="left").merge(rev, on="campaign_id", how="left")
    for col in ["impressions", "clicks", "engaged", "redeemed",
                "campaign_transactions", "campaign_revenue", "discount_cost"]:
        df[col] = df[col].fillna(0)

    df["ctr"] = safe_div(df["clicks"], df["impressions"]).round(4)
    df["conversion_rate"] = safe_div(df["redeemed"], df["clicks"]).round(4)
    df["redemption_rate"] = safe_div(df["redeemed"], df["engaged"]).round(4)
    df["margin_revenue"] = (df["campaign_revenue"] * margin_rate).round(2)
    df["roi"] = safe_div(df["margin_revenue"] - df["discount_cost"], df["discount_cost"]).round(4)
    df["campaign_revenue"] = df["campaign_revenue"].round(2)
    df["discount_cost"] = df["discount_cost"].round(2)

    cols = ["campaign_id", "campaign_name", "campaign_category", "merchant_id",
            "channel", "discount_type", "discount_value", "campaign_budget",
            "impressions", "clicks", "engaged", "redeemed",
            "campaign_transactions", "campaign_revenue", "discount_cost",
            "margin_revenue", "ctr", "conversion_rate", "redemption_rate", "roi"]
    return df[cols].sort_values("campaign_revenue", ascending=False).reset_index(drop=True)


def by_category(summary: pd.DataFrame) -> pd.DataFrame:
    g = summary.groupby("campaign_category").agg(
        campaigns=("campaign_id", "count"),
        revenue=("campaign_revenue", "sum"),
        redeemed=("redeemed", "sum"),
        engaged=("engaged", "sum"),
    ).reset_index()
    g["redemption_rate"] = safe_div(g["redeemed"], g["engaged"]).round(4)
    return g.sort_values("revenue", ascending=False)


def by_channel(summary: pd.DataFrame) -> pd.DataFrame:
    g = summary.groupby("channel").agg(
        campaigns=("campaign_id", "count"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        redeemed=("redeemed", "sum"),
        engaged=("engaged", "sum"),
        revenue=("campaign_revenue", "sum"),
    ).reset_index()
    g["ctr"] = safe_div(g["clicks"], g["impressions"]).round(4)
    g["redemption_rate"] = safe_div(g["redeemed"], g["engaged"]).round(4)
    return g.sort_values("revenue", ascending=False)


def by_month(data: dict) -> pd.DataFrame:
    txn = data["txn"].copy()
    txn["month"] = pd.to_datetime(txn["transaction_date"]).dt.strftime("%Y-%m")
    g = txn.groupby("month").agg(
        campaign_transactions=("transaction_id", "count"),
        campaign_revenue=("transaction_amount", "sum"),
        discount_cost=("discount_amount", "sum"),
    ).reset_index()
    g["campaign_revenue"] = g["campaign_revenue"].round(2)
    return g.sort_values("month")


def by_segment(data: dict) -> pd.DataFrame:
    txn = data["txn"].merge(data["rfm"], on="customer_id", how="left")
    txn["rfm_segment"] = txn["rfm_segment"].fillna("Unsegmented")
    g = txn.groupby("rfm_segment").agg(
        campaign_transactions=("transaction_id", "count"),
        campaign_revenue=("transaction_amount", "sum"),
        customers=("customer_id", "nunique"),
    ).reset_index()
    g["campaign_revenue"] = g["campaign_revenue"].round(2)
    return g.sort_values("campaign_revenue", ascending=False)


def merchant_performance(data: dict) -> pd.DataFrame:
    """Merchant view kept inside campaign analytics (not a separate system)."""
    all_txn = data["all_txn"]
    merch = data["merchants"]
    rfm = data["rfm"]
    t = all_txn.merge(merch, on="merchant_id", how="inner")
    g = t.groupby(["merchant_id", "merchant_name", "category"]).agg(
        revenue=("transaction_amount", "sum"),
        transactions=("transaction_id", "count"),
        customers=("customer_id", "nunique"),
        campaign_revenue=("transaction_amount",
                          lambda s: s[t.loc[s.index, "campaign_id"].notna()].sum()),
    ).reset_index()
    g["avg_txn_value"] = safe_div(g["revenue"], g["transactions"]).round(2)
    g["campaign_share_pct"] = (safe_div(g["campaign_revenue"], g["revenue"]) * 100).round(1)
    # repeat customer rate per merchant
    repeat = (t.groupby(["merchant_id", "customer_id"]).size().reset_index(name="n"))
    rep_rate = repeat.groupby("merchant_id")["n"].apply(lambda s: (s > 1).mean()).rename("repeat_rate")
    g = g.merge(rep_rate, on="merchant_id", how="left")
    g["repeat_rate"] = (g["repeat_rate"] * 100).round(1)
    g["revenue"] = g["revenue"].round(2)
    g["campaign_revenue"] = g["campaign_revenue"].round(2)
    return g.sort_values("revenue", ascending=False).reset_index(drop=True)


def main() -> None:
    cfg = load_config()
    margin_rate = cfg["margin_rate"]
    conn = sqlite3.connect(DB_PATH)
    try:
        data = _load(conn)
    finally:
        conn.close()

    OUTPUTS.mkdir(exist_ok=True)
    summary = campaign_summary(data, margin_rate)
    summary.to_csv(OUTPUTS / "campaign_performance.csv", index=False)
    by_category(summary).to_csv(OUTPUTS / "campaign_by_category.csv", index=False)
    by_channel(summary).to_csv(OUTPUTS / "campaign_by_channel.csv", index=False)
    by_month(data).to_csv(OUTPUTS / "campaign_by_month.csv", index=False)
    by_segment(data).to_csv(OUTPUTS / "campaign_by_segment.csv", index=False)
    merchant_performance(data).to_csv(OUTPUTS / "merchant_performance.csv", index=False)

    print("Campaign analytics written to outputs/ (campaign_performance.csv + breakdowns).\n")
    show = summary[["campaign_id", "campaign_category", "redeemed", "engaged",
                    "redemption_rate", "campaign_revenue", "discount_cost", "roi"]].head(10)
    print("Top campaigns by revenue:")
    print(show.to_string(index=False))
    print("\nROI summary: positive ROI campaigns =",
          int((summary["roi"] > 0).sum()), "of", len(summary))


if __name__ == "__main__":
    main()
