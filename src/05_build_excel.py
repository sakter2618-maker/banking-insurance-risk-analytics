"""
Step 5 - Excel risk workbook
============================
Builds excel/Risk_Analytics_Workbook.xlsx: data sheets + a Summary sheet where every number is a
live Excel formula (COUNTIFS / AVERAGEIFS / SUMIFS), so the workbook recalculates if data changes.

Run:  python src/05_build_excel.py
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "excel"
OUT.mkdir(exist_ok=True)
F = "Arial"
NAVY, GREY, LIGHT = "1F3A5F", "52514E", "EEF3FA"
H1 = Font(name=F, size=16, bold=True, color=NAVY)
H2 = Font(name=F, size=11, bold=True, color=NAVY)
BODY, MUTED, BOLD = Font(name=F, size=10), Font(name=F, size=9, italic=True, color=GREY), Font(name=F, size=10, bold=True)
HEAD_FILL, KPI_FILL = PatternFill("solid", fgColor=NAVY), PatternFill("solid", fgColor=LIGHT)
THIN = Border(bottom=Side(style="thin", color="E1E0D9"))

loans = pd.read_csv(ROOT / "outputs" / "scored" / "borrower_risk_scores.csv")
claims = pd.read_csv(ROOT / "data" / "processed" / "insurance_claims.csv")
sus = pd.read_csv(ROOT / "outputs" / "scored" / "suspicious_transactions.csv")
tx_n = len(pd.read_csv(ROOT / "data" / "processed" / "transactions.csv", usecols=["transaction_id"]))

wb = Workbook()


def data_sheet(name, df, table_name, widths=None):
    ws = wb.create_sheet(name)
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append(list(row))
    ref = f"A1:{get_column_letter(df.shape[1])}{len(df) + 1}"
    t = Table(displayName=table_name, ref=ref)
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(t)
    for i, c in enumerate(df.columns, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(c, max(11, len(c) + 3))
    for row in ws.iter_rows():
        for cell in row:
            cell.font = BODY
    for cell in ws[1]:
        cell.font = Font(name=F, size=10, bold=True, color="FFFFFF")
    ws.freeze_panes = "A2"
    return ws


# ---------------------------------------------------------------- data sheets
ws_l = data_sheet("Loans", loans, "tblLoans")
for col in ("G",):  # loan_amount
    for c in ws_l[col][1:]:
        c.number_format = "$#,##0"
ws_c = data_sheet("Claims", claims.assign(claim_date=claims.claim_date), "tblClaims",
                  {"incident_type": 18, "claim_status": 20})
# Red-flag count is an Excel formula on every claim row (same 7 rules as the Python analysis)
n = len(claims) + 1
ws_c["O1"] = "red_flags"
ws_c["O1"].font = Font(name=F, size=10, bold=True)
ws_c["O1"].fill = HEAD_FILL
ws_c["O1"].font = Font(name=F, size=10, bold=True, color="FFFFFF")
for r in range(2, n + 1):
    ws_c[f"O{r}"] = (f"=(H{r}<6)+(F{r}>2*AVERAGEIFS($F$2:$F${n},$C$2:$C${n},C{r}))+(I{r}>20)+(J{r}>=2)"
                     f"+AND(K{r}=0,OR(C{r}=\"Auto\",C{r}=\"Home\"))+(L{r}=0)+(D{r}=\"Theft\")")
    ws_c[f"O{r}"].font = BODY
ws_c.column_dimensions["O"].width = 11
for c in ws_c["F"][1:]:
    c.number_format = "$#,##0"
data_sheet("Suspicious_Tx", sus, "tblSuspicious", {"transaction_date": 14})

# ---------------------------------------------------------------- summary
ws = wb.active
ws.title = "Summary"
ws.sheet_view.showGridLines = False
ws.column_dimensions["A"].width = 2
for col, w in zip("BCDEFGHI", [30, 14, 14, 14, 14, 3, 30, 14]):
    ws.column_dimensions[col].width = w
ws["B2"] = "Banking & Insurance Risk Analytics — Summary"
ws["B2"].font = H1
ws["B3"] = ("Every figure below is a live formula over the Loans, Claims and Suspicious_Tx sheets. "
            "Loans and claims are synthetic (see README); transactions are real.")
ws["B3"].font = MUTED

LN, CL = f"Loans!$A$2:$P${len(loans) + 1}", None
L = lambda c: f"Loans!${c}$2:${c}${len(loans) + 1}"   # noqa: E731
C = lambda c: f"Claims!${c}$2:${c}${len(claims) + 1}"  # noqa: E731
# Loans columns: A loan_id B customer_id C job D age E segment F grade G loan_amount H credit_score I dti
# J times_30dpd K times_90dpd L pd_score M risk_score N risk_tier O loan_status P is_default
kpis = [
    ("Loans", f"=COUNTA({L('A')})", "#,##0"),
    ("Loan book ($)", f"=SUM({L('G')})", "$#,##0"),
    ("Default rate", f"=AVERAGE({L('P')})", "0.0%"),
    ("Defaulted amount ($)", f"=SUMIFS({L('G')},{L('P')},1)", "$#,##0"),
    ("Critical-tier exposure ($)", f"=SUMIFS({L('G')},{L('N')},\"Critical\")", "$#,##0"),
    ("Suspicious transactions", f"=COUNTA(Suspicious_Tx!$A$2:$A${len(sus) + 1})", "#,##0"),
    ("Total transactions analysed", tx_n, "#,##0"),
    ("Claims", f"=COUNTA({C('A')})", "#,##0"),
    ("Confirmed claim fraud rate", f"=AVERAGE({C('N')})", "0.0%"),
    ("Claims with 3+ red flags", f"=COUNTIF({C('O')},\">=3\")", "#,##0"),
]
ws["B5"] = "Key metrics"
ws["B5"].font = H2
for i, (label, f, fmt) in enumerate(kpis):
    r = 6 + i
    ws[f"B{r}"], ws[f"C{r}"] = label, f
    ws[f"B{r}"].font, ws[f"C{r}"].font = BODY, BOLD
    ws[f"C{r}"].number_format = fmt
    ws[f"C{r}"].fill = KPI_FILL
    ws[f"B{r}"].border = ws[f"C{r}"].border = THIN
ws["D12"] = "← hardcoded from transactions.csv (50,000 rows, too large to embed)"
ws["D12"].font = MUTED
ws["C12"].font = Font(name=F, size=10, bold=True, color="0000FF")


def header(row, col, labels):
    for j, lab in enumerate(labels):
        c = ws.cell(row=row, column=col + j, value=lab)
        c.font = Font(name=F, size=10, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center" if j else "left")


# Default by occupation (B..E)
r0 = 18
ws[f"B{r0 - 1}"] = "Q1. Which customer group has the highest loan default?"
ws[f"B{r0 - 1}"].font = H2
header(r0, 2, ["Occupation", "Loans", "Defaults", "Default rate"])
jobs = loans.groupby("job").is_default.mean().sort_values(ascending=False).index.tolist()
for i, j in enumerate(jobs):
    r = r0 + 1 + i
    ws[f"B{r}"] = j
    ws[f"C{r}"] = f"=COUNTIFS({L('C')},B{r})"
    ws[f"D{r}"] = f"=COUNTIFS({L('C')},B{r},{L('P')},1)"
    ws[f"E{r}"] = f"=IFERROR(D{r}/C{r},0)"
    for col in "BCDE":
        ws[f"{col}{r}"].font = BODY
        ws[f"{col}{r}"].border = THIN
    ws[f"C{r}"].number_format = ws[f"D{r}"].number_format = "#,##0"
    ws[f"E{r}"].number_format = "0.0%"
r_job_end = r0 + len(jobs)
ws.conditional_formatting.add(f"E{r0 + 1}:E{r_job_end}", DataBarRule(start_type="num", start_value=0,
                              end_type="max", color="EB6834"))

# Risk tiers (H..I side) - Q3
ws["H17"] = "Q3. Which customer segment is most risky?"
ws["H17"].font = H2
header(18, 8, ["Risk tier", "Borrowers"])
ws.column_dimensions["J"].width = 14
ws.column_dimensions["K"].width = 14
for j, lab in enumerate(["Exposure ($)", "Default rate"]):
    c = ws.cell(row=18, column=10 + j, value=lab)
    c.font, c.fill, c.alignment = Font(name=F, size=10, bold=True, color="FFFFFF"), HEAD_FILL, Alignment(horizontal="center")
for i, t in enumerate(["Low", "Medium", "High", "Critical"]):
    r = 19 + i
    ws[f"H{r}"] = t
    ws[f"I{r}"] = f"=COUNTIFS({L('N')},H{r})"
    ws[f"J{r}"] = f"=SUMIFS({L('G')},{L('N')},H{r})"
    ws[f"K{r}"] = f"=IFERROR(AVERAGEIFS({L('P')},{L('N')},H{r}),0)"
    ws[f"I{r}"].number_format, ws[f"J{r}"].number_format, ws[f"K{r}"].number_format = "#,##0", "$#,##0", "0.0%"
    for col in "HIJK":
        ws[f"{col}{r}"].font = BODY
        ws[f"{col}{r}"].border = THIN
ws.conditional_formatting.add("K19:K22", CellIsRule(operator="greaterThan", formula=["0.3"],
                              font=Font(name=F, color="D03B3B", bold=True)))

# Segments
ws["H25"] = "K-Means segments"
ws["H25"].font = H2
header(26, 8, ["Segment", "Borrowers"])
for j, lab in enumerate(["Avg credit", "Default rate"]):
    c = ws.cell(row=26, column=10 + j, value=lab)
    c.font, c.fill, c.alignment = Font(name=F, size=10, bold=True, color="FFFFFF"), HEAD_FILL, Alignment(horizontal="center")
for i, s in enumerate(["Steady Prime", "Stretched Mid-Market", "Affluent Prime", "Stressed Borrowers"]):
    r = 27 + i
    ws[f"H{r}"] = s
    ws[f"I{r}"] = f"=COUNTIFS({L('E')},H{r})"
    ws[f"J{r}"] = f"=IFERROR(AVERAGEIFS({L('H')},{L('E')},H{r}),0)"
    ws[f"K{r}"] = f"=IFERROR(AVERAGEIFS({L('P')},{L('E')},H{r}),0)"
    ws[f"I{r}"].number_format, ws[f"J{r}"].number_format, ws[f"K{r}"].number_format = "#,##0", "0", "0.0%"
    for col in "HIJK":
        ws[f"{col}{r}"].font = BODY
        ws[f"{col}{r}"].border = THIN

# Claims by red flags - Q4
rc = r_job_end + 3
ws[f"B{rc - 1}"] = "Q4. Which claim patterns are abnormal? (fraud rate by red-flag count)"
ws[f"B{rc - 1}"].font = H2
header(rc, 2, ["Red flags", "Claims", "Fraud cases", "Fraud rate"])
for i in range(6):
    r = rc + 1 + i
    ws[f"B{r}"] = i if i < 5 else "5+"
    crit = f"\"{i}\"" if i < 5 else "\">=5\""
    ws[f"C{r}"] = f"=COUNTIFS({C('O')},{crit})"
    ws[f"D{r}"] = f"=COUNTIFS({C('O')},{crit},{C('N')},1)"
    ws[f"E{r}"] = f"=IFERROR(D{r}/C{r},0)"
    ws[f"E{r}"].number_format = "0.0%"
    for col in "BCDE":
        ws[f"{col}{r}"].font = BODY
        ws[f"{col}{r}"].border = THIN
    ws[f"B{r}"].alignment = Alignment(horizontal="left")

# Claims by policy type
ws["H33"] = "Claims by policy type"
ws["H33"].font = H2
header(34, 8, ["Policy type", "Claims"])
for j, lab in enumerate(["Total claimed ($)", "Fraud rate"]):
    c = ws.cell(row=34, column=10 + j, value=lab)
    c.font, c.fill, c.alignment = Font(name=F, size=10, bold=True, color="FFFFFF"), HEAD_FILL, Alignment(horizontal="center")
ws.column_dimensions["J"].width = 17
for i, p in enumerate(["Auto", "Health", "Home", "Travel", "Life"]):
    r = 35 + i
    ws[f"H{r}"] = p
    ws[f"I{r}"] = f"=COUNTIFS({C('C')},H{r})"
    ws[f"J{r}"] = f"=SUMIFS({C('F')},{C('C')},H{r})"
    ws[f"K{r}"] = f"=IFERROR(AVERAGEIFS({C('N')},{C('C')},H{r}),0)"
    ws[f"I{r}"].number_format, ws[f"J{r}"].number_format, ws[f"K{r}"].number_format = "#,##0", "$#,##0", "0.0%"
    for col in "HIJK":
        ws[f"{col}{r}"].font = BODY
        ws[f"{col}{r}"].border = THIN

# Charts
ch = BarChart()
ch.type, ch.style, ch.title = "bar", 10, "Default rate by occupation"
ch.add_data(Reference(ws, min_col=5, min_row=r0, max_row=r_job_end), titles_from_data=True)
ch.set_categories(Reference(ws, min_col=2, min_row=r0 + 1, max_row=r_job_end))
ch.y_axis.numFmt, ch.legend, ch.height, ch.width = "0%", None, 8, 14
ch.x_axis.scaling.orientation = "maxMin"
ch.series[0].graphicalProperties.solidFill = "2A78D6"
ws.add_chart(ch, f"M5")
ch2 = BarChart()
ch2.type, ch2.style, ch2.title = "col", 10, "Claim fraud rate by red-flag count"
ch2.add_data(Reference(ws, min_col=5, min_row=rc, max_row=rc + 6), titles_from_data=True)
ch2.set_categories(Reference(ws, min_col=2, min_row=rc + 1, max_row=rc + 6))
ch2.y_axis.numFmt, ch2.legend, ch2.height, ch2.width = "0%", None, 7, 14
ch2.series[0].graphicalProperties.solidFill = "EB6834"
ws.add_chart(ch2, "M22")
ws.freeze_panes = "A4"

out = OUT / "Risk_Analytics_Workbook.xlsx"
wb.save(out)
print("Saved", out.relative_to(ROOT))
