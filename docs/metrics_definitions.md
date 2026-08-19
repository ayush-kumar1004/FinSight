# Metric Definitions

Every metric shown anywhere in the project (SQL, Python, Power BI, the AI summary)
uses the definitions below, so the numbers agree across layers. All division is
guarded against a zero denominator (returns NULL / NaN, never an error).

## Revenue & transactions
| metric | definition |
|---|---|
| Total revenue | `SUM(transaction_amount)` over all transactions |
| Total transactions | row count of `transactions` |
| Active customers | distinct `customer_id` appearing in `transactions` |
| Average transaction value | `SUM(transaction_amount) / COUNT(*)` |
| Monthly revenue | revenue grouped by `strftime('%Y-%m', transaction_date)` |
| Month-over-month growth % | `100 * (rev_m - rev_{m-1}) / rev_{m-1}` (LAG) |
| Repeat customer rate % | share of customers with more than one transaction |

## Campaign funnel
| metric | definition |
|---|---|
| CTR | `clicks / impressions` |
| Conversion rate | `redeemed / clicks` |
| Redemption rate | `redeemed / engaged` (redemption among engaged users) |
| Campaign revenue | `SUM(transaction_amount)` on that campaign's transactions |
| Discount cost | `SUM(discount_amount)` on that campaign's transactions |
| Margin revenue | `margin_rate * campaign_revenue` (`margin_rate = 0.15` in params.yaml) |
| ROI | `(margin_revenue - discount_cost) / discount_cost` |

**Why this ROI.** It measures the offer's unit economics — margin earned on the
spend it drove versus the discount paid to drive it. This deliberately surfaces a
real tension: a campaign can have high revenue and high redemption yet a
**negative ROI** if its discount is deeper than the margin. `campaign_budget` is
reported for context but is a planned figure, so it is not used in ROI.

## RFM segmentation
- **Recency** = days since the customer's last transaction (as of the window end).
- **Frequency** = number of transactions.
- **Monetary** = total spend.
- Each is scored **1–4 by quartile** (recency inverted: fewer days → higher score).
- Segment rules (first match wins):
  - **At Risk** — `r_score ≤ 1` and (`f_score ≥ 3` or `m_score ≥ 3`)
  - **High Value** — `f_score ≥ 3` and `m_score ≥ 3` and `r_score ≥ 2`
  - **Low Engagement** — `f_score ≤ 2` and `m_score ≤ 2`
  - **Regular** — everything else

## Anomaly detection
- **Transaction amount** — flagged if above the `Q3 + 3*IQR` fence computed on
  `log10(amount)` (log space handles the right-skew). Flag only.
- **Campaign month-over-month** — a month is flagged if campaign revenue drops
  ≥ 30% or overall redemption rate drops ≥ 25% versus the previous month.
- Severity is High for larger moves, Medium otherwise. Nothing is deleted.
