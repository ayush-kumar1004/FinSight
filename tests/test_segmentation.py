"""Tests for RFM segmentation logic."""
import pandas as pd

import segmentation as seg


def test_quartile_score_range_and_inversion():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])
    normal = seg._quartile_score(s)
    inverted = seg._quartile_score(s, invert=True)
    assert set(normal.unique()).issubset({1, 2, 3, 4})
    # smallest value gets the highest inverted score (recency: fewer days = better)
    assert inverted.iloc[0] == 4
    assert inverted.iloc[-1] == 1


def test_assign_segment_high_value():
    row = {"r_score": 4, "f_score": 4, "m_score": 4}
    assert seg.assign_segment(row) == "High Value"


def test_assign_segment_at_risk():
    # was valuable (high F/M) but very stale (low recency score)
    row = {"r_score": 1, "f_score": 4, "m_score": 4}
    assert seg.assign_segment(row) == "At Risk"


def test_assign_segment_low_engagement():
    row = {"r_score": 3, "f_score": 1, "m_score": 1}
    assert seg.assign_segment(row) == "Low Engagement"


def test_assign_segment_regular_fallback():
    row = {"r_score": 3, "f_score": 3, "m_score": 2}
    assert seg.assign_segment(row) == "Regular"


def test_compute_rfm_recency_and_frequency():
    tx = pd.DataFrame({
        "customer_id": ["C1", "C1", "C2"],
        "transaction_id": ["T1", "T2", "T3"],
        "transaction_date": ["2026-07-01", "2026-07-31", "2026-01-01"],
        "transaction_amount": [100.0, 200.0, 500.0],
    })
    rfm = seg.compute_rfm(tx, as_of=pd.Timestamp("2026-07-31"))
    c1 = rfm[rfm["customer_id"] == "C1"].iloc[0]
    assert c1["frequency"] == 2
    assert c1["monetary"] == 300.0
    assert c1["recency_days"] == 0  # last txn on the as_of date
