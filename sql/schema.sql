-- FinSight — SQLite schema
-- Loaded with PRAGMA foreign_keys = ON. Only cleaned data is inserted, so the
-- database is referentially valid (the dirty rows were removed upstream).

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS rfm_segments;
DROP TABLE IF EXISTS campaign_interactions;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS merchants;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id       TEXT PRIMARY KEY,
    age               INTEGER,
    gender            TEXT,
    city              TEXT,
    state             TEXT,
    income_band       TEXT,
    employment_type   TEXT,
    account_type      TEXT,
    customer_since    TEXT,
    credit_score_band TEXT,
    preferred_channel TEXT
    -- NOTE: intentionally no customer_segment here. Segments are derived by
    -- src/segmentation.py from transaction behaviour and stored in rfm_segments.
);

CREATE TABLE merchants (
    merchant_id   TEXT PRIMARY KEY,
    merchant_name TEXT,
    category      TEXT,
    city          TEXT,
    state         TEXT,
    merchant_size TEXT,
    onboard_date  TEXT
);

CREATE TABLE campaigns (
    campaign_id       TEXT PRIMARY KEY,
    campaign_name     TEXT,
    campaign_category TEXT,
    merchant_id       TEXT,
    start_date        TEXT,
    end_date          TEXT,
    target_segment    TEXT,
    discount_type     TEXT,
    discount_value    REAL,
    campaign_budget   REAL,
    channel           TEXT,
    FOREIGN KEY (merchant_id) REFERENCES merchants (merchant_id)
);

CREATE TABLE transactions (
    transaction_id          TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL,
    merchant_id             TEXT NOT NULL,
    campaign_id             TEXT,              -- NULL = non-campaign transaction
    transaction_date        TEXT NOT NULL,
    transaction_amount      REAL NOT NULL,
    payment_channel         TEXT,
    city                    TEXT,
    is_campaign_transaction INTEGER,
    discount_amount         REAL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants (merchant_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id)
);

CREATE TABLE campaign_interactions (
    interaction_id   TEXT PRIMARY KEY,
    customer_id      TEXT NOT NULL,
    campaign_id      TEXT NOT NULL,
    interaction_date TEXT,
    channel          TEXT,
    impression       INTEGER,
    click            INTEGER,
    engaged          INTEGER,
    redeemed         INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id)
);

-- Derived table, populated by src/segmentation.py (NOT by the generator).
CREATE TABLE rfm_segments (
    customer_id  TEXT PRIMARY KEY,
    recency_days INTEGER,
    frequency    INTEGER,
    monetary     REAL,
    r_score      INTEGER,
    f_score      INTEGER,
    m_score      INTEGER,
    rfm_segment  TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- Indexes for the common joins/filters used by analytics_queries.sql.
CREATE INDEX idx_txn_customer ON transactions (customer_id);
CREATE INDEX idx_txn_merchant ON transactions (merchant_id);
CREATE INDEX idx_txn_campaign ON transactions (campaign_id);
CREATE INDEX idx_txn_date     ON transactions (transaction_date);
CREATE INDEX idx_int_campaign ON campaign_interactions (campaign_id);
CREATE INDEX idx_int_customer ON campaign_interactions (customer_id);
