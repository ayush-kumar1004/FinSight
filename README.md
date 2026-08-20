# FinSight — Customer & Campaign Analytics

> **All data in this project is synthetic and does not represent real customers,
> merchants or financial institutions.** It was generated with a seeded script for
> educational / portfolio purposes.

FinSight is a student-built customer and campaign analytics project. It uses
synthetic transaction and campaign data to explore how such data can be cleaned,
stored, queried and visualised to understand customer behaviour and evaluate
marketing campaigns. The emphasis is on a clear, explainable analytics workflow —
not on scale or infrastructure.

---

## 1. Project Overview

A small end-to-end analytics pipeline:

```
params.yaml -> generate data (+ inject defects) -> data-quality report
   -> clean -> SQLite -> SQL analytics / RFM / campaign analytics
   -> anomaly detection -> next-best-category -> verified metrics.json
   -> AI business summary -> Power BI CSVs -> Power BI dashboard + Excel
```

Everything is reproducible from a single seed.

## 2. Why I Built It

I already work with Python, Pandas and SQL, and I wanted a single project to
practise the business-analytics skills I am currently learning — advanced SQL,
Excel and Power BI — on a realistic problem. Customer and campaign analytics is a
common, understandable business scenario, so I built a synthetic version of it end
to end rather than following a tutorial.

## 3. Problem Statement

Given raw customer, merchant, campaign, transaction and interaction data:
- Which customers are most valuable, and which are slipping away?
- Which campaigns actually work — and are they profitable, not just popular?
- Where is data quality poor, and how do we stop bad data reaching the analysis?
- Can these findings be communicated clearly to a business reader?

## 4. Tech Stack

Python · Pandas · NumPy · SQL · SQLite · Excel · Power BI · Gemini API
(matplotlib/seaborn for notebook EDA, openpyxl for the workbook, pytest for tests).

No web framework, cloud, or big-data tooling — intentionally, since none of it
would add value at this size.

## 5. Dataset

Default sizes (configurable in `config/params.yaml`):

| table | rows |
|---|---|
| customers | 1,500 |
| merchants | 60 |
| campaigns | 30 |
| transactions | ~22,000 |
| campaign_interactions | 12,000 |

Date window: **Aug 2025 – Jul 2026**. See `docs/data_dictionary.md`.

## 6. Data Generation

Two layers (`src/generate_data.py`):
- **Layer A — clean canonical data** built from five documented behavioural
  relationships (income→spend, category preference→engagement, campaign
  quality→redemption, engagement persona→funnel, seasonality). See
  `docs/ground_truth/behavioral_spec.md`.
- **Layer B — corruption pass** that injects six realistic data-quality defects
  and logs every one to `docs/ground_truth/injected_defects.csv`.

> Because the data is synthetic, I documented the relationships I intentionally
> introduced instead of pretending that every pattern I found was a real
> discovery. Hidden generation labels are kept out of the analytics data entirely.

## 7. Data Quality

`src/data_quality.py` inspects the raw data and writes
`outputs/data_quality_report.csv` (dataset, column, issue, count, example,
recommended action). It detects missing values, duplicate ids/rows, orphan foreign
keys, invalid categories, negative amounts, extreme values and invalid dates.

- `campaign_id` nulls are **not** flagged — they legitimately mark non-campaign
  transactions.
- Extreme values are **flagged, not deleted** — a large transaction may be an
  error or a genuine purchase; that is a review decision.
- An optional step compares detected counts against the planted defect log
  (`outputs/data_quality_validation.csv`) as a sanity check.

`src/clean_data.py` then writes analysis-ready data to `data/processed/`.

## 8. SQL Analysis

`sql/schema.sql` builds a SQLite database with primary/foreign keys and indexes.
`sql/analytics_queries.sql` holds **18 business queries**, each commented with the
question it answers, using JOIN/LEFT JOIN, GROUP BY, HAVING, CASE WHEN, CTEs,
subqueries and window functions (ROW_NUMBER, RANK, DENSE_RANK, LAG).

## 9. RFM Segmentation

`src/segmentation.py` computes Recency, Frequency and Monetary from transaction
behaviour only, scores each 1–4 by quartile, and applies documented rules to
produce four explainable segments: **High Value, Regular, Low Engagement, At
Risk**. No K-Means, and no hidden label — see `docs/metrics_definitions.md`.

## 10. Campaign Analytics

`src/campaign_analytics.py` computes CTR, conversion rate, redemption rate,
revenue and ROI with safe division, broken down by campaign, category, merchant,
segment, channel and month. ROI is measured at the offer level (margin earned vs
discount paid), which surfaces a real insight: **a campaign can have high
redemption yet negative ROI when its discount is deeper than the margin.**

## 11. Anomaly Detection

`src/anomaly_detection.py` uses two simple, explainable methods:
1. **IQR in log space** on transaction amounts (amounts are right-skewed) to flag
   implausibly large values.
