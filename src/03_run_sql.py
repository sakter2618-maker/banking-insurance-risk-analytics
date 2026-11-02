"""
Step 3 - Run the SQL queries
============================
Loads data/processed/*.csv into a local SQLite database (no server needed) and runs every
query in sql/02_business_queries.sql. Each result is saved to outputs/sql_results/Q<n>.csv.
The same .sql file runs unchanged on PostgreSQL (see sql/01_schema.sql for loading steps).

Run:  python src/03_run_sql.py
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "sql_results"
OUT.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(":memory:")
for t in ["customers", "loans", "insurance_claims", "transactions"]:
    pd.read_csv(ROOT / "data" / "processed" / f"{t}.csv").to_sql(t, con, index=False)

sql = (ROOT / "sql" / "02_business_queries.sql").read_text()
blocks = re.split(r"\n(?=-- Q\d+:)", sql)
for b in blocks:
    m = re.match(r"-- (Q\d+): (.*)", b)
    if not m:
        continue
    qid, title = m.groups()
    df = pd.read_sql_query(b.strip().rstrip(";"), con)
    df.to_csv(OUT / f"{qid}.csv", index=False)
    print(f"{qid:4s} {len(df):3d} rows  {title}")
