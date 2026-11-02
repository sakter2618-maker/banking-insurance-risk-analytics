# Data Dictionary

## Sources

| Table | Rows | Type | Source |
|---|---:|---|---|
| `transactions` | 50,000 | **Real** | Kaggle — *Bank Transaction Dataset for Fraud Detection* (augmented version), file `bank_transactions_data_2_augmented_clean_2.csv` |
| `customers` | 41,176 | **Real** | UCI Machine Learning Repository — *Bank Marketing* (`bank-additional-full.csv`, Moro et al., 2014); 12 exact duplicate rows removed |
| `loans` | 15,000 | **Synthetic** | Generated in `src/01_prepare_data.py`, borrowers sampled from `customers` |
| `insurance_claims` | 9,000 | **Synthetic** | Generated in `src/01_prepare_data.py`, policyholders sampled from `customers` |

**Why synthetic?** Neither real file contains loan repayment outcomes (the UCI `default` column has only 3 "yes" values out of 41,188) or insurance claims. Rather than drop two of the seven analyses, loans and claims were simulated with transparent rules based on well-known industry risk drivers. Random seed = 42, so every run gives identical data.

## Table relationships

```
customers (customer_id) ──< loans (customer_id)
                        └─< insurance_claims (customer_id)

transactions (account_id)   ← separate core-banking system, cannot be joined to customers
```

## transactions (real)
| Column | Meaning |
|---|---|
| transaction_id | Unique transaction ID |
| account_id | Bank account (495 accounts) |
| amount | Transaction amount, USD |
| transaction_date | Date (two source formats unified; time dropped because 87% of rows had none) |
| transaction_type | Debit / Credit |
| location | US city |
| device_id, ip_address | Device and IP used |
| merchant_id | Merchant |
| channel | ATM / Branch / Online |
| customer_age, customer_occupation | As recorded on the transaction (not consistent within an account — a known artefact of the augmented dataset) |
| duration_sec | Session length in seconds |
| login_attempts | Login attempts before the transaction (1–5) |
| account_balance | Balance after the transaction |
| amount_to_balance | *Derived:* amount ÷ balance |

## customers (real)
| Column | Meaning |
|---|---|
| customer_id | *Derived:* CU00001… |
| age, age_band | Age and band (18-25, 26-35, 36-50, 51-65, 65+) |
| job, marital, education | Demographics |
| credit_default_flag | Has credit in default? yes / no / **unknown** |
| has_housing_loan, has_personal_loan | Existing loans (yes/no/unknown) |
| contact, campaign, previous, poutcome, subscribed_term_deposit | Marketing campaign fields |
| euribor3m | 3-month Euribor rate at contact |

## loans (synthetic) — generation rules
| Column | Rule |
|---|---|
| annual_income | Median income by job × lognormal noise; +18% for university degree |
| credit_score | Normal(690, 62); −38 if credit status unknown; −35 if unemployed/student; clipped 480–850 |
| loan_amount | 8–45% of income, $1K–$60K |
| term_months | 36 (68%) or 60 |
| grade | A–E from credit score bands |
| interest_rate | Base rate by grade + noise + 1.5 pts for 60-month term |
| dti | Debt-to-income %, includes the new monthly payment |
| is_default | Logistic model: lower credit score, higher DTI, 60-month term, unstable employment, age < 26, existing personal loan, small-business/medical purpose all raise default probability. Overall ≈ 12% |
| times_30dpd, times_90dpd | Late payments: defaulters Poisson(2.2) / Poisson(0.9); others Poisson(0.45) / Poisson(0.03) |
| loan_status | Current / Current - Late History / Fully Paid / Charged Off / Default |

## insurance_claims (synthetic) — generation rules
| Column | Rule |
|---|---|
| policy_type | Auto 42%, Health 24%, Home 22%, Travel 7%, Life 5% |
| claim_amount | Typical amount per policy type × lognormal noise; fraudulent claims inflated 10–80% |
| policy_tenure_months, days_to_report, prior_claims, police_report, witnesses | Realistic distributions |
| is_fraud_confirmed | Logistic model on SIU red flags: new policy, unusually large claim, late reporting, many prior claims, no police report, no witnesses, theft. Overall ≈ 6% |
| claim_status | Paid / Denied / Open / Under Investigation |

## Derived outputs
| File | What it is |
|---|---|
| `outputs/scored/borrower_risk_scores.csv` | PD score, risk score (0–100), risk tier, K-Means segment per loan |
| `outputs/scored/suspicious_transactions.csv` | Every suspicious transaction with rules hit, anomaly score and alert level |
| `outputs/scored/claims_for_review.csv` | Claims with 3+ red flags |
| `outputs/scored/account_behavior.csv` | Behaviour profile per account |
| `outputs/tables/*.csv` | Summary tables behind every chart |
| `outputs/sql_results/Q*.csv` | Result of each SQL query |
