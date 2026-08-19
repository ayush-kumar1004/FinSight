# Defect Ground Truth

**Why this document exists.** Real datasets are messy. To show that FinSight
takes data quality seriously *before* analysis, the generator runs a corruption
pass (Layer B) that injects a small, realistic set of data-quality problems into
the raw CSVs. Every planted defect is logged to `injected_defects.csv`.

The data-quality pipeline (`src/data_quality.py`) then inspects the raw data
**independently** and produces `outputs/data_quality_report.csv`. As an optional
validation step it can compare what it detected against this planted log
(precision/recall) — but the headline is simply:

> "I deliberately introduced common data-quality problems and built checks to
> catch them before the data entered the analysis."

All rates are configurable in `config/params.yaml → defects`. Defaults below.

---

## The six injected defect types

| # | Defect | Where | Default rate | How it's planted |
|---|---|---|---|---|
| 1 | **Missing values** | `customers.income_band`, `transactions.city` | 2.5% / 2% | values set to null |
| 2 | **Duplicate rows** | `transactions` | 100 rows | exact rows appended |
| 3 | **Orphan foreign keys** | `transactions.merchant_id` / `campaign_id` | 120 rows | point to `M9999` / `CMP999` (don't exist) |
| 4 | **Invalid categories** | `merchants.category` | 20 rows | malformed strings (`"Diningg"`, `"TRAVEL"`, `" fuel"`, …) |
| 5 | **Negative amounts** | `transactions.transaction_amount` | 15 rows | amount forced negative |
| 6 | **Extreme values / bad dates** | `transactions` | 25 / 10 rows | huge amounts (₹0.5–2M); date `2030-13-40` |

Total planted defects with defaults: ~760 records (dominated by missing values).

---

## The injected-defects log

`injected_defects.csv` columns:

| column | meaning |
|---|---|
| `dataset` | table the defect was planted in |
| `defect_type` | one of the six types above |
| `record_key` | primary key of the affected row |
| `detail` | short description of what was changed |

---

## How each defect is handled downstream

| Defect | Detection (`data_quality.py`) | Cleaning (`clean_data.py`) |
|---|---|---|
| Missing values | null count per column | income_band → `"Unknown"`; city → back-filled from the customer's city |
| Duplicate rows | duplicated `transaction_id` / full-row | drop duplicates, keep first |
| Orphan FKs | anti-join vs parent tables | drop orphan transactions (can't attribute them) |
| Invalid categories | value not in the allowed set | normalise where obvious (trim/case/typo map), else `"Unknown"` |
| Negative amounts | `amount < 0` | drop (a sale cannot be negative here) |
| Extreme values | IQR upper-fence flag | **kept and flagged**, never auto-deleted |
| Bad dates | unparseable / outside window | drop rows with unparseable dates |

**Design choice worth stating in an interview:** extreme values are *flagged, not
deleted*. A ₹900,000 transaction might be a data error or a genuinely large
purchase — that's a judgement call for review, not something a cleaning script
should silently throw away.
