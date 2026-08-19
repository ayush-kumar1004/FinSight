-- =====================================================================
-- FinSight — Analytics Queries (SQLite)
-- 18 business questions. Each block states the question it answers.
-- Techniques used across the file: JOIN, LEFT JOIN, GROUP BY, HAVING,
-- CASE WHEN, CTEs, subqueries, window functions (ROW_NUMBER, RANK,
-- DENSE_RANK, LAG), and date functions.
-- Revenue convention: SUM(transaction_amount) over valid (>=0) transactions.
-- =====================================================================


-- Q1 -----------------------------------------------------------------
-- Business question: What is our total revenue, transaction count and
-- average transaction value overall?
SELECT
    COUNT(*)                         AS total_transactions,
    ROUND(SUM(transaction_amount),2) AS total_revenue,
    ROUND(AVG(transaction_amount),2) AS avg_transaction_value
FROM transactions;


-- Q2 -----------------------------------------------------------------
-- Business question: How has revenue trended month by month?
SELECT
    strftime('%Y-%m', transaction_date) AS month,
    COUNT(*)                            AS transactions,
    ROUND(SUM(transaction_amount),2)    AS revenue
FROM transactions
GROUP BY month
ORDER BY month;


-- Q3 -----------------------------------------------------------------
-- Business question: Which spending categories generate the most revenue?
SELECT
    m.category,
    COUNT(*)                           AS transactions,
    ROUND(SUM(t.transaction_amount),2) AS revenue
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
GROUP BY m.category
ORDER BY revenue DESC;


-- Q4 -----------------------------------------------------------------
-- Business question: Who are our top 10 merchants by revenue?
SELECT
    m.merchant_id,
    m.merchant_name,
    m.category,
    ROUND(SUM(t.transaction_amount),2) AS revenue,
    COUNT(*)                           AS transactions
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
GROUP BY m.merchant_id, m.merchant_name, m.category
ORDER BY revenue DESC
LIMIT 10;


-- Q5 -----------------------------------------------------------------
-- Business question: What are the top 3 merchants within each category?
-- (window function ranking partitioned by category)
WITH merchant_rev AS (
    SELECT
        m.category,
        m.merchant_name,
        SUM(t.transaction_amount) AS revenue
    FROM transactions t
    JOIN merchants m ON m.merchant_id = t.merchant_id
    GROUP BY m.category, m.merchant_name
)
SELECT category, merchant_name, ROUND(revenue,2) AS revenue, rnk
FROM (
    SELECT
        category, merchant_name, revenue,
        ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC) AS rnk
    FROM merchant_rev
)
WHERE rnk <= 3
ORDER BY category, rnk;


-- Q6 -----------------------------------------------------------------
-- Business question: Who are our highest-value customers, and how do they
-- rank against everyone else? (RANK window function)
SELECT
    customer_id,
    ROUND(SUM(transaction_amount),2) AS lifetime_spend,
    COUNT(*)                         AS transactions,
    RANK() OVER (ORDER BY SUM(transaction_amount) DESC) AS spend_rank
FROM transactions
GROUP BY customer_id
ORDER BY spend_rank
LIMIT 15;


-- Q7 -----------------------------------------------------------------
-- Business question: How does revenue and average spend differ across
-- income bands? (validates behavioural relationship B1)
SELECT
    c.income_band,
    COUNT(DISTINCT c.customer_id)      AS customers,
    COUNT(t.transaction_id)            AS transactions,
    ROUND(SUM(t.transaction_amount),2) AS revenue,
    ROUND(AVG(t.transaction_amount),2) AS avg_txn_value
FROM customers c
LEFT JOIN transactions t ON t.customer_id = c.customer_id
GROUP BY c.income_band
ORDER BY avg_txn_value DESC;


