"""Synthetic data generator for FinSight.

Two layers:
  Layer A  -- clean, internally-consistent canonical data built from 5 documented
              behavioural relationships (B1..B5 in docs/ground_truth/behavioral_spec.md).
  Layer B  -- a corruption pass that injects 6 realistic data-quality defects and
              logs every planted defect to docs/ground_truth/injected_defects.csv.

The hidden generation labels (generation_persona, campaign quality, category
preference) are NEVER written into the analytics CSVs. They live only in the
ground-truth folder so the later analysis is an honest re-discovery.

Run:  python src/generate_data.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    load_config, ensure_dirs, DATA_RAW, DOCS_GT,
)

# ---------- id helpers ----------

def _ids(prefix: str, n: int, width: int) -> list[str]:
    return [f"{prefix}{i:0{width}d}" for i in range(1, n + 1)]


# ---------- Layer A: clean canonical data ----------

def build_customers(cfg: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (customers_analytics, hidden_labels).

    hidden_labels carries generation_persona + preferred_category and is written
    ONLY to the ground-truth folder, never to the analytics dataset.
    """
    n = cfg["counts"]["customers"]
    cats = cfg["categories"]
    cust_ids = _ids("C", n, 5)

    income = rng.choice(cfg["income_bands"], size=n, p=[0.18, 0.24, 0.30, 0.18, 0.10])
    # Income loosely nudges account type / credit band (tendency, not a rule).
    acct = np.where(
        np.isin(income, ["High", "Upper-Mid"]),
        rng.choice(cfg["account_types"], size=n, p=[0.25, 0.45, 0.30]),
        rng.choice(cfg["account_types"], size=n, p=[0.65, 0.30, 0.05]),
    )

    start = pd.Timestamp(cfg["dates"]["start"])
    # customer_since: sometime in the ~4 years before the data window opens.
    since = start - pd.to_timedelta(rng.integers(30, 365 * 4, size=n), unit="D")

    customers = pd.DataFrame({
        "customer_id": cust_ids,
        "age": rng.integers(19, 68, size=n),
        "gender": rng.choice(cfg["genders"], size=n, p=[0.52, 0.46, 0.02]),
        "city": rng.choice(_CITIES["city"], size=n),
        "income_band": income,
        "employment_type": rng.choice(cfg["employment"], size=n, p=[0.55, 0.22, 0.15, 0.08]),
        "account_type": acct,
        "customer_since": since.strftime("%Y-%m-%d"),
        "credit_score_band": rng.choice(cfg["credit_bands"], size=n, p=[0.12, 0.30, 0.40, 0.18]),
        "preferred_channel": rng.choice(cfg["channels"], size=n, p=[0.5, 0.3, 0.12, 0.08]),
    })
    # attach state consistent with city
    customers = customers.merge(_CITIES, on="city", how="left")

    # ---- hidden generation labels (NOT part of analytics) ----
    persona_names = list(cfg["engagement_persona"].keys())
    persona_p = [cfg["engagement_persona"][k]["weight"] for k in persona_names]
    hidden = pd.DataFrame({
        "customer_id": cust_ids,
        "generation_persona": rng.choice(persona_names, size=n, p=persona_p),
        "preferred_category": rng.choice(cats, size=n),
    })
    return customers, hidden


