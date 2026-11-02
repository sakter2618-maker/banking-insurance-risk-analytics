-- =====================================================================
-- Banking & Insurance Risk Analytics — database schema (PostgreSQL)
-- =====================================================================
-- How to load (pgAdmin Query Tool or psql):
--   1. CREATE DATABASE risk_analytics;  then connect to it
--   2. Run this whole file to create the 4 tables
--   3. Import the CSVs from data/processed/ (pgAdmin: right-click table -> Import/Export,
--      Format = csv, Header = ON)  or in psql:
--        \copy customers        FROM 'data/processed/customers.csv'        CSV HEADER
--        \copy loans            FROM 'data/processed/loans.csv'            CSV HEADER
--        \copy insurance_claims FROM 'data/processed/insurance_claims.csv' CSV HEADER
--        \copy transactions     FROM 'data/processed/transactions.csv'     CSV HEADER
-- =====================================================================

DROP TABLE IF EXISTS insurance_claims, loans, transactions, customers CASCADE;

-- Real data: UCI Bank Marketing customers
CREATE TABLE customers (
    customer_id             VARCHAR(10) PRIMARY KEY,
    age                     INT,
    age_band                VARCHAR(10),
    job                     VARCHAR(20),
    marital                 VARCHAR(12),
    education               VARCHAR(30),
    credit_default_flag     VARCHAR(10),   -- yes / no / unknown
    has_housing_loan        VARCHAR(10),
    has_personal_loan       VARCHAR(10),
    contact                 VARCHAR(12),
    campaign                INT,
    previous                INT,
    poutcome                VARCHAR(15),
    subscribed_term_deposit VARCHAR(5),
    euribor3m               NUMERIC(6,3)
);

-- Synthetic loan book (linked to real customers)
CREATE TABLE loans (
    loan_id          VARCHAR(10) PRIMARY KEY,
    customer_id      VARCHAR(10) REFERENCES customers(customer_id),
    issue_date       DATE,
    loan_amount      NUMERIC(12,2),
    term_months      INT,
    interest_rate    NUMERIC(5,2),
    grade            CHAR(1),
    purpose          VARCHAR(30),
    annual_income    NUMERIC(12,2),
    credit_score     INT,
    dti              NUMERIC(5,1),
    monthly_payment  NUMERIC(10,2),
    times_30dpd      INT,               -- times 30+ days past due
    times_90dpd      INT,               -- times 90+ days past due
    loan_status      VARCHAR(30),
    is_default       INT                -- 1 = defaulted / charged off
);

-- Synthetic insurance claims (linked to real customers)
CREATE TABLE insurance_claims (
    claim_id              VARCHAR(10) PRIMARY KEY,
    customer_id           VARCHAR(10) REFERENCES customers(customer_id),
    policy_type           VARCHAR(10),
    incident_type         VARCHAR(25),
    claim_date            DATE,
    claim_amount          NUMERIC(12,2),
    annual_premium        NUMERIC(10,2),
    policy_tenure_months  INT,
    days_to_report        INT,
    prior_claims          INT,
    police_report         INT,
    witnesses             INT,
    claim_status          VARCHAR(25),
    is_fraud_confirmed    INT
);

-- Real data: Kaggle bank transactions (separate core-banking system, own account_id)
CREATE TABLE transactions (
    transaction_id       VARCHAR(10) PRIMARY KEY,
    account_id           VARCHAR(10),
    amount               NUMERIC(12,2),
    transaction_date     DATE,
    transaction_type     VARCHAR(10),
    location             VARCHAR(30),
    device_id            VARCHAR(10),
    ip_address           VARCHAR(20),
    merchant_id          VARCHAR(10),
    channel              VARCHAR(10),
    customer_age         INT,
    customer_occupation  VARCHAR(20),
    duration_sec         INT,
    login_attempts       INT,
    account_balance      NUMERIC(12,2),
    year                 INT,
    month                VARCHAR(7),
    amount_to_balance    NUMERIC(10,4),
    age_band             VARCHAR(10)
);

CREATE INDEX idx_tx_account ON transactions(account_id);
CREATE INDEX idx_loans_customer ON loans(customer_id);
CREATE INDEX idx_claims_customer ON insurance_claims(customer_id);