-- Q8 -----------------------------------------------------------------
-- Business question: Which campaigns drove the most campaign revenue and
-- how much discount did they cost? (LEFT JOIN: include campaigns with 0 txns)
SELECT
    cp.campaign_id,
    cp.campaign_name,
    cp.campaign_category,
    COUNT(t.transaction_id)                     AS campaign_transactions,
    ROUND(COALESCE(SUM(t.transaction_amount),0),2) AS campaign_revenue,
    ROUND(COALESCE(SUM(t.discount_amount),0),2)    AS discount_given
FROM campaigns cp
LEFT JOIN transactions t
       ON t.campaign_id = cp.campaign_id
GROUP BY cp.campaign_id, cp.campaign_name, cp.campaign_category
ORDER BY campaign_revenue DESC;


-- Q9 -----------------------------------------------------------------
-- Business question: What is each campaign's funnel — CTR, and redemption
-- rate among engaged users? (division-by-zero guarded with CASE WHEN)
SELECT
    ci.campaign_id,
    SUM(ci.impression) AS impressions,
    SUM(ci.click)      AS clicks,
    SUM(ci.engaged)    AS engaged,
    SUM(ci.redeemed)   AS redeemed,
    CASE WHEN SUM(ci.impression) = 0 THEN NULL
         ELSE ROUND(1.0 * SUM(ci.click) / SUM(ci.impression), 4) END AS ctr,
    CASE WHEN SUM(ci.engaged) = 0 THEN NULL
         ELSE ROUND(1.0 * SUM(ci.redeemed) / SUM(ci.engaged), 4) END AS redemption_rate
FROM campaign_interactions ci
GROUP BY ci.campaign_id
ORDER BY redemption_rate DESC;


-- Q10 ----------------------------------------------------------------
-- Business question: Which campaigns have strong redemption AND meaningful
-- volume (at least 50 engaged users)? (HAVING on an aggregate)
SELECT
    campaign_id,
    SUM(engaged)  AS engaged,
    SUM(redeemed) AS redeemed,
    ROUND(1.0 * SUM(redeemed) / SUM(engaged), 4) AS redemption_rate
FROM campaign_interactions
GROUP BY campaign_id
HAVING SUM(engaged) >= 50 AND redemption_rate >= 0.5
ORDER BY redemption_rate DESC;


-- Q11 ----------------------------------------------------------------
-- Business question: How does campaign redemption differ by delivery channel?
SELECT
    channel,
    SUM(impression) AS impressions,
    SUM(click)      AS clicks,
    SUM(redeemed)   AS redeemed,
    ROUND(1.0 * SUM(click)   / NULLIF(SUM(impression),0), 4) AS ctr,
    ROUND(1.0 * SUM(redeemed)/ NULLIF(SUM(engaged),0),   4) AS redemption_rate
FROM campaign_interactions
GROUP BY channel
ORDER BY redemption_rate DESC;


-- Q12 ----------------------------------------------------------------
-- Business question: What is the month-over-month revenue change and % growth?
-- (LAG window function over the monthly series)
WITH monthly AS (
    SELECT strftime('%Y-%m', transaction_date) AS month,
           SUM(transaction_amount)             AS revenue
    FROM transactions
    GROUP BY month
)
SELECT
    month,
    ROUND(revenue,2)                                   AS revenue,
    ROUND(LAG(revenue) OVER (ORDER BY month),2)        AS prev_month_revenue,
    ROUND(revenue - LAG(revenue) OVER (ORDER BY month),2) AS mom_change,
    CASE WHEN LAG(revenue) OVER (ORDER BY month) IS NULL THEN NULL
         ELSE ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                     / LAG(revenue) OVER (ORDER BY month), 2) END AS mom_growth_pct
FROM monthly
ORDER BY month;


