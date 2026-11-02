"""
Step 4 - Build the web dashboard
================================
Injects docs/data.json into dashboard/template.html and writes docs/index.html:
a single self-contained page (no libraries, no server) that GitHub Pages can host for free.

Run:  python src/04_build_dashboard.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
data = (ROOT / "docs" / "data.json").read_text(encoding="utf-8")
out = ROOT / "docs" / "index.html"
out.write_text(html.replace("/*__DATA__*/null", data), encoding="utf-8")
print(f"Dashboard written to {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB)")
