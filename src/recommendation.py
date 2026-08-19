"""Next-Best-Category — a simple, fully explainable rule-based recommender.

For each customer we recommend ONE spending category, using only transparent
signals:
  - recent transaction history (last N days, configurable)
  - transaction frequency within categories
  - overall category preference (fallback when there's no recent activity)
  - campaign engagement in the recommended category (adds confidence / reason)

Every recommendation carries a human-readable reason. There is no ML model, no
embedding and no black box — by design, so the logic can be explained and trusted.

Output: outputs/recommendations.csv
  customer_id, recommended_category, basis, reason, recent_txns, engaged_in_category
Run:  python src/recommendation.py
"""
from __future__ import annotations

import sqlite3
import pandas as pd

from config import load_config, DB_PATH, OUTPUTS

RECENT_DAYS = 90


def _top_category(df: pd.DataFrame) -> tuple[str | None, int, int]:
    """Return (top_category, count_in_top, total) for a customer's transactions."""
    if df.empty:
        return None, 0, 0
    counts = df["category"].value_counts()
    return counts.index[0], int(counts.iloc[0]), int(counts.sum())


def build_recommendations(txn: pd.DataFrame, engaged: pd.DataFrame,
                          as_of: pd.Timestamp, popular_category: str) -> pd.DataFrame:
    txn = txn.copy()
    txn["transaction_date"] = pd.to_datetime(txn["transaction_date"])
    recent_cutoff = as_of - pd.Timedelta(days=RECENT_DAYS)

    # set of (customer, category) the customer actually engaged with in campaigns
    engaged_set = set(zip(engaged["customer_id"], engaged["campaign_category"]))

    rows = []
    for cid, grp in txn.groupby("customer_id"):
        recent = grp[grp["transaction_date"] >= recent_cutoff]
        if not recent.empty:
            cat, cnt, total = _top_category(recent)
            basis = "recent_activity"
            share = round(100 * cnt / total, 0)
            reason = (f"{cat} was the customer's most frequent category in the last "
                      f"{RECENT_DAYS} days ({cnt} of {total} recent transactions).")
        else:
            cat, cnt, total = _top_category(grp)
            basis = "overall_history"
            share = round(100 * cnt / total, 0) if total else 0
            reason = (f"No activity in the last {RECENT_DAYS} days; {cat} is the "
                      f"customer's most frequent category overall.")

        engaged_here = (cid, cat) in engaged_set
        if engaged_here:
            reason += " They have previously engaged with a campaign in this category."

        rows.append({
            "customer_id": cid,
            "recommended_category": cat,
            "basis": basis,
            "reason": reason,
            "recent_txns": int(len(recent)),
            "engaged_in_category": int(engaged_here),
        })

    # cold-start: customers with no transactions at all
    recommended_ids = {r["customer_id"] for r in rows}
    return pd.DataFrame(rows), recommended_ids, popular_category


def main() -> None:
    cfg = load_config()
    as_of = pd.Timestamp(cfg["dates"]["end"])

    conn = sqlite3.connect(DB_PATH)
    try:
        txn = pd.read_sql(
            "SELECT t.customer_id, t.transaction_date, m.category "
            "FROM transactions t JOIN merchants m ON m.merchant_id = t.merchant_id", conn)
        engaged = pd.read_sql(
            "SELECT ci.customer_id, cp.campaign_category "
            "FROM campaign_interactions ci "
            "JOIN campaigns cp ON cp.campaign_id = ci.campaign_id "
            "WHERE ci.engaged = 1", conn)
        all_customers = pd.read_sql("SELECT customer_id FROM customers", conn)
        popular_category = txn["category"].value_counts().index[0]
    finally:
        conn.close()

    recs, done_ids, popular = build_recommendations(txn, engaged, as_of, popular_category)

    # cold-start rows for customers with no transactions
    cold = all_customers[~all_customers["customer_id"].isin(done_ids)].copy()
    if not cold.empty:
        cold_rows = pd.DataFrame({
            "customer_id": cold["customer_id"],
            "recommended_category": popular,
            "basis": "cold_start",
            "reason": (f"New or inactive customer with no transaction history; "
                       f"suggesting {popular}, the most popular category overall."),
            "recent_txns": 0,
            "engaged_in_category": 0,
        })
        recs = pd.concat([recs, cold_rows], ignore_index=True)

    OUTPUTS.mkdir(exist_ok=True)
    recs.to_csv(OUTPUTS / "recommendations.csv", index=False)

    print(f"Wrote {len(recs):,} recommendations -> outputs/recommendations.csv\n")
    print("Recommendation basis breakdown:")
    print(recs["basis"].value_counts().to_string())
    print("\nExample:")
    ex = recs.iloc[0]
    print(f"  Customer: {ex['customer_id']}")
    print(f"  Recommended category: {ex['recommended_category']}")
    print(f"  Reason: {ex['reason']}")


if __name__ == "__main__":
    main()
