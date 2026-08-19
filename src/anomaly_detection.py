"""Anomaly detection — simple, explainable, flag-only.

Two methods, deliberately basic:

  1. IQR on transaction amounts. Amounts are right-skewed (log-normal), so the
     plain 1.5*IQR fence would flag the whole natural upper tail. We therefore
     apply IQR in log space and use the 3*IQR "far out" fence, which isolates
     genuinely implausible transactions.

  2. Month-over-month percentage change for campaign revenue and overall
     campaign redemption rate. A large negative change month-to-month is flagged
     as a possible sudden drop worth investigating.

These FLAG unusual behaviour for a human to review. They do not decide fraud and
they never delete anything.

Output: outputs/anomalies.csv with columns
  entity, metric, date, current_value, baseline, pct_change, reason, severity

Run:  python src/anomaly_detection.py
"""
from __future__ import annotations

import sqlite3
import numpy as np
import pandas as pd

from config import DB_PATH, OUTPUTS


def transaction_amount_anomalies(txn: pd.DataFrame) -> pd.DataFrame:
    pos = txn[txn["transaction_amount"] > 0].copy()
    logs = np.log10(pos["transaction_amount"])
    q1, q3 = logs.quantile(0.25), logs.quantile(0.75)
    fence_log = q3 + 3.0 * (q3 - q1)
    fence = 10 ** fence_log

    flagged = pos[pos["transaction_amount"] > fence].copy()
    if flagged.empty:
        return pd.DataFrame()

    flagged["pct_change"] = ((flagged["transaction_amount"] - fence) / fence * 100).round(1)
    # severity: >5x fence is High, else Medium
    flagged["severity"] = np.where(flagged["transaction_amount"] > 5 * fence, "High", "Medium")
    out = pd.DataFrame({
        "entity": flagged["transaction_id"],
        "metric": "transaction_amount",
        "date": flagged["transaction_date"],
        "current_value": flagged["transaction_amount"].round(2),
        "baseline": round(float(fence), 2),
        "pct_change": flagged["pct_change"],
        "reason": "Transaction amount far above the IQR (log-space, 3x) upper fence — review.",
        "severity": flagged["severity"],
    })
    return out.sort_values("current_value", ascending=False)


def _mom_flags(series: pd.DataFrame, value_col: str, entity: str, metric: str,
               drop_threshold: float) -> list[dict]:
    """Flag months where value dropped more than drop_threshold% vs previous month."""
    s = series.sort_values("month").reset_index(drop=True)
    s["prev"] = s[value_col].shift(1)
    s["pct_change"] = ((s[value_col] - s["prev"]) / s["prev"] * 100)
    rows = []
    for r in s.itertuples(index=False):
        if pd.notna(r.prev) and r.prev > 0 and r.pct_change <= drop_threshold:
            rows.append({
                "entity": entity,
                "metric": metric,
                "date": r.month,
                "current_value": round(float(getattr(r, value_col)), 4),
                "baseline": round(float(r.prev), 4),
                "pct_change": round(float(r.pct_change), 1),
                "reason": f"{metric} fell {abs(round(float(r.pct_change),1))}% vs the previous month.",
                "severity": "High" if r.pct_change <= 2 * drop_threshold else "Medium",
            })
    return rows


def campaign_mom_anomalies(txn: pd.DataFrame, inter: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    # (a) overall campaign revenue month over month
    ct = txn[txn["campaign_id"].notna()].copy()
    ct["month"] = pd.to_datetime(ct["transaction_date"]).dt.strftime("%Y-%m")
    rev = ct.groupby("month")["transaction_amount"].sum().reset_index(name="revenue")
    rows += _mom_flags(rev, "revenue", "ALL_CAMPAIGNS", "campaign_revenue", drop_threshold=-30)

    # (b) overall campaign redemption rate month over month
    ii = inter.copy()
    ii["month"] = pd.to_datetime(ii["interaction_date"]).dt.strftime("%Y-%m")
    m = ii.groupby("month").agg(redeemed=("redeemed", "sum"),
                                engaged=("engaged", "sum")).reset_index()
    m["redemption_rate"] = np.where(m["engaged"] > 0, m["redeemed"] / m["engaged"], np.nan)
    m = m.dropna(subset=["redemption_rate"])
    rows += _mom_flags(m, "redemption_rate", "ALL_CAMPAIGNS", "redemption_rate", drop_threshold=-25)

    return pd.DataFrame(rows)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        txn = pd.read_sql("SELECT * FROM transactions", conn)
        inter = pd.read_sql("SELECT * FROM campaign_interactions", conn)
    finally:
        conn.close()

    parts = [transaction_amount_anomalies(txn), campaign_mom_anomalies(txn, inter)]
    anomalies = pd.concat([p for p in parts if not p.empty], ignore_index=True)

    OUTPUTS.mkdir(exist_ok=True)
    anomalies.to_csv(OUTPUTS / "anomalies.csv", index=False)

    print(f"Flagged {len(anomalies)} anomalies -> outputs/anomalies.csv")
    print("  by metric:")
    print(anomalies.groupby(["metric", "severity"]).size().to_string())
    print("\nSample transaction-amount anomalies:")
    ta = anomalies[anomalies["metric"] == "transaction_amount"].head(5)
    print(ta[["entity", "current_value", "baseline", "severity"]].to_string(index=False))
    mom = anomalies[anomalies["metric"] != "transaction_amount"]
    if not mom.empty:
        print("\nMonth-over-month drops flagged:")
        print(mom[["metric", "date", "current_value", "baseline", "pct_change", "severity"]].to_string(index=False))


if __name__ == "__main__":
    main()
