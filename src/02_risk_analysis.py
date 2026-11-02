"""
Step 2 - Risk analysis
======================
Runs the seven analyses and writes:
  * outputs/tables/*.csv          summary tables (one per question)
  * outputs/scored/*.csv          row-level scores (anomaly flags, risk tiers)
  * reports/figures/*.png         charts used in the Risk Report
  * docs/data.json                aggregated numbers for the web dashboard

Analyses
  1. Loan Default Analysis          (loans + customers)
  2. Customer Risk Segmentation     (K-Means on borrower profile)
  3. Transaction Anomaly Detection  (rules + Isolation Forest)
  4. Insurance Claims Analysis      (claims)
  5. Customer Payment Behavior      (late payments + transaction behaviour)
  6. Risk Category Analysis         (composite risk score -> Low/Medium/High/Critical)
  7. Fraud Indicators               (lift of each red flag, transactions + claims)

Run:  python src/02_risk_analysis.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
TAB, SCO, FIG = ROOT / "outputs" / "tables", ROOT / "outputs" / "scored", ROOT / "reports" / "figures"
for d in (TAB, SCO, FIG, ROOT / "docs"):
    d.mkdir(parents=True, exist_ok=True)

# ---- chart style (minimal) -------------------------------------------------
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9"
TIER_COLORS = {"Low": "#0ca30c", "Medium": "#fab219", "High": "#ec835a", "Critical": "#d03b3b"}
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.edgecolor": "#c3c2b7",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "x",
    "grid.color": GRID, "grid.linewidth": .6, "axes.labelcolor": "#52514e", "xtick.color": MUTED,
    "ytick.color": "#52514e", "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "figure.dpi": 130, "axes.axisbelow": True,
})


def hbar(series: pd.Series, title: str, fname: str, pct=True, color=BLUE, highlight_top=0):
    s = series.sort_values()
    fig, ax = plt.subplots(figsize=(7, max(2.4, .38 * len(s) + 1)))
    colors = [color] * len(s)
    for i in range(1, highlight_top + 1):
        colors[-i] = ORANGE
    ax.barh(s.index.astype(str), s.values, color=colors, height=.62)
    for y, v in enumerate(s.values):
        ax.text(v, y, f"  {v:.1%}" if pct else f"  {v:,.0f}", va="center", fontsize=9, color="#52514e")
    if pct:
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_title(title)
    ax.set_xlim(0, s.max() * 1.18)
    fig.tight_layout()
    fig.savefig(FIG / fname)
    plt.close(fig)


def rate_table(df, by, target):
    t = df.groupby(by, observed=True).agg(count=(target, "size"), events=(target, "sum"),
                                          rate=(target, "mean")).reset_index()
    t["rate"] = t["rate"].round(4)
    return t.sort_values("rate", ascending=False)


def to_records(df):
    return json.loads(df.to_json(orient="records"))


tx = pd.read_csv(P / "transactions.csv", parse_dates=["transaction_date"])
cu = pd.read_csv(P / "customers.csv")
loans = pd.read_csv(P / "loans.csv", parse_dates=["issue_date"])
claims = pd.read_csv(P / "insurance_claims.csv", parse_dates=["claim_date"])
L = loans.merge(cu, on="customer_id", how="left")
dash = {}

# ============================================================ 1. LOAN DEFAULT
L["credit_band"] = pd.cut(L["credit_score"], [0, 580, 620, 660, 700, 740, 900],
                          labels=["<580", "580-619", "620-659", "660-699", "700-739", "740+"])
L["dti_band"] = pd.cut(L["dti"], [0, 15, 20, 25, 30, 35, 100],
                       labels=["<15", "15-20", "20-25", "25-30", "30-35", "35+"])
L["income_band"] = pd.cut(L["annual_income"], [0, 30000, 50000, 75000, 100000, 1e9],
                          labels=["<30K", "30-50K", "50-75K", "75-100K", "100K+"])
default_by = {}
for col in ["grade", "purpose", "job", "age_band", "credit_band", "dti_band", "income_band",
            "term_months", "education", "marital"]:
    t = rate_table(L, col, "is_default")
    t.to_csv(TAB / f"loan_default_by_{col}.csv", index=False)
    default_by[col] = to_records(t)

hbar(L.groupby("job").is_default.mean(), "Loan default rate by occupation", "01_default_by_job.png",
     highlight_top=3)
hbar(L.groupby("credit_band", observed=True).is_default.mean(), "Default rate by credit score band",
     "02_default_by_credit.png")
hbar(L.groupby("purpose").is_default.mean(), "Default rate by loan purpose", "03_default_by_purpose.png",
     highlight_top=2)

# PD model - logistic regression (explainable; standard in credit risk)
feat_num = ["credit_score", "dti", "annual_income", "loan_amount", "interest_rate", "age"]
X = pd.get_dummies(L[feat_num + ["term_months", "purpose", "job"]].astype({"term_months": str}),
                   drop_first=True, dtype=float)
y = L["is_default"]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.25, random_state=42, stratify=y)
scaler = StandardScaler().fit(Xtr)
model = LogisticRegression(max_iter=2000).fit(scaler.transform(Xtr), ytr)
auc = roc_auc_score(yte, model.predict_proba(scaler.transform(Xte))[:, 1])
L["pd_score"] = model.predict_proba(scaler.transform(X))[:, 1].round(4)
coef = pd.DataFrame({"feature": X.columns, "coefficient": model.coef_[0]}).assign(
    abs=lambda d: d.coefficient.abs()).sort_values("abs", ascending=False).drop(columns="abs")
coef.to_csv(TAB / "pd_model_coefficients.csv", index=False)
top = coef.head(10).set_index("feature")["coefficient"][::-1]
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.barh(top.index, top.values, color=[ORANGE if v > 0 else BLUE for v in top.values], height=.6)
ax.axvline(0, color="#c3c2b7", lw=1)
ax.set_title(f"What drives default? (logistic regression, test AUC {auc:.2f})")
ax.set_xlabel("standardised coefficient  (orange = raises risk, blue = lowers risk)")
fig.tight_layout(); fig.savefig(FIG / "04_pd_model_drivers.png"); plt.close(fig)

# ============================================================ 2. SEGMENTATION
seg_feats = ["credit_score", "dti", "annual_income", "loan_amount", "times_30dpd"]
Z = StandardScaler().fit_transform(L[seg_feats])
km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(Z)
L["cluster"] = km.labels_
prof = L.groupby("cluster").agg(customers=("loan_id", "size"), avg_credit=("credit_score", "mean"),
                                avg_dti=("dti", "mean"), avg_income=("annual_income", "mean"),
                                avg_loan=("loan_amount", "mean"), avg_late=("times_30dpd", "mean"),
                                default_rate=("is_default", "mean"))
# name clusters by their profile so the labels are business-readable
order = prof["default_rate"].sort_values().index.tolist()
names = {}
for c in order:
    r = prof.loc[c]
    if r.default_rate == prof.default_rate.max():
        names[c] = "Stressed Borrowers"
    elif r.avg_income == prof.avg_income.max():
        names[c] = "Affluent Prime"
    elif r.default_rate == prof.default_rate.min():
        names[c] = "Steady Prime"
    else:
        names[c] = "Stretched Mid-Market"
# guarantee 4 unique names
if len(set(names.values())) < 4:
    for c, n in zip(order, ["Steady Prime", "Affluent Prime", "Stretched Mid-Market", "Stressed Borrowers"]):
        names[c] = n
L["segment"] = L["cluster"].map(names)
prof = prof.rename(index=names).round(4).sort_values("default_rate").reset_index(names="segment")
prof.to_csv(TAB / "customer_risk_segments.csv", index=False)
hbar(prof.set_index("segment")["default_rate"], "Default rate by customer segment (K-Means)",
     "05_segments.png", highlight_top=1)

# Customer base credit profile (real UCI data): unknown credit history is the red flag here
cu["credit_unknown"] = (cu["credit_default_flag"] == "unknown").astype(int)
base_profile = rate_table(cu, "job", "credit_unknown").rename(columns={"rate": "unknown_credit_rate"})
base_profile.to_csv(TAB / "customer_base_unknown_credit_by_job.csv", index=False)

# ============================================================ 3. TRANSACTION ANOMALIES
acct = tx.groupby("account_id")["amount"].agg(acct_median="median", acct_std="std").reset_index()
tx = tx.merge(acct, on="account_id", how="left")
tx["amount_z"] = ((tx["amount"] - tx["acct_median"]) / tx["acct_std"]).round(2)
dev_accts = tx.groupby("device_id")["account_id"].nunique()
ip_accts = tx.groupby("ip_address")["account_id"].nunique()
tx["accounts_on_device"] = tx["device_id"].map(dev_accts)
tx["accounts_on_ip"] = tx["ip_address"].map(ip_accts)
q_amt, q_dur = tx["amount"].quantile(.98), tx["duration_sec"].quantile(.98)
dev_hi, ip_hi = dev_accts.quantile(.95), ip_accts.quantile(.95)
RULES = {
    "Multiple login attempts (3+)": tx["login_attempts"] >= 3,
    "Amount > 3 std above account norm": tx["amount_z"] > 3,
    "Amount in top 2% overall": tx["amount"] > q_amt,
    "Drains 80%+ of balance": tx["amount_to_balance"] > .8,
    "Very long session (top 2%)": tx["duration_sec"] > q_dur,
    "Device shared by many accounts": tx["accounts_on_device"] > dev_hi,
    "IP shared by many accounts": tx["accounts_on_ip"] > ip_hi,
}
for k, v in RULES.items():
    tx[k] = v.astype(int)
tx["rule_flags"] = tx[list(RULES)].sum(axis=1)

iso_cols = ["amount", "amount_z", "duration_sec", "login_attempts", "amount_to_balance", "account_balance"]
iso = IsolationForest(n_estimators=300, contamination=.02, random_state=42).fit(tx[iso_cols])
tx["iso_anomaly"] = (iso.predict(tx[iso_cols]) == -1).astype(int)
tx["iso_score"] = (-iso.score_samples(tx[iso_cols])).round(4)
tx["is_suspicious"] = ((tx["rule_flags"] >= 2) | (tx["iso_anomaly"] == 1)).astype(int)
tx["alert_level"] = np.select([(tx.rule_flags >= 3) | ((tx.iso_anomaly == 1) & (tx.rule_flags >= 2)),
                               tx.is_suspicious == 1, tx.rule_flags == 1],
                              ["High", "Medium", "Watch"], "Normal")

rule_summary = pd.DataFrame({
    "indicator": list(RULES),
    "transactions": [int(tx[k].sum()) for k in RULES],
    "share_of_all": [round(tx[k].mean(), 4) for k in RULES],
    "share_also_isolation_forest": [round(tx.loc[tx[k] == 1, "iso_anomaly"].mean(), 4) for k in RULES],
}).sort_values("transactions", ascending=False)
rule_summary.to_csv(TAB / "transaction_fraud_indicators.csv", index=False)
anom_by_channel = rate_table(tx, "channel", "is_suspicious")
anom_by_type = rate_table(tx, "transaction_type", "is_suspicious")
anom_by_occ = rate_table(tx, "customer_occupation", "is_suspicious")
anom_by_loc = rate_table(tx, "location", "is_suspicious")
for n_, t in [("channel", anom_by_channel), ("type", anom_by_type), ("occupation", anom_by_occ),
              ("location", anom_by_loc)]:
    t.to_csv(TAB / f"suspicious_tx_by_{n_}.csv", index=False)

sus_cols = ["transaction_id", "account_id", "transaction_date", "amount", "account_balance", "channel",
            "transaction_type", "location", "login_attempts", "duration_sec", "amount_z",
            "accounts_on_device", "accounts_on_ip", "rule_flags", "iso_anomaly", "iso_score", "alert_level"]
tx.loc[tx.is_suspicious == 1, sus_cols].sort_values(["rule_flags", "iso_score"], ascending=False) \
    .to_csv(SCO / "suspicious_transactions.csv", index=False)

fig, ax = plt.subplots(figsize=(7, 4))
norm = tx[tx.is_suspicious == 0].sample(6000, random_state=1)
sus = tx[tx.is_suspicious == 1]
ax.scatter(norm.amount, norm.duration_sec, s=6, c="#c3c2b7", alpha=.5, label="Normal", lw=0)
ax.scatter(sus.amount, sus.duration_sec, s=10, c=ORANGE, alpha=.8, label="Suspicious", lw=0)
ax.set_xlabel("transaction amount ($)"); ax.set_ylabel("session duration (sec)")
ax.grid(axis="y", color=GRID, lw=.6)
ax.set_title(f"Transaction anomalies — {tx.is_suspicious.sum():,} of {len(tx):,} flagged")
ax.legend(frameon=False, loc="upper right")
fig.tight_layout(); fig.savefig(FIG / "06_tx_anomalies.png"); plt.close(fig)
hbar(rule_summary.set_index("indicator")["transactions"], "Fraud indicators triggered (transactions)",
     "07_tx_indicators.png", pct=False)

# ============================================================ 4. INSURANCE CLAIMS
TYP = claims.groupby("policy_type")["claim_amount"].transform("mean")  # same rule as SQL & Excel
claims["amount_vs_typical"] = (claims["claim_amount"] / TYP).round(2)
claims["loss_ratio"] = (claims["claim_amount"] / claims["annual_premium"]).round(2)
CFLAGS = {
    "New policy (< 6 months)": claims["policy_tenure_months"] < 6,
    "Claim > 2x typical for policy": claims["amount_vs_typical"] > 2,
    "Reported late (> 20 days)": claims["days_to_report"] > 20,
    "2+ prior claims": claims["prior_claims"] >= 2,
    "No police report (Auto/Home)": (claims["police_report"] == 0) & claims["policy_type"].isin(["Auto", "Home"]),
    "No witnesses": claims["witnesses"] == 0,
    "Theft incident": claims["incident_type"] == "Theft",
}
base_fraud = claims["is_fraud_confirmed"].mean()
crows = []
for k, m in CFLAGS.items():
    claims[k] = m.astype(int)
    fr = claims.loc[m, "is_fraud_confirmed"].mean()
    crows.append({"indicator": k, "claims": int(m.sum()), "fraud_rate_when_present": round(fr, 4),
                  "fraud_rate_when_absent": round(claims.loc[~m, "is_fraud_confirmed"].mean(), 4),
                  "lift": round(fr / base_fraud, 2)})
claim_flags = pd.DataFrame(crows).sort_values("lift", ascending=False)
claim_flags.to_csv(TAB / "claims_fraud_indicators.csv", index=False)
claims["red_flags"] = claims[list(CFLAGS)].sum(axis=1)
flags_curve = rate_table(claims.assign(red_flags=claims.red_flags.clip(upper=5)), "red_flags",
                         "is_fraud_confirmed").sort_values("red_flags")
flags_curve.to_csv(TAB / "claims_fraud_by_flag_count.csv", index=False)
claims_by_type = claims.groupby("policy_type").agg(
    claims=("claim_id", "size"), total_paid=("claim_amount", "sum"), avg_claim=("claim_amount", "mean"),
    median_claim=("claim_amount", "median"), avg_days_to_report=("days_to_report", "mean"),
    fraud_rate=("is_fraud_confirmed", "mean")).round(4).reset_index().sort_values("claims", ascending=False)
claims_by_type.to_csv(TAB / "claims_by_policy_type.csv", index=False)
claims["claim_month"] = claims["claim_date"].dt.to_period("Q").astype(str)
claims_trend = claims.groupby("claim_month").agg(claims=("claim_id", "size"),
                                                 fraud=("is_fraud_confirmed", "sum")).reset_index()
claims.loc[claims.red_flags >= 3].sort_values("red_flags", ascending=False)[
    ["claim_id", "customer_id", "policy_type", "incident_type", "claim_date", "claim_amount",
     "amount_vs_typical", "policy_tenure_months", "days_to_report", "prior_claims", "red_flags",
     "claim_status", "is_fraud_confirmed"]].to_csv(SCO / "claims_for_review.csv", index=False)
hbar(claim_flags.set_index("indicator")["lift"], "Claim red flags — fraud lift vs. average",
     "08_claim_flags.png", pct=False, highlight_top=2)
fig, ax = plt.subplots(figsize=(7, 3.6))
ax.bar(flags_curve.red_flags.astype(str), flags_curve.rate, color=BLUE, width=.6)
for x, v in enumerate(flags_curve.rate):
    ax.text(x, v, f"{v:.0%}", ha="center", va="bottom", fontsize=9, color="#52514e")
ax.set_xlabel("number of red flags on the claim (5 = 5 or more)")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
ax.grid(axis="y", color=GRID); ax.grid(axis="x", visible=False)
ax.set_title("Confirmed fraud rate rises with each red flag")
fig.tight_layout(); fig.savefig(FIG / "09_claim_flag_curve.png"); plt.close(fig)

# ============================================================ 5. PAYMENT BEHAVIOR
L["payment_behavior"] = np.select(
    [L.times_90dpd > 0, L.times_30dpd >= 3, L.times_30dpd >= 1], ["Severe delinquency (90+ DPD)",
                                                                  "Chronic late payer", "Occasional late"],
    "Always on time")
pay = rate_table(L, "payment_behavior", "is_default")
pay.to_csv(TAB / "payment_behavior_vs_default.csv", index=False)
acct_beh = tx.groupby("account_id").agg(
    transactions=("transaction_id", "size"), avg_amount=("amount", "mean"),
    debit_share=("transaction_type", lambda s: (s == "Debit").mean()),
    online_share=("channel", lambda s: (s == "Online").mean()),
    avg_balance=("account_balance", "mean"), suspicious_share=("is_suspicious", "mean")).round(3).reset_index()
acct_beh.to_csv(SCO / "account_behavior.csv", index=False)
monthly = tx.groupby(tx.transaction_date.dt.to_period("Q").astype(str)).agg(
    volume=("amount", "sum"), transactions=("transaction_id", "size"),
    suspicious=("is_suspicious", "sum")).reset_index(names="quarter")
monthly.to_csv(TAB / "transactions_by_quarter.csv", index=False)
channel_mix = tx.groupby(["channel", "transaction_type"]).agg(
    transactions=("transaction_id", "size"), avg_amount=("amount", "mean")).round(2).reset_index()
channel_mix.to_csv(TAB / "channel_type_mix.csv", index=False)
hbar(pay.set_index("payment_behavior")["rate"], "Default rate by repayment behaviour",
     "10_payment_behavior.png", highlight_top=1)

# ============================================================ 6. RISK CATEGORY
# Composite borrower score 0-100: 60% model PD, 25% delinquency history, 15% leverage (DTI)
pd_pct = L["pd_score"].rank(pct=True)
delinq = ((L.times_30dpd.clip(upper=6) / 6) * .6 + L.times_90dpd.clip(upper=3) / 3 * .4)
lev = L["dti"].rank(pct=True)
L["risk_score"] = (100 * (.60 * pd_pct + .25 * delinq + .15 * lev)).round(1)
L["risk_tier"] = pd.cut(L["risk_score"], [-1, 35, 55, 70, 101], labels=["Low", "Medium", "High", "Critical"])
tiers = L.groupby("risk_tier", observed=True).agg(
    borrowers=("loan_id", "size"), exposure=("loan_amount", "sum"), avg_score=("risk_score", "mean"),
    default_rate=("is_default", "mean"), avg_credit=("credit_score", "mean")).round(3).reset_index()
tiers["exposure_share"] = (tiers.exposure / tiers.exposure.sum()).round(4)
tiers.to_csv(TAB / "risk_tiers.csv", index=False)
L[["loan_id", "customer_id", "job", "age", "segment", "grade", "loan_amount", "credit_score", "dti",
   "times_30dpd", "times_90dpd", "pd_score", "risk_score", "risk_tier", "loan_status", "is_default"]] \
    .to_csv(SCO / "borrower_risk_scores.csv", index=False)
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.bar(tiers.risk_tier.astype(str), tiers.default_rate,
       color=[TIER_COLORS[t] for t in tiers.risk_tier.astype(str)], width=.55)
for x, (v, n) in enumerate(zip(tiers.default_rate, tiers.borrowers)):
    ax.text(x, v, f"{v:.0%}\n{n:,} loans", ha="center", va="bottom", fontsize=9, color="#52514e")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
ax.set_ylim(0, tiers.default_rate.max() * 1.3)
ax.grid(axis="y", color=GRID); ax.grid(axis="x", visible=False)
ax.set_title("Actual default rate by assigned risk tier")
fig.tight_layout(); fig.savefig(FIG / "11_risk_tiers.png"); plt.close(fig)

# ============================================================ dashboard data
dash["kpis"] = {
    "loans": int(len(L)), "loan_book": float(L.loan_amount.sum()), "default_rate": float(L.is_default.mean()),
    "defaulted_amount": float(L.loc[L.is_default == 1, "loan_amount"].sum()), "pd_auc": round(float(auc), 3),
    "transactions": int(len(tx)), "tx_volume": float(tx.amount.sum()), "accounts": int(tx.account_id.nunique()),
    "suspicious_tx": int(tx.is_suspicious.sum()), "high_alerts": int((tx.alert_level == "High").sum()),
    "claims": int(len(claims)), "claims_paid": float(claims.loc[claims.claim_status == "Paid", "claim_amount"].sum()),
    "claim_fraud_rate": float(base_fraud), "claims_for_review": int((claims.red_flags >= 3).sum()),
    "customers": int(len(cu)), "critical_borrowers": int((L.risk_tier == "Critical").sum()),
    "critical_exposure": float(L.loc[L.risk_tier == "Critical", "loan_amount"].sum()),
}
dash["default_by"] = default_by
dash["segments"] = to_records(prof)
dash["tiers"] = to_records(tiers.assign(risk_tier=tiers.risk_tier.astype(str)))
dash["pd_drivers"] = to_records(coef.head(10))
dash["payment_behavior"] = to_records(pay)
dash["tx_indicators"] = to_records(rule_summary)
dash["tx_by_channel"] = to_records(anom_by_channel)
dash["tx_by_type"] = to_records(anom_by_type)
dash["tx_by_location"] = to_records(anom_by_loc.head(10))
dash["tx_quarterly"] = to_records(monthly)
dash["tx_alert_levels"] = tx.alert_level.value_counts().to_dict()
dash["tx_top_alerts"] = to_records(
    tx.loc[tx.alert_level == "High", ["transaction_id", "account_id", "transaction_date", "amount",
                                      "channel", "location", "login_attempts", "rule_flags", "iso_score"]]
    .sort_values(["rule_flags", "iso_score"], ascending=False)
    .drop_duplicates("account_id").head(12)
    .assign(transaction_date=lambda d: d.transaction_date.dt.strftime("%Y-%m-%d")))
dash["claims_by_type"] = to_records(claims_by_type)
dash["claim_flags"] = to_records(claim_flags)
dash["claim_flag_curve"] = to_records(flags_curve)
dash["claims_trend"] = to_records(claims_trend)
dash["base_unknown_credit"] = to_records(base_profile)
dash["top_borrowers"] = to_records(
    L.loc[L.risk_tier == "Critical", ["loan_id", "job", "grade", "loan_amount", "credit_score", "dti",
                                       "times_30dpd", "risk_score", "loan_status"]]
    .sort_values("risk_score", ascending=False).head(12))
(ROOT / "docs" / "data.json").write_text(json.dumps(dash, default=float))

print(f"PD model AUC (test): {auc:.3f}")
print("Segments:\n", prof[["segment", "customers", "default_rate"]].to_string(index=False))
print("Tiers:\n", tiers[["risk_tier", "borrowers", "default_rate", "exposure_share"]].to_string(index=False))
print(f"Suspicious transactions: {tx.is_suspicious.sum():,} ({tx.is_suspicious.mean():.1%}); alerts:",
      tx.alert_level.value_counts().to_dict())
print("Claim flags:\n", claim_flags.to_string(index=False))
print("Flag curve:", flags_curve[["red_flags", "rate"]].to_dict("records"))