-- Q13 ----------------------------------------------------------------
-- Business question: Which campaigns show a declining redemption rate versus
-- their own previous active month? (LAG per campaign over months)
WITH camp_month AS (
    SELECT
        campaign_id,
        strftime('%Y-%m', interaction_date) AS month,
        SUM(redeemed) AS redeemed,
        SUM(engaged)  AS engaged
    FROM campaign_interactions
    GROUP BY campaign_id, month
),
rates AS (
    SELECT
        campaign_id, month,
        1.0 * redeemed / NULLIF(engaged,0) AS redemption_rate
    FROM camp_month
    WHERE engaged > 0
)
SELECT
    campaign_id, month,
    ROUND(redemption_rate,4) AS redemption_rate,
    ROUND(LAG(redemption_rate) OVER (PARTITION BY campaign_id ORDER BY month),4) AS prev_rate,
    ROUND(redemption_rate - LAG(redemption_rate) OVER (PARTITION BY campaign_id ORDER BY month),4) AS change
FROM rates
ORDER BY change ASC
LIMIT 15;


-- Q14 ----------------------------------------------------------------
-- Business question: How much revenue do campaign vs non-campaign
-- transactions represent? (CASE WHEN bucketing)
SELECT
    CASE WHEN campaign_id IS NULL THEN 'Non-campaign' ELSE 'Campaign' END AS txn_type,
    COUNT(*)                           AS transactions,
    ROUND(SUM(transaction_amount),2)   AS revenue,
    ROUND(AVG(transaction_amount),2)   AS avg_value
FROM transactions
GROUP BY txn_type;


-- Q15 ----------------------------------------------------------------
-- Business question: Which merchants earn the most from campaigns and what
-- share of their revenue is campaign-driven?
SELECT
    m.merchant_id,
    m.merchant_name,
    ROUND(SUM(t.transaction_amount),2) AS total_revenue,
    ROUND(SUM(CASE WHEN t.campaign_id IS NOT NULL THEN t.transaction_amount ELSE 0 END),2) AS campaign_revenue,
    ROUND(100.0 * SUM(CASE WHEN t.campaign_id IS NOT NULL THEN t.transaction_amount ELSE 0 END)
                / SUM(t.transaction_amount), 1) AS campaign_share_pct
FROM transactions t
JOIN merchants m ON m.merchant_id = t.merchant_id
GROUP BY m.merchant_id, m.merchant_name
HAVING total_revenue > 0
ORDER BY campaign_revenue DESC
LIMIT 10;


-- Q16 ----------------------------------------------------------------
-- Business question: How many customers are repeat customers (>1 txn) vs
-- one-time, and what is the repeat rate?
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS txns
    FROM transactions
    GROUP BY customer_id
)
SELECT
    SUM(CASE WHEN txns > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    SUM(CASE WHEN txns = 1 THEN 1 ELSE 0 END) AS one_time_customers,
    ROUND(100.0 * SUM(CASE WHEN txns > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS repeat_rate_pct
FROM per_customer;


-- Q17 ----------------------------------------------------------------
-- Business question: Once RFM segments exist, what is revenue and average
-- customer value per segment? (LEFT JOIN so unsegmented customers still show)
SELECT
    COALESCE(r.rfm_segment, 'Unsegmented')      AS rfm_segment,
    COUNT(DISTINCT c.customer_id)               AS customers,
    ROUND(SUM(t.transaction_amount),2)          AS revenue,
    ROUND(SUM(t.transaction_amount)
          / COUNT(DISTINCT c.customer_id), 2)   AS avg_customer_value
FROM customers c
LEFT JOIN rfm_segments r ON r.customer_id = c.customer_id
LEFT JOIN transactions t ON t.customer_id = c.customer_id
GROUP BY COALESCE(r.rfm_segment, 'Unsegmented')
ORDER BY revenue DESC;


-- Q18 ----------------------------------------------------------------
-- Business question: Ranking the categories by revenue with a dense rank, so
-- we can see the category league table including ties. (DENSE_RANK)
SELECT
    category,
    ROUND(revenue,2) AS revenue,
    DENSE_RANK() OVER (ORDER BY revenue DESC) AS revenue_dense_rank
FROM (
    SELECT m.category, SUM(t.transaction_amount) AS revenue
    FROM transactions t
    JOIN merchants m ON m.merchant_id = t.merchant_id
    GROUP BY m.category
)
ORDER BY revenue_dense_rank;
