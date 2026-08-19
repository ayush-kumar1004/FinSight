# Power BI Dashboard — Build Instructions

The `.pbix` file is authored in **Power BI Desktop** (Windows). This folder ships
the data model and the exact build spec so the dashboard can be assembled in a few
minutes. Save your file here as `FinSight.pbix` and export page screenshots to
`dashboard/powerbi/screenshots/` for the README.

## 1. Load the data

Run the pipeline first so the CSVs exist:

```bash
python src/run_pipeline.py
```

In Power BI Desktop: **Get Data → Text/CSV** and load these from
`outputs/powerbi/`:

- `fact_transactions.csv`  (main fact table)
- `dim_customers.csv`
- `dim_campaigns.csv`
- `monthly_revenue.csv`
- `category_revenue.csv`
- `rfm_summary.csv`
- `campaign_performance.csv`
- `merchant_performance.csv`
- `anomalies.csv`
- `recommendations.csv`
- `kpi_summary.csv`

## 2. Model relationships (Model view)

- `fact_transactions[customer_id]`  →  `dim_customers[customer_id]`  (many-to-one)
- `fact_transactions[campaign_id]`  →  `dim_campaigns[campaign_id]`  (many-to-one)
- `fact_transactions[campaign_id]`  →  `campaign_performance[campaign_id]` (many-to-one, single direction)

Keep helper/aggregate tables (`monthly_revenue`, `category_revenue`, `rfm_summary`)
unrelated — use them directly on their own visuals.

## 3. Core DAX measures

Create these on `fact_transactions` (they match `docs/metrics_definitions.md`):

```DAX
Total Revenue = SUM(fact_transactions[transaction_amount])
Total Transactions = COUNTROWS(fact_transactions)
Active Customers = DISTINCTCOUNT(fact_transactions[customer_id])
Avg Transaction Value = DIVIDE([Total Revenue], [Total Transactions])
Campaign Revenue =
    CALCULATE([Total Revenue], fact_transactions[is_campaign_transaction] = 1)

-- redemption uses the interaction totals; simplest is to read kpi_summary,
-- or add campaign_interactions.csv and:
Redemption Rate =
    DIVIDE(SUM(campaign_performance[redeemed]), SUM(campaign_performance[engaged]))

Repeat Customer Rate =
    VAR perCust =
        ADDCOLUMNS(VALUES(fact_transactions[customer_id]),
                   "n", CALCULATE(COUNTROWS(fact_transactions)))
    RETURN DIVIDE(COUNTROWS(FILTER(perCust, [n] > 1)), COUNTROWS(perCust))
```

## 4. Pages (exactly 3)

### Page 1 — Overview
- **KPI cards:** Total Revenue, Total Transactions, Active Customers,
  Redemption Rate, Avg Transaction Value.
- **Line chart:** `monthly_revenue[revenue]` by `month`.
- **Bar chart:** `category_revenue[revenue]` by `category`.
- **Bar chart:** top campaigns — `campaign_performance[campaign_revenue]` by
  `campaign_name` (Top N = 10).

### Page 2 — Customer Analytics
- **KPI cards:** Total Customers, Active Customers, Repeat Customer Rate,
  Avg Customer Value.
- **Bar/donut:** customers by `rfm_summary[rfm_segment]`.
- **Bar:** revenue by `rfm_summary[rfm_segment]`.
- **Histogram/column:** spending distribution — `transaction_amount` (binned) or
  `monetary` from `dim_customers`.
- **Matrix:** `category` × `rfm_segment` revenue (category preference).
- **Slicer:** `income_band`.

### Page 3 — Campaign Analytics
- **KPI cards:** Total Campaigns, Avg ROI, Avg Redemption Rate, Total Campaign Revenue.
- **Scatter:** `redemption_rate` (x) vs `roi` (y), bubble size = `campaign_revenue`
  — highlights popular-but-unprofitable campaigns.
- **Bar:** `campaign_performance[roi]` by campaign (conditional colour: red < 0).
- **Table:** underperforming campaigns — filter `engaged >= 30`, sort
  `redemption_rate` ascending.
- **Table/cards:** `anomalies` — the flagged transaction and month-over-month drops.
- **Bar:** `merchant_performance[revenue]` — top merchants.

## 5. Formatting
- One consistent theme, generous white space, no more than ~4–5 visuals per page.
- Use conditional formatting on ROI (red for negative) and redemption rate.
- Title each page and add a one-line "synthetic data" note in the footer.
