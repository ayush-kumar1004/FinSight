"""Tests for campaign metric formulas (esp. safe division and ROI)."""
import numpy as np
import pandas as pd

import campaign_analytics as ca


def test_safe_div_handles_zero_denominator():
    out = ca.safe_div([10, 5, 0], [2, 0, 0])
    assert out[0] == 5.0
    assert np.isnan(out[1])   # 5 / 0 -> NaN, not an error
    assert np.isnan(out[2])


def test_campaign_summary_metrics():
    data = {
        "campaigns": pd.DataFrame({
            "campaign_id": ["CMP1", "CMP2"],
            "campaign_name": ["A", "B"],
            "campaign_category": ["Dining", "Travel"],
            "merchant_id": ["M1", "M2"],
            "channel": ["App", "Web"],
            "discount_type": ["Percentage", "Flat"],
            "discount_value": [10, 100],
            "campaign_budget": [50000, 50000],
        }),
        "interactions": pd.DataFrame({
            "campaign_id": ["CMP1", "CMP1", "CMP2"],
            "impression": [1, 1, 1], "click": [1, 1, 0],
            "engaged": [1, 1, 0], "redeemed": [1, 0, 0],
        }),
        "txn": pd.DataFrame({
            "campaign_id": ["CMP1", "CMP1"],
            "transaction_id": ["T1", "T2"],
            "transaction_amount": [1000.0, 2000.0],
            "discount_amount": [100.0, 200.0],
            "transaction_date": ["2025-08-01", "2025-08-02"],
            "customer_id": ["C1", "C2"],
        }),
    }
    summary = ca.campaign_summary(data, margin_rate=0.15)
    cmp1 = summary[summary["campaign_id"] == "CMP1"].iloc[0]

    # CTR = clicks/impressions = 2/2 = 1.0
    assert cmp1["ctr"] == 1.0
    # redemption rate = redeemed/engaged = 1/2 = 0.5
    assert cmp1["redemption_rate"] == 0.5
    # revenue = 3000, margin = 450, discount cost = 300 -> ROI = (450-300)/300 = 0.5
    assert cmp1["campaign_revenue"] == 3000.0
    assert cmp1["roi"] == 0.5

    # CMP2 has no clicks/engaged/txns -> metrics must be NaN, not a crash
    cmp2 = summary[summary["campaign_id"] == "CMP2"].iloc[0]
    assert np.isnan(cmp2["redemption_rate"])


def test_roi_negative_when_discount_exceeds_margin():
    """A deep discount should produce negative ROI even with high revenue."""
    data = {
        "campaigns": pd.DataFrame({
            "campaign_id": ["CMP1"], "campaign_name": ["A"],
            "campaign_category": ["Dining"], "merchant_id": ["M1"],
            "channel": ["App"], "discount_type": ["Percentage"],
            "discount_value": [30], "campaign_budget": [1000],
        }),
        "interactions": pd.DataFrame({
            "campaign_id": ["CMP1"], "impression": [1], "click": [1],
            "engaged": [1], "redeemed": [1],
        }),
        "txn": pd.DataFrame({
            "campaign_id": ["CMP1"], "transaction_id": ["T1"],
            "transaction_amount": [1000.0], "discount_amount": [300.0],
            "transaction_date": ["2025-08-01"], "customer_id": ["C1"],
        }),
    }
    summary = ca.campaign_summary(data, margin_rate=0.15)
    # margin = 150, discount = 300 -> ROI = (150-300)/300 = -0.5
    assert summary.iloc[0]["roi"] == -0.5
