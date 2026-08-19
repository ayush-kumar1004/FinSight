"""Tests for the next-best-category recommender."""
import pandas as pd

import recommendation as rec


def test_recent_activity_drives_recommendation():
    as_of = pd.Timestamp("2026-07-31")
    txn = pd.DataFrame({
        "customer_id": ["C1", "C1", "C1"],
        "transaction_date": ["2026-07-01", "2026-07-15", "2026-01-01"],
        "category": ["Travel", "Travel", "Dining"],
    })
    engaged = pd.DataFrame({"customer_id": [], "campaign_category": []})
    recs, _, _ = rec.build_recommendations(txn, engaged, as_of, popular_category="Dining")
    row = recs[recs["customer_id"] == "C1"].iloc[0]
    assert row["recommended_category"] == "Travel"     # recent favourite
    assert row["basis"] == "recent_activity"


def test_falls_back_to_overall_history_when_no_recent_activity():
    as_of = pd.Timestamp("2026-07-31")
    txn = pd.DataFrame({
        "customer_id": ["C2", "C2"],
        "transaction_date": ["2025-09-01", "2025-09-05"],  # >90 days before as_of
        "category": ["Fuel", "Fuel"],
    })
    engaged = pd.DataFrame({"customer_id": [], "campaign_category": []})
    recs, _, _ = rec.build_recommendations(txn, engaged, as_of, popular_category="Dining")
    row = recs[recs["customer_id"] == "C2"].iloc[0]
    assert row["recommended_category"] == "Fuel"
    assert row["basis"] == "overall_history"


def test_engagement_mentioned_in_reason():
    as_of = pd.Timestamp("2026-07-31")
    txn = pd.DataFrame({
        "customer_id": ["C3"],
        "transaction_date": ["2026-07-10"],
        "category": ["Travel"],
    })
    engaged = pd.DataFrame({"customer_id": ["C3"], "campaign_category": ["Travel"]})
    recs, _, _ = rec.build_recommendations(txn, engaged, as_of, popular_category="Dining")
    row = recs[recs["customer_id"] == "C3"].iloc[0]
    assert row["engaged_in_category"] == 1
    assert "engaged" in row["reason"].lower()


def test_every_recommendation_has_a_reason():
    as_of = pd.Timestamp("2026-07-31")
    txn = pd.DataFrame({
        "customer_id": ["C1", "C2"],
        "transaction_date": ["2026-07-10", "2026-06-10"],
        "category": ["Dining", "Shopping"],
    })
    engaged = pd.DataFrame({"customer_id": [], "campaign_category": []})
    recs, _, _ = rec.build_recommendations(txn, engaged, as_of, popular_category="Dining")
    assert recs["reason"].str.len().gt(0).all()
    assert recs["recommended_category"].notna().all()