2. **Month-over-month % change** on campaign revenue and redemption to flag sudden
   drops.

Output: `outputs/anomalies.csv` (entity, metric, date, current value, baseline,
% change, reason, severity). These **flag for review** — they do not decide fraud
and delete nothing.

## 12. Next-Best-Category

`src/recommendation.py` recommends one category per customer from recent history,
frequency, overall preference and campaign engagement — always with a
human-readable reason. Rule-based and fully explainable by design (no ML).

## 13. AI Business Summary

`src/ai_insights.py` sends **only** the verified metrics in `outputs/metrics.json`
to Gemini, with a strict prompt: use only supplied numbers, never invent or
recompute, say so if information is missing. If `GEMINI_API_KEY` is absent the
pipeline still runs via a deterministic template. This is an experiment in using
an LLM to *communicate* verified results, not to analyse.

## 14. Power BI Dashboard

`src/export_powerbi.py` writes clean CSVs to `outputs/powerbi/` (a `fact_transactions`
table, dimensions, and pre-aggregated helpers). The dashboard has **3 pages**:
Overview, Customer Analytics, Campaign Analytics. Build steps and the exact
visual/measure list are in [`dashboard/powerbi/README.md`](dashboard/powerbi/README.md).

> The `.pbix` is authored in Power BI Desktop (Windows). This repo ships the data
> model and full build instructions; opening Power BI and following them takes a
> few minutes.

## 14b. Screenshots

Dashboard page screenshots live in `dashboard/powerbi/screenshots/`:

| Page | File |
|---|---|
| Overview | `screenshots/page1_overview.png` |
| Customer Analytics | `screenshots/page2_customers.png` |
| Campaign Analytics | `screenshots/page3_campaigns.png` |

_(Add your exported PNGs there; they render here once pushed to GitHub.)_

## 15. Excel Analysis

`excel/FinSight_Analytics.xlsx` (built by `excel/build_excel.py`) is a small
analyst-skill demo: a 500-row sample plus sheets using **XLOOKUP, SUMIFS,
COUNTIFS**, a formula-driven category×month cross-tab, a chart, and conditional
formatting. A native PivotTable can be added on `Raw_Data` in one step.

## 16. Project Structure

```
FinSight/
├── config/params.yaml          # one seed + all knobs
├── data/{raw,processed}/        # regenerable (gitignored)
├── db/finsight.db               # SQLite (gitignored)
├── docs/
│   ├── ground_truth/{behavioral_spec.md, defect_spec.md, injected_defects.csv}
│   ├── data_dictionary.md
│   └── metrics_definitions.md
├── src/                         # 11 pipeline modules + config.py + run_pipeline.py
├── sql/{schema.sql, analytics_queries.sql}
├── notebooks/{01_data_exploration, 02_customer_campaign_analysis}.ipynb
├── excel/{build_excel.py, FinSight_Analytics.xlsx}
├── dashboard/powerbi/           # build instructions (+ your .pbix)
├── outputs/                     # reports, metrics, anomalies, powerbi CSVs (gitignored)
├── tests/                       # pytest (20 tests)
├── requirements.txt, .env.example, .gitignore, README.md
```

## 17. How to Run

```bash
pip install -r requirements.txt
cp .env.example .env          # optional: add GEMINI_API_KEY (works without one)
python src/run_pipeline.py    # runs the whole pipeline end to end
python excel/build_excel.py   # builds the Excel workbook
pytest -q                     # runs the test suite
```

Individual steps can also be run directly, e.g. `python src/segmentation.py`.
Outputs land in `outputs/` and `outputs/powerbi/`. Then open Power BI Desktop and
follow `dashboard/powerbi/README.md`.

## 18. Limitations

- Synthetic data does not represent real customer behaviour; results are
  illustrative.
- RFM segmentation and the recommender are **rule-based**, not ML models.
- Anomaly detection flags unusual patterns for review; it does **not** determine
  fraud or root cause.
- Gemini only summarises pre-computed metrics; it performs no analysis.
- Power BI is a reporting layer, not the source of truth (the database is).
- The synthetic relationships are deliberately noisy, so signals are tendencies.

## 19. Future Improvements

- Try K-Means / other clustering and compare with the rule-based segments.
- Add campaign uplift modelling (treated vs control) instead of raw redemption.
- Track data-quality metrics over time rather than a single snapshot.
- Parameterise the AI summary for different audiences (exec vs analyst).

## 20. What I Learned

- Using **SQL** (window functions, CTEs, ranking) to answer business questions.
- **Data cleaning** and why validating data before analysis matters — analytics is
  only as good as its inputs.
- **RFM segmentation** and expressing it as clear, defensible business rules.
- **Dashboard design** in Power BI, and building a clean data model for it.
- **Responsible LLM use** — computing metrics in code and letting the model only
  narrate verified numbers.
- Designing a **reproducible pipeline** driven by a single config and seed.
