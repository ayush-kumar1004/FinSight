"""Data-quality inspection for the raw synthetic data.

Detects the defect types described in docs/ground_truth/defect_spec.md, writes a
human-readable report to outputs/data_quality_report.csv, and (optionally)
compares what it detected against the planted defect log as a validation step.

Run:  python src/data_quality.py
"""
from __future__ import annotations

import pandas as pd

from config import load_config, ensure_dirs, DATA_RAW, DOCS_GT, OUTPUTS


def _load_raw() -> dict[str, pd.DataFrame]:
    names = ["customers", "merchants", "campaigns", "transactions", "campaign_interactions"]
    return {n: pd.read_csv(DATA_RAW / f"{n}.csv") for n in names}


def _valid_date(series: pd.Series, start, end) -> pd.Series:
    """True where the value parses to a date inside [start, end]."""
    d = pd.to_datetime(series, errors="coerce")
    return d.notna() & (d >= start) & (d <= end)


def run_checks(raw: dict[str, pd.DataFrame], cfg: dict) -> pd.DataFrame:
    rows = []
    def add(dataset, column, issue, count, example, action):
        rows.append({
            "dataset": dataset, "column": column, "issue": issue,
            "count": int(count), "example": example, "recommended_action": action,
        })

    cust, merch = raw["customers"], raw["merchants"]
    camp, txn = raw["campaigns"], raw["transactions"]
    allowed_cats = set(cfg["categories"])
    start = pd.Timestamp(cfg["dates"]["start"])
    end = pd.Timestamp(cfg["dates"]["end"])

    # --- missing values (all tables, per column) ---
    # transactions.campaign_id is legitimately null for non-campaign transactions,
    # so a null there is expected, not a defect — we skip it here.
    expected_null = {("transactions", "campaign_id")}
    for name, df in raw.items():
        for col in df.columns:
            if (name, col) in expected_null:
                continue
            n_missing = df[col].isna().sum()
            if n_missing:
                add(name, col, "missing_value", n_missing,
                    "", "impute or drop depending on column")

    # --- duplicate transaction ids + full duplicate rows ---
    dup_ids = txn["transaction_id"].duplicated().sum()
    if dup_ids:
        ex = txn.loc[txn["transaction_id"].duplicated(keep=False), "transaction_id"].iloc[0]
        add("transactions", "transaction_id", "duplicate_id", dup_ids, ex, "drop duplicates, keep first")
    dup_rows = txn.duplicated().sum()
    if dup_rows:
        add("transactions", "(all)", "duplicate_row", dup_rows, "", "drop exact duplicate rows")

    # --- orphan foreign keys ---
    orphan_m = (~txn["merchant_id"].isin(merch["merchant_id"])).sum()
    if orphan_m:
        ex = txn.loc[~txn["merchant_id"].isin(merch["merchant_id"]), "merchant_id"].iloc[0]
        add("transactions", "merchant_id", "orphan_fk", orphan_m, ex, "drop rows with unknown merchant")
    valid_camp = set(camp["campaign_id"])
    orphan_c = txn["campaign_id"].notna() & ~txn["campaign_id"].isin(valid_camp)
    if orphan_c.sum():
        ex = txn.loc[orphan_c, "campaign_id"].iloc[0]
        add("transactions", "campaign_id", "orphan_fk", orphan_c.sum(), ex, "drop rows with unknown campaign")

    # --- invalid categories (merchants) ---
    bad_cat = ~merch["category"].isin(allowed_cats)
    if bad_cat.sum():
        ex = merch.loc[bad_cat, "category"].iloc[0]
        add("merchants", "category", "invalid_category", bad_cat.sum(), ex,
            "normalise typo/case or set Unknown")

    # --- negative / zero amounts ---
    neg = (txn["transaction_amount"] < 0).sum()
    if neg:
        add("transactions", "transaction_amount", "negative_amount", neg,
            round(txn.loc[txn["transaction_amount"] < 0, "transaction_amount"].min(), 2),
            "drop (invalid sale)")
    zero = (txn["transaction_amount"] == 0).sum()
    if zero:
        add("transactions", "transaction_amount", "zero_amount", zero, 0, "review / drop")

    # --- extreme values — FLAG ONLY ---
    # Transaction amounts are log-normal (right-skewed), so the ordinary 1.5*IQR
    # fence flags the whole natural upper tail. For a *data-quality* flag we want
    # only implausibly large values, so we use the "far out" 3*IQR fence.
    pos = txn.loc[txn["transaction_amount"] > 0, "transaction_amount"]
    q1, q3 = pos.quantile(0.25), pos.quantile(0.75)
    upper = q3 + 3.0 * (q3 - q1)
    extreme = (txn["transaction_amount"] > upper).sum()
    if extreme:
        add("transactions", "transaction_amount", "extreme_value_flag", extreme,
            f"> {round(upper,2)} (3x IQR far-out fence)", "FLAG for review, do not auto-delete")

    # --- invalid dates ---
    bad_dates = (~_valid_date(txn["transaction_date"], start, end)).sum()
    if bad_dates:
        add("transactions", "transaction_date", "invalid_date", bad_dates,
            "unparseable or outside window", "drop unparseable dates")

    report = pd.DataFrame(rows, columns=[
        "dataset", "column", "issue", "count", "example", "recommended_action"])
    return report.sort_values(["dataset", "issue"]).reset_index(drop=True)


def validate_against_log(report: pd.DataFrame) -> pd.DataFrame | None:
    """OPTIONAL: compare detected defect counts vs the planted log by type.

    This is a light sanity check, not the main feature. Some detected counts
    exceed planted counts because a check can catch pre-existing edge cases too.
    """
    log_path = DOCS_GT / "injected_defects.csv"
    if not log_path.exists():
        return None
    log = pd.read_csv(log_path)
    planted = log.groupby("defect_type").size().rename("planted")

    # map report issue -> planted defect_type
    issue_to_type = {
        "missing_value": "missing_value",
        "duplicate_row": "duplicate_row",
        "duplicate_id": "duplicate_row",
        "orphan_fk": "orphan_fk",
        "invalid_category": "invalid_category",
        "negative_amount": "negative_amount",
        "extreme_value_flag": "extreme_value",
        "invalid_date": "bad_date",
    }
    detected = (report.assign(dtype=report["issue"].map(issue_to_type))
                      .dropna(subset=["dtype"])
                      .groupby("dtype")["count"].sum().rename("detected"))
    out = pd.concat([planted, detected], axis=1).fillna(0).astype(int)
    out["detected_at_least_planted"] = out["detected"] >= out["planted"]
    return out.reset_index().rename(columns={"index": "defect_type"})


def main() -> None:
    ensure_dirs()
    cfg = load_config()
    raw = _load_raw()
    report = run_checks(raw, cfg)
    OUTPUTS.mkdir(exist_ok=True)
    report.to_csv(OUTPUTS / "data_quality_report.csv", index=False)

    print("Data-quality report written to outputs/data_quality_report.csv")
    print(report.to_string(index=False))

    validation = validate_against_log(report)
    if validation is not None:
        validation.to_csv(OUTPUTS / "data_quality_validation.csv", index=False)
        print("\nOptional validation vs planted defect log:")
        print(validation.to_string(index=False))


if __name__ == "__main__":
    main()
