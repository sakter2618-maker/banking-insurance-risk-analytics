"""
Financial Risk Dashboard — Streamlit app
========================================
Interactive version of the dashboard with filters, drill-downs and CSV downloads.

Run locally:   streamlit run app.py
Deploy:        Streamlit Community Cloud -> New app -> this repo -> main file: app.py

Reads the files produced by run_all.py (data/processed, outputs/).
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Financial Risk Dashboard", page_icon="📊", layout="wide")

# ------------------------------------------------------------------ style
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#c3c2b7"
TIER = {"Low": "#0ca30c", "Medium": "#fab219", "High": "#ec835a", "Critical": "#d03b3b"}
SEG = {"Steady Prime": "#0ca30c", "Stretched Mid-Market": BLUE, "Affluent Prime": "#fab219",
       "Stressed Borrowers": "#d03b3b"}
ALERT = {"Normal": GREY, "Watch": "#fab219", "Medium": "#ec835a", "High": "#d03b3b"}
st.markdown("""
<style>
  .block-container {padding-top: 2rem; max-width: 1240px;}
  h1 {font-size: 1.55rem !important; font-weight: 650 !important; letter-spacing: -.015em;}
  h3 {font-size: 1rem !important; font-weight: 620 !important; margin-bottom: .1rem;}
  .kpi {background: var(--secondary-background-color); border-radius: 12px; padding: 14px 16px;
         border: 1px solid rgba(128,128,128,.15); margin-bottom: 12px; min-height: 104px;}
  .kpi .l {font-size: .82rem; opacity: .75;} .kpi .v {font-size: 1.6rem; font-weight: 650; letter-spacing: -.02em;}
  .kpi .n {font-size: .76rem; opacity: .6;}
  [data-testid="stMetric"] {background: var(--secondary-background-color); border-radius: 12px;
      padding: 14px 16px; border: 1px solid rgba(128,128,128,.15);}
  [data-testid="stMetricLabel"] p {font-size: .82rem; opacity: .8;}
  [data-testid="stMetricValue"] {font-size: 1.55rem; font-weight: 650;}
  .note {font-size: .78rem; opacity: .65; margin-top: -6px; margin-bottom: 8px;}
  .tag {display:inline-block; font-size:.74rem; padding:2px 9px; border-radius:999px;
        background: rgba(250,178,25,.18); margin-bottom: 6px;}
  .tag.real {background: rgba(42,120,214,.14);}
  .insight {border-left: 3px solid #1f3a5f; padding: 2px 0 2px 12px; font-size: .9rem; opacity: .9;}
</style>""", unsafe_allow_html=True)


def layout(fig, h=320, pct_x=False, pct_y=False):
    fig.update_layout(height=h, margin=dict(l=8, r=16, t=8, b=8), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", showlegend=False, font=dict(size=12),
                      hoverlabel=dict(font_size=12), bargap=.35)
    fig.update_xaxes(showgrid=pct_x or not pct_y, gridcolor="rgba(128,128,128,.15)", zeroline=False,
                     tickformat=".0%" if pct_x else None)
    fig.update_yaxes(showgrid=pct_y, gridcolor="rgba(128,128,128,.15)", zeroline=False,
                     tickformat=".0%" if pct_y else None)
    return fig


def hbar(df, label, value, colors=None, fmt=".1%", h=None, hover=None):
    d = df.sort_values(value)
    c = colors if colors is not None else [BLUE] * len(d)
    fig = go.Figure(go.Bar(x=d[value], y=d[label].astype(str), orientation="h", marker_color=c,
                           marker_cornerradius=3, text=[f"{v:{fmt}}" for v in d[value]],
                           textposition="outside", cliponaxis=False,
                           hovertext=hover(d) if hover else None, hoverinfo="text" if hover else "x+y"))
    return layout(fig, h or max(180, 30 * len(d) + 30), pct_x=fmt.endswith("%"))


def top_n_colors(d, value, n=2):
    order = d[value].rank(ascending=False, method="first")
    return [ORANGE if r <= n else BLUE for r in order]


def money(v):
    return f"${v / 1e6:,.1f}M" if v >= 1e6 else f"${v / 1e3:,.1f}K" if v >= 1e3 else f"${v:,.0f}"


def kpi(col, label, value, note=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div>'
                 f'<div class="n">{note}</div></div>', unsafe_allow_html=True)


def download(df, name, label="Download CSV"):
    st.download_button(label, df.to_csv(index=False).encode(), file_name=name, mime="text/csv")


# ------------------------------------------------------------------ data
@st.cache_data
def load():
    P, S, T = ROOT / "data" / "processed", ROOT / "outputs" / "scored", ROOT / "outputs" / "tables"
    loans = pd.read_csv(P / "loans.csv").merge(
        pd.read_csv(S / "borrower_risk_scores.csv")[["loan_id", "job", "age", "segment", "pd_score",
                                                      "risk_score", "risk_tier"]], on="loan_id")
    cust = pd.read_csv(P / "customers.csv")
    loans = loans.merge(cust[["customer_id", "age_band", "education", "marital"]], on="customer_id")
    loans["credit_band"] = pd.cut(loans.credit_score, [0, 580, 620, 660, 700, 740, 900],
                                  labels=["<580", "580-619", "620-659", "660-699", "700-739", "740+"])
    loans["dti_band"] = pd.cut(loans.dti, [0, 15, 20, 25, 30, 35, 100],
                               labels=["<15", "15-20", "20-25", "25-30", "30-35", "35+"])
    loans["payment_behavior"] = pd.Series(pd.NA, index=loans.index, dtype="object")
    loans.loc[:, "payment_behavior"] = "Always on time"
    loans.loc[loans.times_30dpd >= 1, "payment_behavior"] = "Occasional late"
    loans.loc[loans.times_30dpd >= 3, "payment_behavior"] = "Chronic late payer"
    loans.loc[loans.times_90dpd > 0, "payment_behavior"] = "Severe delinquency (90+ DPD)"

    tx = pd.read_csv(P / "transactions.csv", parse_dates=["transaction_date"])
    sus = pd.read_csv(S / "suspicious_transactions.csv")
    tx = tx.merge(sus[["transaction_id", "rule_flags", "iso_anomaly", "iso_score", "alert_level"]],
                  on="transaction_id", how="left")
    tx["alert_level"] = tx["alert_level"].fillna("Normal / Watch")
    tx["is_suspicious"] = tx["iso_score"].notna().astype(int)
    tx["quarter"] = tx.transaction_date.dt.to_period("Q").astype(str)

    cl = pd.read_csv(P / "insurance_claims.csv", parse_dates=["claim_date"])
    typ = cl.groupby("policy_type").claim_amount.transform("mean")
    flags = {
        "Claim > 2x typical for policy": cl.claim_amount > 2 * typ,
        "New policy (< 6 months)": cl.policy_tenure_months < 6,
        "Reported late (> 20 days)": cl.days_to_report > 20,
        "Theft incident": cl.incident_type == "Theft",
        "2+ prior claims": cl.prior_claims >= 2,
        "No police report (Auto/Home)": (cl.police_report == 0) & cl.policy_type.isin(["Auto", "Home"]),
        "No witnesses": cl.witnesses == 0,
    }
    for k, v in flags.items():
        cl[k] = v.astype(int)
    cl["red_flags"] = cl[list(flags)].sum(axis=1)
    tables = {f.stem: pd.read_csv(f) for f in T.glob("*.csv")}
    return loans, cust, tx, cl, list(flags), tables


loans, cust, tx, claims, CLAIM_FLAGS, TB = load()

# ------------------------------------------------------------------ header + navigation
st.title("Financial Risk Dashboard")
st.caption("Banking & Insurance Risk Analytics · credit, transaction and insurance-claims risk · data 2020–2025")
page = st.radio("Page", ["Overview", "Loan Default", "Customer Segments", "Transactions & Fraud",
                         "Insurance Claims"], horizontal=True, label_visibility="collapsed")
st.divider()

# ================================================================== OVERVIEW
if page == "Overview":
    c = st.columns(5)
    kpi(c[0], "Loan book", money(loans.loan_amount.sum()), f"{len(loans):,} loans")
    kpi(c[1], "Default rate", f"{loans.is_default.mean():.1%}",
        f"{money(loans.loc[loans.is_default == 1, 'loan_amount'].sum())} defaulted")
    crit = loans[loans.risk_tier == "Critical"]
    kpi(c[2], "Critical-risk exposure", money(crit.loan_amount.sum()), f"{len(crit):,} borrowers")
    kpi(c[3], "Suspicious transactions", f"{tx.is_suspicious.sum():,}",
        f"{tx.is_suspicious.mean():.1%} of {len(tx):,}")
    kpi(c[4], "Claims for investigation", f"{(claims.red_flags >= 3).sum():,}", "3+ red flags")

    left, right = st.columns([7, 5])
    tiers = loans.groupby("risk_tier").agg(borrowers=("loan_id", "size"), exposure=("loan_amount", "sum"),
                                           avg_credit=("credit_score", "mean"), default_rate=("is_default", "mean"))
    tiers = tiers.reindex(["Low", "Medium", "High", "Critical"]).reset_index()
    with left:
        st.subheader("Borrowers by risk tier")
        st.markdown('<p class="note">Composite score: 60% model PD · 25% delinquency · 15% debt-to-income</p>',
                    unsafe_allow_html=True)
        show = tiers.assign(share=tiers.borrowers / tiers.borrowers.sum(), exposure=tiers.exposure.map(money))
        st.dataframe(show, hide_index=True, use_container_width=True, column_config={
            "risk_tier": "Tier", "borrowers": st.column_config.NumberColumn("Borrowers", format="%d"),
            "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, max_value=1),
            "exposure": "Exposure",
            "avg_credit": st.column_config.NumberColumn("Avg credit", format="%.0f"),
            "default_rate": st.column_config.NumberColumn("Default rate", format="percent")})
        cr, lo = tiers.iloc[3], tiers.iloc[0]
        st.markdown(f'<p class="insight"><b>{cr.borrowers / tiers.borrowers.sum():.1%}</b> of borrowers are '
                    f'Critical, holding <b>{money(cr.exposure)}</b> — they default '
                    f'{cr.default_rate / lo.default_rate:.0f}× more often than Low-tier borrowers.</p>',
                    unsafe_allow_html=True)
    with right:
        st.subheader("Actual default rate by tier")
        st.markdown('<p class="note">Does the tiering separate good from bad borrowers?</p>', unsafe_allow_html=True)
        fig = go.Figure(go.Bar(x=tiers.risk_tier, y=tiers.default_rate, marker_color=[TIER[t] for t in tiers.risk_tier],
                               marker_cornerradius=4, text=[f"{v:.0%}" for v in tiers.default_rate],
                               textposition="outside", cliponaxis=False))
        st.plotly_chart(layout(fig, 300, pct_y=True), use_container_width=True)

    st.subheader("Key findings")
    job = loans.groupby("job").is_default.mean().sort_values(ascending=False)
    seg = loans.groupby("segment").is_default.mean().sort_values(ascending=False)
    cf = TB["claims_fraud_indicators"].iloc[0]
    curve = claims.groupby("red_flags").is_fraud_confirmed.mean()
    st.dataframe(pd.DataFrame([
        ["Which customer group defaults most?", f"{job.index[0].title()} ({job.iloc[0]:.1%}) and {job.index[1]} "
         f"({job.iloc[1]:.1%}) vs {loans.is_default.mean():.1%} average", "Income verification / co-signer"],
        ["Which transactions are abnormal?", f"{tx.is_suspicious.sum():,} flagged by 7 rules + Isolation Forest",
         f"Step-up auth on {(tx.alert_level == 'High').sum():,} high alerts"],
        ["Which customer segment is most risky?", f"{seg.index[0]}: {seg.iloc[0]:.0%} default",
         "Early collections outreach"],
        ["Which claim patterns are abnormal?", f"\"{cf.indicator}\" ({cf.lift}× lift); 4 flags → {curve.get(4, 0):.0%} fraud",
         "Route 3+ flag claims to SIU"],
    ], columns=["Business question", "Answer", "Recommended action"]), hide_index=True, use_container_width=True)

# ================================================================== LOAN DEFAULT
elif page == "Loan Default":
    st.markdown('<span class="tag">Loan book is synthetic, linked to real customers</span>', unsafe_allow_html=True)
    with st.expander("Filters", expanded=False):
        f1, f2, f3 = st.columns(3)
        g = f1.multiselect("Grade", sorted(loans.grade.unique()), default=sorted(loans.grade.unique()))
        p = f2.multiselect("Purpose", sorted(loans.purpose.unique()), default=sorted(loans.purpose.unique()))
        t = f3.multiselect("Term (months)", [36, 60], default=[36, 60])
    L = loans[loans.grade.isin(g) & loans.purpose.isin(p) & loans.term_months.isin(t)]
    if L.empty:
        st.warning("No loans match these filters.")
        st.stop()
    c = st.columns(4)
    kpi(c[0], "Loans", f"{len(L):,}", money(L.loan_amount.sum()) + " originated")
    kpi(c[1], "Default rate", f"{L.is_default.mean():.1%}")
    kpi(c[2], "Defaulted amount", money(L.loc[L.is_default == 1, "loan_amount"].sum()))
    kpi(c[3], "Avg credit score", f"{L.credit_score.mean():.0f}")

    def rate(col):
        return L.groupby(col, observed=True).agg(rate=("is_default", "mean"), n=("loan_id", "size")).reset_index()

    hov = lambda d: [f"{a}: {r:.1%} default · {n:,} loans" for a, r, n in zip(d.iloc[:, 0], d.rate, d.n)]  # noqa: E731
    a, b = st.columns(2)
    with a:
        st.subheader("Default rate by occupation")
        st.markdown('<p class="note">Q: Which customer group has the highest loan default?</p>', unsafe_allow_html=True)
        d = rate("job")
        st.plotly_chart(hbar(d, "job", "rate", top_n_colors(d.sort_values("rate"), "rate"), hover=hov),
                        use_container_width=True)
    with b:
        st.subheader("Default rate by credit score")
        st.markdown('<p class="note">Clear step-down as credit score improves</p>', unsafe_allow_html=True)
        d = rate("credit_band")
        fig = go.Figure(go.Bar(x=d.credit_band.astype(str), y=d.rate, marker_color=BLUE, marker_cornerradius=4,
                               text=[f"{v:.0%}" for v in d.rate], textposition="outside", cliponaxis=False,
                               hovertext=hov(d), hoverinfo="text"))
        st.plotly_chart(layout(fig, 400, pct_y=True), use_container_width=True)
    a, b, c3 = st.columns(3)
    for col, title, box in [("purpose", "By loan purpose", a), ("dti_band", "By debt-to-income", b),
                            ("age_band", "By age band", c3)]:
        with box:
            st.subheader(title)
            d = rate(col)
            st.plotly_chart(hbar(d, col, "rate", hover=hov), use_container_width=True)
    a, b = st.columns(2)
    with a:
        st.subheader("What drives default")
        st.markdown('<p class="note">Standardised logistic-regression coefficients (full portfolio, test AUC 0.71)</p>',
                    unsafe_allow_html=True)
        co = TB["pd_model_coefficients"].head(10).assign(size=lambda d: d.coefficient.abs())
        st.plotly_chart(hbar(co, "feature", "size", [ORANGE if v > 0 else BLUE for v in co.sort_values("size").coefficient],
                             fmt=".2f"), use_container_width=True)
        st.caption("Orange raises risk · blue lowers risk")
    with b:
        st.subheader("Payment behaviour vs default")
        st.markdown('<p class="note">Late-payment history is the strongest early warning</p>', unsafe_allow_html=True)
        d = rate("payment_behavior")
        st.plotly_chart(hbar(d, "payment_behavior", "rate", hover=hov), use_container_width=True)
    with st.expander(f"Loan records ({len(L):,})"):
        cols = ["loan_id", "job", "grade", "purpose", "loan_amount", "credit_score", "dti", "times_30dpd",
                "pd_score", "risk_tier", "loan_status"]
        st.dataframe(L[cols].sort_values("pd_score", ascending=False), hide_index=True, use_container_width=True)
        download(L[cols], "loans_filtered.csv")

# ================================================================== SEGMENTS
elif page == "Customer Segments":
    st.markdown('<span class="tag">Borrower data synthetic</span>', unsafe_allow_html=True)
    st.markdown("K-Means clustering (k = 4) on credit score, DTI, income, loan size and late payments. "
                "**Q: Which customer segment is most risky?**")
    prof = loans.groupby("segment").agg(borrowers=("loan_id", "size"), default_rate=("is_default", "mean"),
                                        avg_credit=("credit_score", "mean"), avg_dti=("dti", "mean"),
                                        avg_income=("annual_income", "mean"), avg_loan=("loan_amount", "mean"),
                                        avg_late=("times_30dpd", "mean")).sort_values("default_rate").reset_index()
    cols = st.columns(4)
    for col, r in zip(cols, prof.itertuples()):
        with col:
            with st.container(border=True):
                st.markdown(f"<span style='color:{SEG[r.segment]}'>●</span> **{r.segment}**", unsafe_allow_html=True)
                st.markdown(f'<div class="kpi" style="border:0;padding:4px 0;min-height:0;background:none">'
                            f'<div class="v">{r.default_rate:.1%}</div><div class="n">default rate · '
                            f'{r.borrowers:,} borrowers</div></div>', unsafe_allow_html=True)
                st.markdown(f"Avg credit **{r.avg_credit:.0f}** · DTI **{r.avg_dti:.1f}%**  \n"
                            f"Income **{money(r.avg_income).replace('$', '&#36;')}** · "
                            f"Loan **{money(r.avg_loan).replace('$', '&#36;')}**  \n"
                            f"Late payments **{r.avg_late:.1f}**", unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.subheader("Default rate by segment")
        st.plotly_chart(hbar(prof, "segment", "default_rate", [SEG[s] for s in prof.segment]), use_container_width=True)
        st.subheader("Credit score vs debt-to-income")
        st.markdown('<p class="note">Sample of 3,000 borrowers, coloured by segment</p>', unsafe_allow_html=True)
        smp = loans.sample(3000, random_state=1)
        fig = go.Figure()
        for s, col in SEG.items():
            d = smp[smp.segment == s]
            fig.add_trace(go.Scattergl(x=d.credit_score, y=d.dti, mode="markers", name=s,
                                       marker=dict(color=col, size=5, opacity=.55)))
        fig = layout(fig, 340)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-.18))
        fig.update_xaxes(title="credit score")
        fig.update_yaxes(title="DTI %", showgrid=True)
        st.plotly_chart(fig, use_container_width=True)
    with b:
        st.subheader("Unknown credit history, by occupation")
        st.markdown(f'<p class="note"><span class="tag real">Real data</span> customer base ({len(cust):,}) — share whose '
                    'credit-default status is "unknown"</p>', unsafe_allow_html=True)
        d = cust.assign(u=cust.credit_default_flag.eq("unknown")).groupby("job").u.mean().reset_index()
        st.plotly_chart(hbar(d, "job", "u", top_n_colors(d.sort_values("u"), "u", 3)), use_container_width=True)
    st.subheader("Borrower watch-list")
    tier = st.segmented_control("Risk tier", ["Critical", "High", "Medium", "Low"], default="Critical") \
        if hasattr(st, "segmented_control") else st.selectbox("Risk tier", ["Critical", "High", "Medium", "Low"])
    w = loans[loans.risk_tier == (tier or "Critical")].sort_values("risk_score", ascending=False)
    wcols = ["loan_id", "customer_id", "job", "grade", "loan_amount", "credit_score", "dti", "times_30dpd",
             "risk_score", "loan_status"]
    st.dataframe(w[wcols].head(200), hide_index=True, use_container_width=True, column_config={
        "risk_score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.0f"),
        "loan_amount": st.column_config.NumberColumn("Amount", format="dollar")})
    download(w[wcols], f"watchlist_{(tier or 'Critical').lower()}.csv", f"Download all {len(w):,} {tier} borrowers")

# ================================================================== TRANSACTIONS
elif page == "Transactions & Fraud":
    st.markdown('<span class="tag real">Real data · 50,000 transactions</span>', unsafe_allow_html=True)
    st.markdown("Seven rule-based red flags plus an **Isolation Forest** model. **Q: Which transactions are abnormal?**")
    with st.expander("Filters", expanded=False):
        f1, f2, f3 = st.columns(3)
        ch = f1.multiselect("Channel", sorted(tx.channel.unique()), default=sorted(tx.channel.unique()))
        ty = f2.multiselect("Type", sorted(tx.transaction_type.unique()), default=sorted(tx.transaction_type.unique()))
        yr = f3.slider("Year", int(tx.transaction_date.dt.year.min()), int(tx.transaction_date.dt.year.max()), (2020, 2025))
    T = tx[tx.channel.isin(ch) & tx.transaction_type.isin(ty) & tx.transaction_date.dt.year.between(*yr)]
    if T.empty:
        st.warning("No transactions match these filters.")
        st.stop()
    c = st.columns(4)
    kpi(c[0], "Transactions", f"{len(T):,}", f"{money(T.amount.sum())} · {T.account_id.nunique()} accounts")
    kpi(c[1], "Suspicious", f"{T.is_suspicious.sum():,}", f"{T.is_suspicious.mean():.1%} of filtered")
    kpi(c[2], "High alerts", f"{(T.alert_level == 'High').sum():,}", "3+ rules, or model + 2 rules")
    kpi(c[3], "Medium alerts", f"{(T.alert_level == 'Medium').sum():,}", "2 rules, or model only")
    a, b = st.columns([2, 1])
    with a:
        st.subheader("Transactions per quarter")
        q = T.groupby("quarter").agg(n=("transaction_id", "size"), s=("is_suspicious", "sum")).reset_index()
        fig = go.Figure(go.Scatter(x=q.quarter, y=q.n, mode="lines", line=dict(color=BLUE, width=2), fill="tozeroy",
                                   fillcolor="rgba(42,120,214,.08)",
                                   hovertext=[f"{a}: {n:,} tx · {s:,} suspicious ({s / n:.1%})" for a, n, s in zip(q.quarter, q.n, q.s)],
                                   hoverinfo="text"))
        fig = layout(fig, 300).update_yaxes(showgrid=True).update_xaxes(showgrid=False, dtick=4, tickangle=0)
        st.plotly_chart(fig, use_container_width=True)
    with b:
        st.subheader("Amount vs session length")
        smp = pd.concat([T[T.is_suspicious == 0].sample(min(3000, (T.is_suspicious == 0).sum()), random_state=1),
                         T[T.is_suspicious == 1]])
        fig = go.Figure()
        for flag, col, nm in [(0, GREY, "Normal"), (1, ORANGE, "Suspicious")]:
            d = smp[smp.is_suspicious == flag]
            fig.add_trace(go.Scattergl(x=d.amount, y=d.duration_sec, mode="markers", name=nm,
                                       marker=dict(color=col, size=4, opacity=.6 if flag else .35)))
        fig = layout(fig, 300)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-.28))
        fig.update_xaxes(title="amount ($)")
        fig.update_yaxes(title="session (sec)", showgrid=True)
        st.plotly_chart(fig, use_container_width=True)
    a, b = st.columns([7, 5])
    with a:
        st.subheader("Fraud indicators")
        st.markdown('<p class="note">Transactions hitting each red-flag rule (full dataset) and agreement with the ML model</p>',
                    unsafe_allow_html=True)
        ind = TB["transaction_fraud_indicators"]
        st.plotly_chart(hbar(ind, "indicator", "transactions", fmt=",.0f",
                             hover=lambda d: [f"{i}: {n:,} tx · {s:.0%} also flagged by Isolation Forest"
                                              for i, n, s in zip(d.indicator, d.transactions, d.share_also_isolation_forest)]),
                        use_container_width=True)
    with b:
        st.subheader("Suspicious rate by channel")
        d = T.groupby("channel").is_suspicious.mean().reset_index()
        st.plotly_chart(hbar(d, "channel", "is_suspicious", top_n_colors(d.sort_values("is_suspicious"), "is_suspicious", 1)),
                        use_container_width=True)
        st.subheader("Top locations")
        d = T.groupby("location").is_suspicious.mean().nlargest(6).reset_index()
        st.plotly_chart(hbar(d, "location", "is_suspicious"), use_container_width=True)
    st.subheader("Alert queue")
    lvl = st.multiselect("Alert level", ["High", "Medium"], default=["High"])
    q = T[T.alert_level.isin(lvl)].sort_values(["rule_flags", "iso_score"], ascending=False)
    qcols = ["transaction_id", "account_id", "transaction_date", "amount", "account_balance", "channel", "location",
             "login_attempts", "rule_flags", "iso_score", "alert_level"]
    st.dataframe(q[qcols], hide_index=True, use_container_width=True, column_config={
        "transaction_date": st.column_config.DateColumn("Date"),
        "amount": st.column_config.NumberColumn("Amount", format="dollar"),
        "account_balance": st.column_config.NumberColumn("Balance", format="dollar"),
        "iso_score": st.column_config.NumberColumn("Anomaly score", format="%.2f")})
    download(q[qcols], "alert_queue.csv", f"Download {len(q):,} alerts")

# ================================================================== CLAIMS
else:
    st.markdown('<span class="tag">Claims data synthetic</span>', unsafe_allow_html=True)
    st.markdown("Red flags used by Special Investigation Units. **Q: Which claim patterns are abnormal?**")
    pt = st.multiselect("Policy type", sorted(claims.policy_type.unique()), default=sorted(claims.policy_type.unique()))
    C = claims[claims.policy_type.isin(pt)]
    if C.empty:
        st.warning("Select at least one policy type.")
        st.stop()
    c = st.columns(4)
    kpi(c[0], "Claims", f"{len(C):,}", money(C.claim_amount.sum()) + " claimed")
    kpi(c[1], "Paid out", money(C.loc[C.claim_status == "Paid", "claim_amount"].sum()))
    kpi(c[2], "Confirmed fraud rate", f"{C.is_fraud_confirmed.mean():.1%}")
    kpi(c[3], "Flagged for review", f"{(C.red_flags >= 3).sum():,}", "3+ red flags")
    a, b = st.columns(2)
    with a:
        st.subheader("Fraud rate rises with every red flag")
        d = C.assign(k=C.red_flags.clip(upper=5)).groupby("k").agg(r=("is_fraud_confirmed", "mean"),
                                                                  n=("claim_id", "size")).reset_index()
        fig = go.Figure(go.Bar(x=[("5+" if k == 5 else str(k)) for k in d.k], y=d.r, marker_color=BLUE, marker_cornerradius=4,
                               text=[f"{v:.0%}" for v in d.r], textposition="outside", cliponaxis=False,
                               hovertext=[f"{k} flags: {r:.1%} fraud · {n:,} claims" for k, r, n in zip(d.k, d.r, d.n)],
                               hoverinfo="text"))
        fig = layout(fig, 330, pct_y=True)
        fig.update_xaxes(title="red flags on the claim")
        st.plotly_chart(fig, use_container_width=True)
    with b:
        st.subheader("Red-flag lift")
        st.markdown('<p class="note">Fraud rate when the flag is present ÷ average fraud rate</p>', unsafe_allow_html=True)
        base = C.is_fraud_confirmed.mean()
        lift = pd.DataFrame([{"flag": f, "lift": C.loc[C[f] == 1, "is_fraud_confirmed"].mean() / base,
                              "n": int(C[f].sum())} for f in CLAIM_FLAGS if C[f].sum() > 0])
        st.plotly_chart(hbar(lift, "flag", "lift", top_n_colors(lift.sort_values("lift"), "lift"), fmt=".2f",
                             hover=lambda d: [f"{f}: {l:.2f}× · {n:,} claims" for f, l, n in zip(d.flag, d.lift, d.n)]),
                        use_container_width=True)
    st.subheader("Claims by policy type")
    s = C.groupby("policy_type").agg(claims=("claim_id", "size"), total=("claim_amount", "sum"),
                                     avg=("claim_amount", "mean"), days=("days_to_report", "mean"),
                                     fraud=("is_fraud_confirmed", "mean")).sort_values("claims", ascending=False).reset_index()
    s["total"] = s["total"].map(money)
    st.dataframe(s, hide_index=True, use_container_width=True, column_config={
        "policy_type": "Policy type", "claims": "Claims", "total": "Total claimed",
        "avg": st.column_config.NumberColumn("Avg claim", format="dollar"),
        "days": st.column_config.NumberColumn("Avg days to report", format="%.1f"),
        "fraud": st.column_config.NumberColumn("Fraud rate", format="percent")})
    st.subheader("Investigation queue (3+ red flags)")
    rv = C[C.red_flags >= 3].sort_values(["red_flags", "claim_amount"], ascending=False)
    rcols = ["claim_id", "customer_id", "policy_type", "incident_type", "claim_date", "claim_amount",
             "policy_tenure_months", "days_to_report", "prior_claims", "red_flags", "claim_status"]
    st.dataframe(rv[rcols], hide_index=True, use_container_width=True, column_config={
        "claim_date": st.column_config.DateColumn("Date"),
        "claim_amount": st.column_config.NumberColumn("Amount", format="dollar")})
    download(rv[rcols], "claims_for_review.csv", f"Download {len(rv):,} claims")

st.divider()
st.caption("Built by Salma Akter · Python · SQL · Excel · Streamlit · Transactions: Kaggle bank transactions · "
           "Customers: UCI Bank Marketing · Loans & claims: synthetic, generated with documented rules.")
