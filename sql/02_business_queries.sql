-- =====================================================================
-- Banking & Insurance Risk Analytics — business questions in SQL
-- Written in standard SQL: runs on PostgreSQL (and SQLite, used for automated testing).
-- Each query starts with "-- Q<n>:" ; results are saved in outputs/sql_results/.
-- =====================================================================


-- Q1: Which customer group (occupation) has the highest loan default rate?
SELECT c.job,
       COUNT(*)                                             AS loans,
       SUM(l.is_default)                                    AS defaults,
       ROUND(CAST(100.0 * AVG(l.is_default) AS NUMERIC), 2) AS default_rate_pct
FROM loans l
JOIN customers c ON c.customer_id = l.customer_id
GROUP BY c.job
ORDER BY default_rate_pct DESC;


-- Q2: Default rate and money lost by credit-score band
SELECT CASE WHEN credit_score < 580 THEN '1. <580'
            WHEN credit_score < 620 THEN '2. 580-619'
            WHEN credit_score < 660 THEN '3. 620-659'
            WHEN credit_score < 700 THEN '4. 660-699'
            WHEN credit_score < 740 THEN '5. 700-739'
            ELSE '6. 740+' END                              AS credit_band,
       COUNT(*)                                             AS loans,
       ROUND(CAST(100.0 * AVG(is_default) AS NUMERIC), 2)   AS default_rate_pct,
       SUM(CASE WHEN is_default = 1 THEN loan_amount ELSE 0 END) AS defaulted_amount
FROM loans
GROUP BY 1
ORDER BY 1;


-- Q3: Default rate by loan purpose and term
SELECT purpose,
       term_months,
       COUNT(*)                                           AS loans,
       ROUND(CAST(100.0 * AVG(is_default) AS NUMERIC), 2) AS default_rate_pct,
       ROUND(CAST(AVG(interest_rate) AS NUMERIC), 2)      AS avg_interest_rate
FROM loans
GROUP BY purpose, term_months
ORDER BY default_rate_pct DESC;


-- Q4: Riskiest customer groups — occupation x age band (min. 100 loans)
SELECT c.job, c.age_band,
       COUNT(*)                                             AS loans,
       ROUND(CAST(100.0 * AVG(l.is_default) AS NUMERIC), 2) AS default_rate_pct,
       ROUND(CAST(AVG(l.is_default) / (SELECT AVG(is_default) FROM loans) AS NUMERIC), 2) AS lift_vs_avg
FROM loans l
JOIN customers c ON c.customer_id = l.customer_id
GROUP BY c.job, c.age_band
HAVING COUNT(*) >= 100
ORDER BY default_rate_pct DESC
LIMIT 10;


-- Q5: Which customer segment is most risky? Rule-based risk tiers (credit score + DTI + delinquency)
WITH scored AS (
    SELECT l.*,
           (CASE WHEN credit_score < 620 THEN 3 WHEN credit_score < 680 THEN 2
                 WHEN credit_score < 740 THEN 1 ELSE 0 END)
         + (CASE WHEN dti > 35 THEN 2 WHEN dti > 25 THEN 1 ELSE 0 END)
         + (CASE WHEN times_90dpd > 0 THEN 3 WHEN times_30dpd >= 2 THEN 2
                 WHEN times_30dpd = 1 THEN 1 ELSE 0 END) AS risk_points
    FROM loans l
)
SELECT CASE WHEN risk_points >= 6 THEN '4. Critical'
            WHEN risk_points >= 4 THEN '3. High'
            WHEN risk_points >= 2 THEN '2. Medium'
            ELSE '1. Low' END                               AS risk_tier,
       COUNT(*)                                             AS borrowers,
       SUM(loan_amount)                                     AS exposure,
       ROUND(CAST(100.0 * AVG(is_default) AS NUMERIC), 2)   AS default_rate_pct
FROM scored
GROUP BY 1
ORDER BY 1;