def build_merchants(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg["counts"]["merchants"]
    cats = cfg["categories"]
    ids = _ids("M", n, 4)
    category = rng.choice(cats, size=n)
    size = rng.choice(cfg["merchant_sizes"], size=n, p=[0.5, 0.35, 0.15])
    city = rng.choice(_CITIES["city"], size=n)
    start = pd.Timestamp(cfg["dates"]["start"])
    onboard = start - pd.to_timedelta(rng.integers(60, 365 * 3, size=n), unit="D")
    df = pd.DataFrame({
        "merchant_id": ids,
        "merchant_name": [f"{c} {s} #{i:03d}" for i, (c, s) in enumerate(zip(category, size), 1)],
        "category": category,
        "city": city,
        "merchant_size": size,
        "onboard_date": onboard.strftime("%Y-%m-%d"),
    }).merge(_CITIES, on="city", how="left")
    return df


def build_campaigns(cfg: dict, rng: np.random.Generator, merchants: pd.DataFrame
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (campaigns_analytics, hidden_quality)."""
    n = cfg["counts"]["campaigns"]
    ids = _ids("CMP", n, 3)
    cats = cfg["categories"]
    merch = merchants.sample(n, replace=True, random_state=int(rng.integers(1e9)))
    category = merch["category"].to_numpy()

    win_start = pd.Timestamp(cfg["dates"]["start"])
    win_end = pd.Timestamp(cfg["dates"]["end"])
    span_days = (win_end - win_start).days
    start_offsets = rng.integers(0, span_days - 40, size=n)
    starts = win_start + pd.to_timedelta(start_offsets, unit="D")
    durations = rng.integers(14, 45, size=n)
    ends = starts + pd.to_timedelta(durations, unit="D")

    disc_type = rng.choice(["Percentage", "Flat", "Cashback"], size=n, p=[0.5, 0.2, 0.3])
    disc_value = np.where(disc_type == "Percentage",
                          rng.integers(5, 30, size=n),
                          rng.choice([100, 150, 200, 250, 300, 500], size=n))

    campaigns = pd.DataFrame({
        "campaign_id": ids,
        "campaign_name": [f"{c} {t} Offer" for c, t in zip(category, disc_type)],
        "campaign_category": category,
        "merchant_id": merch["merchant_id"].to_numpy(),
        "start_date": starts.strftime("%Y-%m-%d"),
        "end_date": ends.strftime("%Y-%m-%d"),
        "target_segment": rng.choice(cats, size=n),  # a category we target
        "discount_type": disc_type,
        "discount_value": disc_value,
        "campaign_budget": rng.choice([50000, 75000, 100000, 150000, 200000], size=n),
        "channel": rng.choice(cfg["channels"], size=n, p=[0.5, 0.3, 0.1, 0.1]),
    })

    # ---- hidden latent quality (B3) ----
    q_names = list(cfg["campaign_quality"].keys())
    q_p = [cfg["campaign_quality"][k]["weight"] for k in q_names]
    hidden = pd.DataFrame({
        "campaign_id": ids,
        "latent_quality": rng.choice(q_names, size=n, p=q_p),
    })
    return campaigns, hidden


def _seasonal_month_weights(cfg: dict, category: str) -> np.ndarray:
    """Return a length-12 multiplier array for a category (B5)."""
    w = np.ones(12)
    season = cfg.get("seasonality", {}).get(category, {})
    for month, mult in season.items():
        w[int(month) - 1] = mult
    return w


def build_transactions(cfg: dict, rng: np.random.Generator,
                       customers: pd.DataFrame, hidden_cust: pd.DataFrame,
                       merchants: pd.DataFrame, campaigns: pd.DataFrame,
                       hidden_camp: pd.DataFrame) -> pd.DataFrame:
    n = cfg["counts"]["transactions"]
    cats = cfg["categories"]
    boost = cfg["category_preference_boost"]

    win_start = pd.Timestamp(cfg["dates"]["start"])
    win_end = pd.Timestamp(cfg["dates"]["end"])
    n_days = (win_end - win_start).days + 1

    # Pre-compute per-category seasonal day weights across the window.
    day_index = pd.date_range(win_start, win_end, freq="D")
    day_month = day_index.month.to_numpy()
    cat_day_weights = {c: _seasonal_month_weights(cfg, c)[day_month - 1] for c in cats}

    # Merchant sampling weighted by size (B7-lite: larger merchants see more volume).
    size_w = merchants["merchant_size"].map({"Small": 1.0, "Medium": 2.2, "Large": 4.0}).to_numpy()
    merch_p = size_w / size_w.sum()

    cust_lookup = customers.set_index("customer_id")
    pref_lookup = hidden_cust.set_index("customer_id")["preferred_category"].to_dict()
    income_amount = cfg["income_amount"]

    # Choose customers (active customers transact more; a random activity weight adds a long tail).
    activity = rng.gamma(shape=2.0, scale=1.0, size=len(customers))
    cust_p = activity / activity.sum()
    chosen_cust = rng.choice(customers["customer_id"].to_numpy(), size=n, p=cust_p)

    # For each txn, pick a category influenced by the customer's preferred category (B2).
    base_p = np.ones(len(cats)) / len(cats)
    cat_index = {c: i for i, c in enumerate(cats)}
    tx_categories = np.empty(n, dtype=object)
    for i, cid in enumerate(chosen_cust):
        p = base_p.copy()
        pref = pref_lookup.get(cid)
        if pref is not None:
            p[cat_index[pref]] += boost / len(cats)
        p = p / p.sum()
        tx_categories[i] = cats[rng.choice(len(cats), p=p)]

    # Pick a merchant within the chosen category (fall back to any if none in category).
    merch_by_cat = {c: merchants[merchants["category"] == c] for c in cats}
    merch_ids = np.empty(n, dtype=object)
    for i, c in enumerate(tx_categories):
        pool = merch_by_cat[c]
        if len(pool) == 0:
            pool = merchants
        w = pool["merchant_size"].map({"Small": 1.0, "Medium": 2.2, "Large": 4.0}).to_numpy()
        merch_ids[i] = pool["merchant_id"].to_numpy()[rng.choice(len(pool), p=w / w.sum())]

    # Transaction dates: seasonal weighting depends on the txn category.
    tx_dates = np.empty(n, dtype="datetime64[ns]")
    for c in cats:
        mask = tx_categories == c
        k = int(mask.sum())
        if k == 0:
            continue
        w = cat_day_weights[c]
        w = w / w.sum()
        day_offsets = rng.choice(n_days, size=k, p=w)
        tx_dates[mask] = (win_start + pd.to_timedelta(day_offsets, unit="D")).to_numpy()

    # Amounts driven by income band (B1).
    income_bands = cust_lookup.loc[chosen_cust, "income_band"].to_numpy()
    mu = np.array([income_amount[b]["mu"] for b in income_bands])
    sigma = np.array([income_amount[b]["sigma"] for b in income_bands])
    amounts = np.round(rng.lognormal(mean=mu, sigma=sigma), 2)

    df = pd.DataFrame({
        "transaction_id": _ids("T", n, 8),
        "customer_id": chosen_cust,
        "merchant_id": merch_ids,
        "campaign_id": pd.NA,
        "transaction_date": pd.to_datetime(tx_dates).strftime("%Y-%m-%d"),
        "transaction_amount": amounts,
        "payment_channel": rng.choice(cfg["channels"], size=n, p=[0.55, 0.3, 0.08, 0.07]),
        "city": cust_lookup.loc[chosen_cust, "city"].to_numpy(),
        "is_campaign_transaction": 0,
        "discount_amount": 0.0,
    })

    # Attach a subset of transactions to campaigns that were live on that date and
    # match the campaign category (this is what redemption later measures).
    _attach_campaigns(cfg, rng, df, tx_categories, campaigns, hidden_camp)
    return df


def _attach_campaigns(cfg, rng, df, tx_categories, campaigns, hidden_camp):
    """Mark ~a fraction of transactions as campaign redemptions, weighted by the
    campaign's latent quality (B3). Mutates df in place."""
    camp = campaigns.merge(hidden_camp, on="campaign_id")
    camp["start"] = pd.to_datetime(camp["start_date"])
    camp["end"] = pd.to_datetime(camp["end_date"])
    q_redeem = {k: v["base_redemption"] for k, v in cfg["campaign_quality"].items()}

    tx_date = pd.to_datetime(df["transaction_date"])
    for c in camp.itertuples(index=False):
        # candidate txns: same category, date within campaign window, not yet attached
        mask = (
            (tx_categories == c.campaign_category)
            & (tx_date >= c.start) & (tx_date <= c.end)
            & (df["campaign_id"].isna())
        )
        idx = np.where(mask.to_numpy())[0]
        if len(idx) == 0:
            continue
        take = rng.random(len(idx)) < (q_redeem[c.latent_quality] * 3.0)  # scale to get visible volume
        sel = idx[take]
        if len(sel) == 0:
            continue
        df.loc[df.index[sel], "campaign_id"] = c.campaign_id
        df.loc[df.index[sel], "is_campaign_transaction"] = 1
        if c.discount_type == "Percentage":
            disc = df.loc[df.index[sel], "transaction_amount"] * (c.discount_value / 100.0)
        else:
            disc = float(c.discount_value)
        df.loc[df.index[sel], "discount_amount"] = np.round(disc, 2)


def build_interactions(cfg: dict, rng: np.random.Generator,
                       customers: pd.DataFrame, hidden_cust: pd.DataFrame,
                       campaigns: pd.DataFrame, hidden_camp: pd.DataFrame,
                       transactions: pd.DataFrame) -> pd.DataFrame:
    """Campaign funnel: impression -> click -> engage -> redeem.

    click/engage propensity comes from the customer's engagement persona (B4);
    redeem propensity is also lifted by campaign quality (B3). If a customer
    actually has a campaign transaction, that interaction is marked redeemed.
    """
    n = cfg["counts"]["interactions"]
    persona = cfg["engagement_persona"]
    q_redeem = {k: v["base_redemption"] for k, v in cfg["campaign_quality"].items()}

    cust_ids = customers["customer_id"].to_numpy()
    camp = campaigns.merge(hidden_camp, on="campaign_id")
    camp["start"] = pd.to_datetime(camp["start_date"])
    camp["end"] = pd.to_datetime(camp["end_date"])

    chosen_cust = rng.choice(cust_ids, size=n)
    chosen_camp_idx = rng.integers(0, len(camp), size=n)
    persona_lookup = hidden_cust.set_index("customer_id")["generation_persona"].to_dict()

    # interaction date within the campaign window
    dates = []
    for ci in chosen_camp_idx:
        s, e = camp["start"].iloc[ci], camp["end"].iloc[ci]
        span = max((e - s).days, 1)
        dates.append(s + pd.to_timedelta(int(rng.integers(0, span + 1)), unit="D"))
    dates = pd.to_datetime(dates)

    click = np.zeros(n, dtype=int)
    engage = np.zeros(n, dtype=int)
    redeem = np.zeros(n, dtype=int)
    for i in range(n):
        p = persona[persona_lookup[chosen_cust[i]]]
        cl = int(rng.random() < p["click"])
        en = int(cl and rng.random() < p["engage"])
        q = camp["latent_quality"].iloc[chosen_camp_idx[i]]
        rd = int(en and rng.random() < (p["redeem"] * (q_redeem[q] / 0.06)))
        click[i], engage[i], redeem[i] = cl, en, rd

    df = pd.DataFrame({
        "interaction_id": _ids("I", n, 7),
        "customer_id": chosen_cust,
        "campaign_id": camp["campaign_id"].to_numpy()[chosen_camp_idx],
        "interaction_date": dates.strftime("%Y-%m-%d"),
        "channel": rng.choice(cfg["channels"], size=n, p=[0.55, 0.3, 0.08, 0.07]),
        "impression": 1,
        "click": click,
        "engaged": engage,
        "redeemed": redeem,
    })
    return df


# ---------- reference: small city/state table (India-flavoured, synthetic) ----------
_CITIES = pd.DataFrame({
    "city":  ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata", "Hyderabad",
              "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Kochi", "Indore"],
    "state": ["Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "West Bengal",
              "Telangana", "Maharashtra", "Gujarat", "Rajasthan", "Uttar Pradesh",
              "Kerala", "Madhya Pradesh"],
})


# ---------- Layer B: corruption pass ----------

def corrupt(cfg: dict, rng: np.random.Generator, tables: dict) -> pd.DataFrame:
    """Inject 6 defect types. Returns the injected-defects log DataFrame.
    Mutates the raw tables in `tables` in place."""
    d = cfg["defects"]
    log = []  # rows: dataset, defect_type, key, detail

    cust = tables["customers"]
    txn = tables["transactions"]
    merch = tables["merchants"]

    # 1) missing values -------------------------------------------------------
    k = max(1, int(len(cust) * d["missing_income_frac"]))
    idx = rng.choice(cust.index, size=k, replace=False)
    cust.loc[idx, "income_band"] = np.nan
    for cid in cust.loc[idx, "customer_id"]:
        log.append(["customers", "missing_value", cid, "income_band set null"])

    k = max(1, int(len(txn) * d["missing_city_frac"]))
    idx = rng.choice(txn.index, size=k, replace=False)
    txn.loc[idx, "city"] = np.nan
    for tid in txn.loc[idx, "transaction_id"]:
        log.append(["transactions", "missing_value", tid, "city set null"])

    # 2) duplicate transaction rows ------------------------------------------
    k = d["duplicate_txn_rows"]
    dup_src = txn.sample(k, random_state=int(rng.integers(1e9)))
    tables["transactions"] = pd.concat([txn, dup_src], ignore_index=True)
    txn = tables["transactions"]
    for tid in dup_src["transaction_id"]:
        log.append(["transactions", "duplicate_row", tid, "exact duplicate appended"])

    # 3) orphan foreign keys --------------------------------------------------
    k = d["orphan_fk_rows"]
    idx = rng.choice(txn.index, size=k, replace=False)
    half = k // 2
    txn.loc[idx[:half], "merchant_id"] = "M9999"      # non-existent merchant
    txn.loc[idx[half:], "campaign_id"] = "CMP999"     # non-existent campaign
    for tid in txn.loc[idx[:half], "transaction_id"]:
        log.append(["transactions", "orphan_fk", tid, "merchant_id=M9999"])
    for tid in txn.loc[idx[half:], "transaction_id"]:
        log.append(["transactions", "orphan_fk", tid, "campaign_id=CMP999"])

    # 4) invalid categories (malformed strings) ------------------------------
    k = d["invalid_category_rows"]
    idx = rng.choice(merch.index, size=k, replace=False)
    bad = rng.choice(["Diningg", "TRAVEL", " fuel", "shoping", "Electronic"], size=k)
    merch.loc[idx, "category"] = bad
    for mid, b in zip(merch.loc[idx, "merchant_id"], bad):
        log.append(["merchants", "invalid_category", mid, f"category='{b}'"])

    # 5) negative transaction amounts ----------------------------------------
    k = d["negative_amount_rows"]
    idx = rng.choice(txn.index, size=k, replace=False)
    txn.loc[idx, "transaction_amount"] = -np.abs(txn.loc[idx, "transaction_amount"])
    for tid in txn.loc[idx, "transaction_id"]:
        log.append(["transactions", "negative_amount", tid, "amount made negative"])

    # 6) extreme values + bad dates ------------------------------------------
    k = d["extreme_value_rows"]
    idx = rng.choice(txn.index, size=k, replace=False)
    # Suspiciously large but not economy-breaking: ~3-8x the legitimate max, so
    # IQR clearly flags them while total revenue stays believable. Kept, flagged.
    txn.loc[idx, "transaction_amount"] = rng.integers(50_000, 150_000, size=k).astype(float)
    for tid in txn.loc[idx, "transaction_id"]:
        log.append(["transactions", "extreme_value", tid, "amount inflated (kept, flag only)"])

    k = d["bad_date_rows"]
    idx = rng.choice(txn.index, size=k, replace=False)
    txn.loc[idx, "transaction_date"] = "2030-13-40"  # clearly invalid / out of window
    for tid in txn.loc[idx, "transaction_id"]:
        log.append(["transactions", "bad_date", tid, "date=2030-13-40"])

    return pd.DataFrame(log, columns=["dataset", "defect_type", "record_key", "detail"])


# ---------- driver ----------

def main() -> None:
    ensure_dirs()
    cfg = load_config()
    rng = np.random.default_rng(cfg["seed"])

    customers, hidden_cust = build_customers(cfg, rng)
    merchants = build_merchants(cfg, rng)
    campaigns, hidden_camp = build_campaigns(cfg, rng, merchants)
    transactions = build_transactions(cfg, rng, customers, hidden_cust,
                                      merchants, campaigns, hidden_camp)
    interactions = build_interactions(cfg, rng, customers, hidden_cust,
                                      campaigns, hidden_camp, transactions)

    tables = {
        "customers": customers.copy(),
        "merchants": merchants.copy(),
        "campaigns": campaigns.copy(),
        "transactions": transactions.copy(),
        "campaign_interactions": interactions.copy(),
    }

    # Corruption pass (Layer B) operates on the raw copies we will write out.
    defect_log = corrupt(cfg, rng, tables)

    # Write raw (corrupted) analytics tables.
    for name, df in tables.items():
        df.to_csv(DATA_RAW / f"{name}.csv", index=False)

    # Write hidden ground-truth labels (never part of analytics).
    hidden_cust.to_csv(DOCS_GT / "generation_labels_customers.csv", index=False)
    hidden_camp.to_csv(DOCS_GT / "generation_labels_campaigns.csv", index=False)
    defect_log.to_csv(DOCS_GT / "injected_defects.csv", index=False)

    print("Generated raw data (with injected defects):")
    for name, df in tables.items():
        print(f"  {name:24s} {len(df):>7,} rows")
    print(f"  injected defects logged : {len(defect_log):>7,}")


if __name__ == "__main__":
    main()
