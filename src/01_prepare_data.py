"""
Step 1 - Data preparation
=========================
Builds the five analysis tables used by the whole project.

REAL data (data/raw):
  * bank_transactions.csv  - 50,000 card/account transactions, 495 accounts (Kaggle)
  * bank_customers.csv     - 41,188 bank customers (UCI Bank Marketing dataset)

SYNTHETIC data (generated here, clearly labelled):
  * loans.csv              - loan book for a sample of the real customers
  * insurance_claims.csv   - insurance claims for a sample of the real customers

Why synthetic? Neither source file contains loan repayment outcomes or insurance
claims, so they are simulated from documented, realistic rules (see docs/DATA_DICTIONARY.md).
A fixed random seed makes every run identical.

Run:  python src/01_prepare_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)


# ---------------------------------------------------------------- transactions
def prepare_transactions() -> pd.DataFrame:
    tx = pd.read_csv(RAW / "bank_transactions.csv")
    tx.columns = [
        "transaction_id", "account_id", "amount", "transaction_date", "transaction_type",
        "location", "device_id", "ip_address", "merchant_id", "channel", "customer_age",
        "customer_occupation", "duration_sec", "login_attempts", "account_balance",
    ]
    # Dates come in two formats ("4/11/2023 16:29" and "9/15/2024"): parse both, keep the date only.
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"], format="mixed").dt.normalize()
    tx = tx.drop_duplicates("transaction_id")
    for c in ["transaction_type", "channel", "customer_occupation", "location"]:
        tx[c] = tx[c].str.strip()
    tx["year"] = tx["transaction_date"].dt.year
    tx["month"] = tx["transaction_date"].dt.to_period("M").astype(str)
    tx["amount_to_balance"] = (tx["amount"] / tx["account_balance"]).round(4)
    tx["age_band"] = pd.cut(tx["customer_age"], [17, 25, 35, 50, 65, 120],
                            labels=["18-25", "26-35", "36-50", "51-65", "65+"]).astype(str)
    return tx


# ---------------------------------------------------------------- customers
def prepare_customers() -> pd.DataFrame:
    c = pd.read_csv(RAW / "bank_customers.csv", sep=";")
    c = c.drop_duplicates().reset_index(drop=True)
    c.insert(0, "customer_id", [f"CU{i:05d}" for i in range(1, len(c) + 1)])
    c = c.rename(columns={
        "default": "credit_default_flag", "housing": "has_housing_loan", "loan": "has_personal_loan",
        "duration": "last_call_sec", "y": "subscribed_term_deposit",
        "emp.var.rate": "emp_var_rate", "cons.price.idx": "cons_price_idx",
        "cons.conf.idx": "cons_conf_idx", "nr.employed": "nr_employed",
    })
    c["job"] = c["job"].str.replace(".", "", regex=False)
    c["education"] = c["education"].str.replace(".", " ", regex=False).str.title()
    c["age_band"] = pd.cut(c["age"], [17, 25, 35, 50, 65, 120],
                           labels=["18-25", "26-35", "36-50", "51-65", "65+"]).astype(str)
    keep = ["customer_id", "age", "age_band", "job", "marital", "education", "credit_default_flag",
            "has_housing_loan", "has_personal_loan", "contact", "campaign", "previous", "poutcome",
            "subscribed_term_deposit", "euribor3m"]
    return c[keep]


# ---------------------------------------------------------------- synthetic loans
JOB_INCOME = {  # median annual income (USD) by job - realistic US-style levels
    "admin": 52000, "blue-collar": 43000, "technician": 58000, "services": 38000,
    "management": 92000, "retired": 34000, "entrepreneur": 85000, "self-employed": 64000,
    "housemaid": 29000, "unemployed": 18000, "student": 16000, "unknown": 40000,
}
JOB_RISK = {  # extra default log-odds by employment stability
    "unemployed": 0.9, "student": 0.6, "housemaid": 0.35, "services": 0.25, "blue-collar": 0.2,
    "entrepreneur": 0.3, "self-employed": 0.25, "unknown": 0.3, "admin": 0.0,
    "technician": -0.05, "retired": -0.1, "management": -0.3,
}


def make_loans(customers: pd.DataFrame, n: int = 15000) -> pd.DataFrame:
    b = customers.sample(n, random_state=7).reset_index(drop=True)
    income = np.array([JOB_INCOME[j] for j in b["job"]]) * rng.lognormal(0, 0.35, n)
    income *= np.where(b["education"].str.contains("University"), 1.18, 1.0)
    income = income.round(-2).clip(9000, 400000)

    credit = rng.normal(690, 62, n) - np.where(b["credit_default_flag"].eq("unknown"), 38, 0)
    credit -= np.where(b["job"].isin(["unemployed", "student"]), 35, 0)
    credit = credit.clip(480, 850).round()

    purpose = rng.choice(["Debt Consolidation", "Home Improvement", "Auto", "Personal",
                          "Education", "Small Business", "Medical"], n,
                         p=[.33, .15, .17, .16, .07, .06, .06])
    amount = (income * rng.uniform(.08, .45, n)).round(-2).clip(1000, 60000)
    term = rng.choice([36, 60], n, p=[.68, .32])
    grade = pd.cut(credit, [0, 600, 650, 700, 750, 900], labels=list("EDCBA")).astype(str)
    base_rate = {"A": 7.0, "B": 10.5, "C": 14.0, "D": 18.5, "E": 24.0}
    rate = np.array([base_rate[g] for g in grade]) + rng.normal(0, 1.2, n) + (term == 60) * 1.5
    rate = rate.clip(5.5, 29.9)
    monthly = amount * (rate / 1200) / (1 - (1 + rate / 1200) ** -term)
    dti = ((monthly * 12) / income * 100 + rng.uniform(5, 25, n)).round(1).clip(1, 65)

    # default probability: logistic model with realistic drivers (~11% overall)
    z = (-2.85 - 0.012 * (credit - 690) + 0.035 * (dti - 20) + (term == 60) * 0.35
         + np.array([JOB_RISK[j] for j in b["job"]])
         + np.where(b["age"] < 26, 0.3, 0) + np.where(b["has_personal_loan"].eq("yes"), 0.25, 0)
         + np.where(purpose == "Small Business", 0.45, 0) + np.where(purpose == "Medical", 0.3, 0)
         + rng.normal(0, 0.3, n))
    p_default = 1 / (1 + np.exp(-z))
    defaulted = rng.random(n) < p_default

    issue = pd.to_datetime("2020-01-01") + pd.to_timedelta(rng.integers(0, 6 * 365 - 200, n), "D")
    # payment behaviour: defaulters miss many payments, good borrowers rarely do
    late_30 = np.where(defaulted, rng.poisson(2.2, n), rng.poisson(0.45, n))
    late_90 = np.where(defaulted, rng.poisson(0.9, n), rng.poisson(0.03, n))
    status = np.where(defaulted, rng.choice(["Charged Off", "Default"], n, p=[.7, .3]),
                      np.where(late_30 > 0, "Current - Late History", "Current"))
    paid_off = (~defaulted) & (issue < pd.Timestamp("2022-06-01")) & (rng.random(n) < .55)
    status = np.where(paid_off, "Fully Paid", status)

    return pd.DataFrame({
        "loan_id": [f"LN{i:06d}" for i in range(1, n + 1)],
        "customer_id": b["customer_id"], "issue_date": issue.normalize(),
        "loan_amount": amount, "term_months": term, "interest_rate": rate.round(2),
        "grade": grade, "purpose": purpose, "annual_income": income, "credit_score": credit.astype(int),
        "dti": dti, "monthly_payment": monthly.round(2), "times_30dpd": late_30,
        "times_90dpd": late_90, "loan_status": status, "is_default": defaulted.astype(int),
    })


# ---------------------------------------------------------------- synthetic claims
def make_claims(customers: pd.DataFrame, n: int = 9000) -> pd.DataFrame:
    h = customers.sample(n, random_state=11).reset_index(drop=True)
    ptype = rng.choice(["Auto", "Home", "Health", "Life", "Travel"], n, p=[.42, .22, .24, .05, .07])
    typical = {"Auto": 4200, "Home": 9800, "Health": 3100, "Life": 48000, "Travel": 1300}
    premium_base = {"Auto": 1450, "Home": 1300, "Health": 5200, "Life": 900, "Travel": 160}
    claim_amt = np.array([typical[t] for t in ptype]) * rng.lognormal(0, 0.6, n)
    premium = np.array([premium_base[t] for t in ptype]) * rng.uniform(.7, 1.4, n)
    tenure = rng.gamma(2.2, 18, n).round().clip(1, 240).astype(int)
    report_days = rng.gamma(1.3, 4, n).round().astype(int)
    prior = rng.poisson(0.6, n)
    police = np.where(np.isin(ptype, ["Auto", "Home"]), rng.random(n) < .55, False)
    witnesses = rng.poisson(0.8, n)
    incident = rng.choice(["Collision", "Theft", "Fire", "Water Damage", "Illness", "Injury",
                           "Death", "Trip Cancellation", "Vandalism"], n)
    incident = np.select(
        [ptype == "Auto", ptype == "Home", ptype == "Health", ptype == "Life", ptype == "Travel"],
        [rng.choice(["Collision", "Theft", "Vandalism"], n, p=[.7, .18, .12]),
         rng.choice(["Water Damage", "Fire", "Theft", "Storm"], n, p=[.45, .15, .2, .2]),
         rng.choice(["Illness", "Injury", "Surgery"], n, p=[.55, .3, .15]),
         np.full(n, "Death"), rng.choice(["Trip Cancellation", "Lost Baggage", "Medical Abroad"], n)],
        incident)

    # fraud likelihood: classic red flags used by insurance SIU teams
    ratio = claim_amt / np.array([typical[t] for t in ptype])
    z = (-3.6 + 0.9 * (tenure < 6) + 0.55 * (ratio > 2.2) + 0.45 * (report_days > 20)
         + 0.35 * np.minimum(prior, 4) + 0.6 * ((~police) & np.isin(ptype, ["Auto", "Home"]))
         + 0.4 * (witnesses == 0) + 0.5 * (incident == "Theft") + rng.normal(0, .4, n))
    fraud = rng.random(n) < 1 / (1 + np.exp(-z))
    claim_amt = np.where(fraud, claim_amt * rng.uniform(1.1, 1.8, n), claim_amt)
    claim_date = pd.to_datetime("2021-01-01") + pd.to_timedelta(rng.integers(0, 5 * 365, n), "D")
    status = np.where(fraud, rng.choice(["Denied", "Under Investigation", "Paid"], n, p=[.55, .3, .15]),
                      rng.choice(["Paid", "Denied", "Open"], n, p=[.86, .07, .07]))
    return pd.DataFrame({
        "claim_id": [f"CL{i:06d}" for i in range(1, n + 1)], "customer_id": h["customer_id"],
        "policy_type": ptype, "incident_type": incident, "claim_date": claim_date.normalize(),
        "claim_amount": claim_amt.round(2), "annual_premium": premium.round(2),
        "policy_tenure_months": tenure, "days_to_report": report_days, "prior_claims": prior,
        "police_report": police.astype(int), "witnesses": witnesses,
        "claim_status": status, "is_fraud_confirmed": fraud.astype(int),
    })


if __name__ == "__main__":
    tx = prepare_transactions()
    cu = prepare_customers()
    loans = make_loans(cu)
    claims = make_claims(cu)
    for name, df in [("transactions", tx), ("customers", cu), ("loans", loans), ("insurance_claims", claims)]:
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:18s} {len(df):>7,} rows  {df.shape[1]} cols")
    print(f"loan default rate   {loans.is_default.mean():.1%}")
    print(f"claim fraud rate    {claims.is_fraud_confirmed.mean():.1%}")