-- Q6: Customer payment behaviour vs default
SELECT CASE WHEN times_90dpd > 0  THEN 'Severe delinquency (90+ DPD)'
            WHEN times_30dpd >= 3 THEN 'Chronic late payer'
            WHEN times_30dpd >= 1 THEN 'Occasional late'
            ELSE 'Always on time' END                     AS payment_behavior,
       COUNT(*)                                           AS borrowers,
       ROUND(CAST(100.0 * AVG(is_default) AS NUMERIC), 2) AS default_rate_pct
FROM loans
GROUP BY 1
ORDER BY default_rate_pct DESC;


-- Q7: Which transactions are abnormal? Amount more than 3 std above the account's own average
WITH acct AS (
    SELECT account_id,
           AVG(amount)                                         AS avg_amt,
           SQRT(AVG(amount * amount) - AVG(amount) * AVG(amount)) AS std_amt
    FROM transactions
    GROUP BY account_id
)
SELECT t.transaction_id, t.account_id, t.transaction_date, t.amount,
       ROUND(CAST(a.avg_amt AS NUMERIC), 2)                         AS account_avg,
       ROUND(CAST((t.amount - a.avg_amt) / a.std_amt AS NUMERIC), 2) AS z_score,
       t.channel, t.login_attempts
FROM transactions t
JOIN acct a ON a.account_id = t.account_id
WHERE (t.amount - a.avg_amt) / a.std_amt > 3
ORDER BY z_score DESC
LIMIT 25;


-- Q8: Fraud indicator — repeated login attempts before a transaction
SELECT login_attempts,
       COUNT(*)                                       AS transactions,
       ROUND(CAST(AVG(amount) AS NUMERIC), 2)         AS avg_amount,
       ROUND(CAST(AVG(amount_to_balance) AS NUMERIC), 3) AS avg_share_of_balance
FROM transactions
GROUP BY login_attempts
ORDER BY login_attempts;


-- Q9: Fraud indicator — devices used by unusually many accounts (possible account takeover / mule)
SELECT device_id,
       COUNT(DISTINCT account_id) AS accounts_using_device,
       COUNT(*)                   AS transactions,
       SUM(amount)                AS total_amount
FROM transactions
GROUP BY device_id
HAVING COUNT(DISTINCT account_id) >= 8
ORDER BY accounts_using_device DESC, total_amount DESC
LIMIT 15;


-- Q10: Fraud indicator — transactions that drain 80%+ of the balance, by channel
SELECT channel, transaction_type,
       COUNT(*)                                              AS drain_transactions,
       ROUND(CAST(AVG(amount) AS NUMERIC), 2)                AS avg_amount,
       ROUND(CAST(100.0 * COUNT(*) / (SELECT COUNT(*) FROM transactions) AS NUMERIC), 2) AS pct_of_all_tx
FROM transactions
WHERE amount_to_balance > 0.8
GROUP BY channel, transaction_type
ORDER BY drain_transactions DESC;


-- Q11: Insurance — claims volume, cost and fraud rate by policy type
SELECT policy_type,
       COUNT(*)                                                  AS claims,
       ROUND(CAST(SUM(claim_amount) AS NUMERIC), 0)              AS total_claimed,
       ROUND(CAST(AVG(claim_amount) AS NUMERIC), 0)              AS avg_claim,
       ROUND(CAST(AVG(days_to_report) AS NUMERIC), 1)            AS avg_days_to_report,
       ROUND(CAST(100.0 * AVG(is_fraud_confirmed) AS NUMERIC), 2) AS fraud_rate_pct
FROM insurance_claims
GROUP BY policy_type
ORDER BY claims DESC;


