"""Tests for the data-quality checks."""
import numpy as np
import pandas as pd

import data_quality as dq


def _cfg():
    return {
        "categories": ["Dining", "Travel", "Fuel"],
        "dates": {"start": "2025-08-01", "end": "2026-07-31"},
    }


def _minimal_raw():
    customers = pd.DataFrame({
        "customer_id": ["C1", "C2"], "city": ["Mumbai", "Delhi"],
        "income_band": ["Low", np.nan],
    })
    merchants = pd.DataFrame({
        "merchant_id": ["M1", "M2"], "category": ["Dining", "Diningg"],
    })
    campaigns = pd.DataFrame({"campaign_id": ["CMP1"]})
    transactions = pd.DataFrame({
        "transaction_id": ["T1", "T2", "T2", "T3", "T4"],   # T2 duplicated
        "customer_id":    ["C1", "C1", "C1", "C2", "C2"],
        "merchant_id":    ["M1", "M1", "M1", "M9999", "M1"],  # M9999 orphan
        "campaign_id":    [None, None, None, None, None],
        "transaction_date": ["2025-08-10", "2025-08-11", "2025-08-11",
                              "2025-09-01", "2030-13-40"],    # last = bad date
        "transaction_amount": [100.0, 200.0, 200.0, -50.0, 300.0],  # -50 negative
        "city": ["Mumbai", np.nan, np.nan, "Delhi", "Delhi"],
    })
    interactions = pd.DataFrame({
        "interaction_id": ["I1"], "customer_id": ["C1"], "campaign_id": ["CMP1"],
        "impression": [1], "click": [1], "engaged": [1], "redeemed": [0],
    })
    return {"customers": customers, "merchants": merchants, "campaigns": campaigns,
            "transactions": transactions, "campaign_interactions": interactions}


def _count(report, issue):
    hit = report[report["issue"] == issue]["count"]
    return int(hit.sum())


def test_detects_missing_values():
    report = dq.run_checks(_minimal_raw(), _cfg())
    # one missing income_band + two missing city = 3
    assert _count(report, "missing_value") == 3


def test_detects_duplicate_transaction_id():
    report = dq.run_checks(_minimal_raw(), _cfg())
    assert _count(report, "duplicate_id") == 1


def test_detects_orphan_foreign_key():
    report = dq.run_checks(_minimal_raw(), _cfg())
    assert _count(report, "orphan_fk") >= 1


def test_detects_invalid_category():
    report = dq.run_checks(_minimal_raw(), _cfg())
    assert _count(report, "invalid_category") == 1  # "Diningg"


def test_detects_negative_amount():
    report = dq.run_checks(_minimal_raw(), _cfg())
    assert _count(report, "negative_amount") == 1


def test_detects_bad_date():
    report = dq.run_checks(_minimal_raw(), _cfg())
    assert _count(report, "invalid_date") == 1


def test_campaign_null_not_flagged_as_missing():
    """Null campaign_id is legitimate (non-campaign txn) and must NOT be a defect."""
    report = dq.run_checks(_minimal_raw(), _cfg())
    flagged_cols = set(report[report["issue"] == "missing_value"]["column"])
    assert "campaign_id" not in flagged_cols
