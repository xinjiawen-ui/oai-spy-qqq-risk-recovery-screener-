"""Extract and validate the static dashboard's single inline script before publishing."""
from pathlib import Path
import re
html=(Path(__file__).resolve().parents[1]/"index.html").read_text()
scripts=re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>",html,flags=re.S|re.I)
if len(scripts)!=1: raise SystemExit(f"Expected exactly one inline script; found {len(scripts)}")
if html.count("</html>")!=1: raise SystemExit("Unexpected duplicate HTML document")
if "function asset(t,a)" not in scripts[0]: raise SystemExit("Asset renderer missing")
if "function calculateRisk()" not in scripts[0]: raise SystemExit("Risk calculator missing")
Path("/tmp/dashboard-inline.js").write_text(scripts[0])
print("HTML structure verified; JavaScript syntax checked in next step")