-- Q12: Which claim patterns are abnormal? Fraud rate by number of red flags
WITH typical AS (
    SELECT policy_type, AVG(claim_amount) AS avg_amt FROM insurance_claims GROUP BY policy_type
), flagged AS (
    SELECT c.*,
           (CASE WHEN policy_tenure_months < 6 THEN 1 ELSE 0 END)
         + (CASE WHEN claim_amount > 2 * t.avg_amt THEN 1 ELSE 0 END)
         + (CASE WHEN days_to_report > 20 THEN 1 ELSE 0 END)
         + (CASE WHEN prior_claims >= 2 THEN 1 ELSE 0 END)
         + (CASE WHEN police_report = 0 AND c.policy_type IN ('Auto', 'Home') THEN 1 ELSE 0 END)
         + (CASE WHEN witnesses = 0 THEN 1 ELSE 0 END)
         + (CASE WHEN incident_type = 'Theft' THEN 1 ELSE 0 END) AS red_flags
    FROM insurance_claims c
    JOIN typical t ON t.policy_type = c.policy_type
)
SELECT red_flags,
       COUNT(*)                                                  AS claims,
       ROUND(CAST(100.0 * AVG(is_fraud_confirmed) AS NUMERIC), 2) AS fraud_rate_pct,
       ROUND(CAST(SUM(claim_amount) AS NUMERIC), 0)              AS amount_at_risk
FROM flagged
GROUP BY red_flags
ORDER BY red_flags;


-- Q13: Claims to send to the investigation team (3+ red flags, not yet paid)
WITH typical AS (
    SELECT policy_type, AVG(claim_amount) AS avg_amt FROM insurance_claims GROUP BY policy_type
), flagged AS (
    SELECT c.claim_id, c.customer_id, c.policy_type, c.incident_type, c.claim_amount, c.claim_status,
           (CASE WHEN policy_tenure_months < 6 THEN 1 ELSE 0 END)
         + (CASE WHEN claim_amount > 2 * t.avg_amt THEN 1 ELSE 0 END)
         + (CASE WHEN days_to_report > 20 THEN 1 ELSE 0 END)
         + (CASE WHEN prior_claims >= 2 THEN 1 ELSE 0 END)
         + (CASE WHEN police_report = 0 AND c.policy_type IN ('Auto', 'Home') THEN 1 ELSE 0 END)
         + (CASE WHEN witnesses = 0 THEN 1 ELSE 0 END)
         + (CASE WHEN incident_type = 'Theft' THEN 1 ELSE 0 END) AS red_flags
    FROM insurance_claims c
    JOIN typical t ON t.policy_type = c.policy_type
)
SELECT *
FROM flagged
WHERE red_flags >= 3 AND claim_status <> 'Paid'
ORDER BY red_flags DESC, claim_amount DESC
LIMIT 25;


-- Q14: Cross-product risk — customers who both defaulted on a loan AND have a suspicious claim history
WITH bad_loans AS (
    SELECT customer_id, COUNT(*) AS defaulted_loans, SUM(loan_amount) AS defaulted_amount
    FROM loans WHERE is_default = 1 GROUP BY customer_id
), claim_hist AS (
    SELECT customer_id, COUNT(*) AS claims, SUM(claim_amount) AS claimed_amount,
           MAX(prior_claims) AS max_prior_claims
    FROM insurance_claims GROUP BY customer_id
)
SELECT c.customer_id, c.job, c.age,
       b.defaulted_loans, b.defaulted_amount,
       h.claims, ROUND(CAST(h.claimed_amount AS NUMERIC), 0) AS claimed_amount, h.max_prior_claims
FROM customers c
JOIN bad_loans  b ON b.customer_id = c.customer_id
JOIN claim_hist h ON h.customer_id = c.customer_id
ORDER BY h.max_prior_claims DESC, b.defaulted_amount DESC
LIMIT 15;


-- Q15: Transaction trend by year — volume and abnormal activity
SELECT year,
       COUNT(*)                                                       AS transactions,
       ROUND(CAST(SUM(amount) AS NUMERIC), 0)                         AS total_volume,
       SUM(CASE WHEN login_attempts >= 3 THEN 1 ELSE 0 END)           AS multi_login_tx,
       SUM(CASE WHEN amount_to_balance > 0.8 THEN 1 ELSE 0 END)       AS balance_drain_tx
FROM transactions
GROUP BY year
ORDER BY year;
