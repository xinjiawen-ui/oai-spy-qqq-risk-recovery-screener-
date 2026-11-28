"""Validate the consolidated static dashboard before publishing."""
from pathlib import Path
import re
html=(Path(__file__).resolve().parents[1]/"index.html").read_text()
scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",html,flags=re.S|re.I)
if len(scripts)!=1 or html.count("</html>")!=1:
    raise SystemExit("Expected one inline script and one HTML document")
for token in ("function decisionOverview(d)", "function evidencePanel(d)", "function bindJournal(d)", "function loadRegimes()", "function refreshDashboard()"):
    if token not in scripts[0]:
        raise SystemExit("Required renderer missing: "+token)
for id_ in ("app","checklist","history","method","regimeContent","sourceNotes"):
    if html.count('id="'+id_+'"')!=1:
        raise SystemExit("Missing or duplicated panel: "+id_)
Path("/tmp/dashboard-inline.js").write_text(scripts[0])
print("Consolidated dashboard structure verified")
