"""RFM customer segmentation — rule-based and explainable.

Computes Recency / Frequency / Monetary from transaction behaviour ONLY (never
from any hidden generation label), scores each 1-4 by quartile, and maps every
customer to one of four business segments with a documented rule:

  High Value      -- frequent AND high-spending AND still active
  At Risk         -- previously valuable (high F or M) but has gone quiet (low R)
  Low Engagement  -- infrequent and low-spending
  Regular         -- everyone else (the solid middle)

Writes the result to the rfm_segments table and outputs/rfm_segments.csv.
Run:  python src/segmentation.py
"""
from __future__ import annotations

import sqlite3
import pandas as pd

from config import load_config, DB_PATH, OUTPUTS


def _quartile_score(series: pd.Series, invert: bool = False) -> pd.Series:
    """Score 1-4 by quartile. invert=True means smaller raw value scores higher
    (used for recency, where fewer days since last purchase is better)."""
    ranked = series.rank(method="first")
    q = pd.qcut(ranked, 4, labels=[1, 2, 3, 4]).astype(int)
    return (5 - q) if invert else q


def compute_rfm(transactions: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    tx = transactions.copy()
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])

    rfm = tx.groupby("customer_id").agg(
        last_txn=("transaction_date", "max"),
        frequency=("transaction_id", "count"),
        monetary=("transaction_amount", "sum"),
    ).reset_index()
    rfm["recency_days"] = (as_of - rfm["last_txn"]).dt.days

    rfm["r_score"] = _quartile_score(rfm["recency_days"], invert=True)
    rfm["f_score"] = _quartile_score(rfm["frequency"])
    rfm["m_score"] = _quartile_score(rfm["monetary"])
    return rfm


def assign_segment(row) -> str:
    r, f, m = row["r_score"], row["f_score"], row["m_score"]
    # 1) At Risk: was valuable (frequent or big spender) but has gone quiet.
    if r <= 1 and (f >= 3 or m >= 3):
        return "At Risk"
    # 2) High Value: frequent, high-spending and still reasonably recent.
    if f >= 3 and m >= 3 and r >= 2:
        return "High Value"
    # 3) Low Engagement: infrequent and low spend.
    if f <= 2 and m <= 2:
        return "Low Engagement"
    # 4) Everyone else.
    return "Regular"


def run() -> pd.DataFrame:
    cfg = load_config()
    as_of = pd.Timestamp(cfg["dates"]["end"])

    conn = sqlite3.connect(DB_PATH)
    try:
        tx = pd.read_sql("SELECT customer_id, transaction_id, transaction_date, "
                         "transaction_amount FROM transactions", conn)
        rfm = compute_rfm(tx, as_of)
        rfm["rfm_segment"] = rfm.apply(assign_segment, axis=1)

        out = rfm[["customer_id", "recency_days", "frequency", "monetary",
                   "r_score", "f_score", "m_score", "rfm_segment"]].copy()
        out["monetary"] = out["monetary"].round(2)

        # write to DB (replace the derived table's contents)
        conn.execute("DELETE FROM rfm_segments;")
        out.to_sql("rfm_segments", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()

    OUTPUTS.mkdir(exist_ok=True)
    out.to_csv(OUTPUTS / "rfm_segments.csv", index=False)
    return out


def main() -> None:
    out = run()
    print(f"Segmented {len(out):,} customers into RFM segments.\n")
    summary = out.groupby("rfm_segment").agg(
        customers=("customer_id", "count"),
        avg_recency_days=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
    ).round(1)
    print(summary.to_string())


if __name__ == "__main__":
    main()
