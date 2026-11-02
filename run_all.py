"""Run the whole project end to end:  python run_all.py"""
import subprocess
import sys

STEPS = ["src/01_prepare_data.py", "src/02_risk_analysis.py", "src/03_run_sql.py",
         "src/04_build_dashboard.py", "src/05_build_excel.py"]
for s in STEPS:
    print(f"\n=== {s} ===")
    subprocess.run([sys.executable, s], check=True)
print("\nDone. Run  streamlit run app.py  for the interactive app, or open docs/index.html.")
