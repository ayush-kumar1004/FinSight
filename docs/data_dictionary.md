# Data Dictionary

All data is **synthetic**. Tables below describe the cleaned data as loaded into
`db/finsight.db`.

## customers
| column | type | description |
|---|---|---|
| customer_id | TEXT (PK) | unique customer id, e.g. `C00123` |
| age | INTEGER | 19–67 |
| gender | TEXT | Male / Female / Other |
| city | TEXT | home city |
| state | TEXT | state, consistent with city |
| income_band | TEXT | Low / Lower-Mid / Mid / Upper-Mid / High / Unknown (missing→Unknown) |
| employment_type | TEXT | Salaried / Self-Employed / Student / Retired |
| account_type | TEXT | Basic / Premium / Wealth |
| customer_since | TEXT | signup date (before the data window) |
| credit_score_band | TEXT | Poor / Fair / Good / Excellent |
| preferred_channel | TEXT | App / Web / Branch / Call |

> No `customer_segment` column — segments are derived by `segmentation.py`.

## merchants
| column | type | description |
|---|---|---|
| merchant_id | TEXT (PK) | e.g. `M0042` |
| merchant_name | TEXT | display name |
| category | TEXT | one of the 9 categories (invalid ones normalised in cleaning) |
| city / state | TEXT | location |
| merchant_size | TEXT | Small / Medium / Large |
| onboard_date | TEXT | date merchant joined |

## campaigns
| column | type | description |
|---|---|---|
| campaign_id | TEXT (PK) | e.g. `CMP021` |
| campaign_name | TEXT | display name |
| campaign_category | TEXT | category the campaign targets |
| merchant_id | TEXT (FK) | sponsoring merchant |
| start_date / end_date | TEXT | active window |
| target_segment | TEXT | intended audience (a category label) |
| discount_type | TEXT | Percentage / Flat / Cashback |
| discount_value | REAL | percent or rupee amount depending on type |
| campaign_budget | REAL | planned spend (not used in ROI) |
| channel | TEXT | delivery channel |

## transactions
| column | type | description |
|---|---|---|
| transaction_id | TEXT (PK) | e.g. `T00000123` |
| customer_id | TEXT (FK) | buyer |
| merchant_id | TEXT (FK) | merchant |
| campaign_id | TEXT (FK, nullable) | NULL = non-campaign transaction |
| transaction_date | TEXT | within the data window |
| transaction_amount | REAL | INR; extreme values are flagged, not removed |
| payment_channel | TEXT | App / Web / Branch / Call |
| city | TEXT | txn city (missing back-filled from home city) |
| is_campaign_transaction | INTEGER | 1 if attributed to a campaign |
| discount_amount | REAL | discount applied (0 if non-campaign) |

## campaign_interactions
| column | type | description |
|---|---|---|
| interaction_id | TEXT (PK) | unique interaction |
| customer_id | TEXT (FK) | customer |
| campaign_id | TEXT (FK) | campaign |
| interaction_date | TEXT | within the campaign window |
| channel | TEXT | delivery channel |
| impression | INTEGER | 1 if shown |
| click | INTEGER | 1 if clicked (≤ impression) |
| engaged | INTEGER | 1 if engaged (≤ click) |
| redeemed | INTEGER | 1 if redeemed (≤ engaged) |

## rfm_segments (derived)
| column | type | description |
|---|---|---|
| customer_id | TEXT (PK/FK) | customer |
| recency_days | INTEGER | days since last transaction (as of window end) |
| frequency | INTEGER | number of transactions |
| monetary | REAL | total spend |
| r_score / f_score / m_score | INTEGER | 1–4 quartile scores |
| rfm_segment | TEXT | High Value / Regular / Low Engagement / At Risk |
