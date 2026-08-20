# Power BI — Click-by-Click Build Checklist

Follow top to bottom. **No relationships and no DAX are required** — `fact_transactions`
is already joined (it carries `category`, `rfm_segment`, `income_band`), and the
other files are pre-aggregated. Each visual reads one table.

Every step lists the **expected value** so you can confirm as you go. (Numbers come
from the default seed; if you regenerate with a different seed they will change.)

Time: ~25 minutes. Save as `dashboard/powerbi/FinSight.pbix`.

---

## Step 0 — Import the data (2 min)
Power BI Desktop → **Home ▸ Get data ▸ Text/CSV**. Import all 11 files from
`outputs/powerbi/`:

`fact_transactions.csv`, `dim_customers.csv`, `dim_campaigns.csv`,
`monthly_revenue.csv`, `category_revenue.csv`, `rfm_summary.csv`,
`campaign_performance.csv`, `merchant_performance.csv`, `anomalies.csv`,
`recommendations.csv`, `kpi_summary.csv`.

For each, click **Load** (not Transform — the data is already clean).

> Skip the Model view entirely. You do **not** need relationships for these visuals.

**One formatting fix:** in the Data pane, select `kpi_summary[campaign_redemption_rate]`
and `campaign_performance[redemption_rate]`, `[roi]`, and set **Format ▸ Percentage**
(and 0–1 stays as a ratio). Set money columns to **Whole number / thousands separator**.

---

## Step 1 — Page 1: Overview (8 min)
Rename the page tab to **Overview**.

**KPI cards** (Visual: *Card*). Add five cards, each from `kpi_summary`. Drag the
field in; if it shows a sum that's fine (one row). Expected:

| Card | Field | Expected |
|---|---|---|
| Total Revenue | `total_revenue` | **38,082,223** |
| Total Transactions | `total_transactions` | **21,857** |
| Active Customers | `active_customers` | **1,481** |
| Redemption Rate | `campaign_redemption_rate` | **56.5%** |
| Avg Transaction Value | `avg_transaction_value` | **1,742.34** |

**Monthly revenue** (Visual: *Line chart*) — table `monthly_revenue`:
- X axis = `month`, Y = `revenue`. 12 points, rising into festival months.

**Revenue by category** (Visual: *Clustered bar chart*) — table `category_revenue`:
- Y = `category`, X = `revenue`, sort descending.
- Top 3 should read **Dining (7.72M), Electronics (5.90M), Fuel (4.85M)**.

**Top campaigns** (Visual: *Clustered bar chart*) — table `campaign_performance`:
- Y = `campaign_name`, X = `campaign_revenue`.
- Visual filter: **Top N = 10** by `campaign_revenue`.
- #1 should be **Electronics Percentage Offer (CMP017), ~175,557**.

---

## Step 2 — Page 2: Customer Analytics (7 min)
New page → **Customer Analytics**.

**KPI cards** (Card):
| Card | Table.Field | Expected |
|---|---|---|
| Total Customers | `dim_customers` → Count of `customer_id` | **1,500** |
| Active Customers | `kpi_summary[active_customers]` | **1,481** |
| Repeat Customer Rate | `kpi_summary[repeat_customer_rate_pct]` | **96.9** |
| Avg Customer Value | card on `rfm_summary[avg_customer_value]` set to **Average** | ~ (auto) |

**Customers by segment** (*Donut* or *Bar*) — `rfm_summary`: legend/axis = `rfm_segment`,
values = `customers`. Expected: **High Value 558, Low Engagement 587, Regular 247, At Risk 89**.

**Revenue by segment** (*Clustered bar*) — `rfm_summary`: axis = `rfm_segment`, X = `revenue`.
High Value dominates (**~26.25M**).

**Spending distribution** (*Histogram look*: Clustered column) — `fact_transactions`:
axis = `transaction_amount`, values = Count of `transaction_id`. (Optional: create a
binned column via right-click `transaction_amount` ▸ **New group** ▸ bin size 500.)

**Category preference matrix** (*Matrix*) — `fact_transactions`:
Rows = `rfm_segment`, Columns = `category`, Values = Sum of `transaction_amount`.
Turn on conditional-formatting background colour on the values.

**Slicer** — `fact_transactions[income_band]` (or `dim_customers[income_band]`).

---

## Step 3 — Page 3: Campaign Analytics (7 min)
New page → **Campaign Analytics**. All visuals use `campaign_performance` unless noted.

**KPI cards**:
| Card | Field | Setting | Expected |
|---|---|---|---|
| Total Campaigns | `campaign_id` | Count | **30** |
| Avg ROI | `roi` | Average | **0.42** |
| Avg Redemption Rate | `redemption_rate` | Average | **56.8%** |
| Total Campaign Revenue | `campaign_revenue` | Sum | **1,984,383** |

**Redemption vs ROI** (*Scatter chart*) — the headline visual:
- X = `redemption_rate`, Y = `roi`, Size = `campaign_revenue`, Legend = `campaign_id`.
- Details = `campaign_name`.
- You should see points with **high redemption but ROI below zero** — the "popular but
  unprofitable" story. **11 of 30 campaigns have negative ROI.**

**ROI by campaign** (*Clustered bar*): axis = `campaign_name`, X = `roi`.
- Format ▸ Data colors ▸ **conditional formatting**: rule `roi < 0` → red.

**Underperforming campaigns** (*Table*): columns `campaign_id`, `campaign_category`,
`engaged`, `redeemed`, `redemption_rate`, `roi`.
- Visual filter `engaged ≥ 30`; sort `redemption_rate` ascending. Weakest ≈ **CMP007
  Healthcare, ~18%**.

**Anomalies** (*Table*) — table `anomalies`: columns `entity`, `metric`, `date`,
`current_value`, `baseline`, `pct_change`, `severity`. **31 rows** (25 large
transactions + 6 month-over-month drops).

**Top merchants** (*Clustered bar*) — `merchant_performance`: axis = `merchant_name`,
X = `revenue`, Top N = 10.

---

## Step 4 — Polish, save, capture (3 min)
- Apply one **theme** (View ▸ Themes) for consistent colour.
- Add a page title textbox on each page and a footer:
  *"All data is synthetic — portfolio project."*
- Keep ≤ 5 visuals per page; leave white space.
- **File ▸ Save as** → `dashboard/powerbi/FinSight.pbix`.
- Screenshot each page (Win+Shift+S) into `dashboard/powerbi/screenshots/`
  as `page1_overview.png`, `page2_customers.png`, `page3_campaigns.png`.

---

## Step 5 — Finish the repo
Add the screenshots to the README (a `## Screenshots` section) and commit:

```bash
git add dashboard/powerbi
git commit -m "Add Power BI dashboard (.pbix) and screenshots"
```

Then create a GitHub repo and push:

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/FinSight.git
git push -u origin main
```
