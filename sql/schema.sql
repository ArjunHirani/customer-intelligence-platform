-- Customer Intelligence Platform - Database Schema

CREATE TABLE IF NOT EXISTS customers (
    customer_id     VARCHAR(20) PRIMARY KEY,
    country         VARCHAR(60),
    first_purchase  DATE,
    last_purchase   DATE,
    total_orders    INTEGER DEFAULT 0,
    total_revenue   NUMERIC(10,2) DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id  SERIAL PRIMARY KEY,
    customer_id     VARCHAR(20) REFERENCES customers(customer_id),
    invoice_no      VARCHAR(20),
    stock_code      VARCHAR(20),
    description     TEXT,
    quantity        INTEGER,
    unit_price      NUMERIC(8,2),
    total_price     NUMERIC(10,2),
    invoice_date    TIMESTAMPTZ,
    country         VARCHAR(60),
    is_cancelled    BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS events (
    event_id        SERIAL PRIMARY KEY,
    customer_id     VARCHAR(20),
    event_type      VARCHAR(40),
    product_id      VARCHAR(20),
    session_id      VARCHAR(40),
    event_timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB
);

CREATE TABLE IF NOT EXISTS customer_features (
    customer_id       VARCHAR(20) PRIMARY KEY REFERENCES customers(customer_id),
    recency_days      INTEGER,
    frequency         INTEGER,
    monetary          NUMERIC(10,2),
    avg_order_value   NUMERIC(8,2),
    return_rate       NUMERIC(5,4),
    product_diversity INTEGER,
    churn_score       NUMERIC(5,4),
    clv_12m           NUMERIC(10,2),
    rfm_segment       VARCHAR(30),
    computed_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        SERIAL PRIMARY KEY,
    alert_type      VARCHAR(60),
    segment_name    VARCHAR(40),
    description     TEXT,
    severity        VARCHAR(10),
    metric_name     VARCHAR(60),
    metric_value    NUMERIC(12,4),
    baseline_value  NUMERIC(12,4),
    deviation_pct   NUMERIC(6,2),
    is_resolved     BOOLEAN DEFAULT FALSE,
    detected_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS segment_history (
    snapshot_id     SERIAL PRIMARY KEY,
    segment_name    VARCHAR(40),
    customer_count  INTEGER,
    total_revenue   NUMERIC(12,2),
    avg_clv         NUMERIC(10,2),
    avg_churn_score NUMERIC(5,4),
    snapshot_date   DATE DEFAULT CURRENT_DATE
);

CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(invoice_date);
CREATE INDEX IF NOT EXISTS idx_events_customer ON events(customer_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_segment_history_date ON segment_history(snapshot_date);
