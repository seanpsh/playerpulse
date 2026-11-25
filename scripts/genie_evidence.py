"""Ask the Genie space a list of questions and write the answers (text, generated SQL, result rows) to Markdown.

usage: python3 scripts/genie_evidence.py <profile> <space_id> <out.md>
"""
import json
import subprocess
import sys
import time

profile, space, out = sys.argv[1:4]
QUESTIONS = [
    "How did the 14-day lapse rate of whales change from Season 6 to Season 7?",
    "What was the crash rate by device tier before and after client v7.2?",
    "What are high-risk payers complaining about, by ticket category?",
    "How many players in the retention queue are blocked from paid offers, and why?",
    "How much incremental revenue does PlayerPulse deliver versus the current win-back rule?",
    "Show weekly ARPDAU since March",
]


def api(verb, path, body=None):
    cmd = ["databricks", "-p", profile, "api", verb, path] + (["--json", json.dumps(body)] if body else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout.strip() else {"error": r.stderr}


base = f"/api/2.0/genie/spaces/{space}"
lines = ["# Genie space conversations (real API output)", "", f"Space id: `{space}` · captured {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}", ""]
for q in QUESTIONS:
    r = api("post", f"{base}/start-conversation", {"content": q})
    conv, mid = r.get("conversation_id"), r.get("message_id")
    m = {}
    for _ in range(90):
        m = api("get", f"{base}/conversations/{conv}/messages/{mid}")
        if m.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(3)
    lines += [f"## Q: {q}", "", f"_status: {m.get('status')}_", ""]
    for a in m.get("attachments") or []:
        if "text" in a:
            lines += ["**Genie:** " + a["text"].get("content", ""), ""]
        if "query" in a:
            qd = a["query"]
            if qd.get("description"):
                lines += ["**Genie:** " + qd["description"], ""]
            lines += ["```sql", qd.get("query", "").strip(), "```", ""]
            res = api("get", f"{base}/conversations/{conv}/messages/{mid}/attachments/{a['attachment_id']}/query-result")
            sr = res.get("statement_response", {})
            cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
            rows = (sr.get("result", {}) or {}).get("data_array", []) or []
            if cols:
                lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
                lines += ["| " + " | ".join("" if v is None else str(v) for v in row) + " |" for row in rows[:25]]
                lines += [""]
    print("answered:", q, "->", m.get("status"))
open(out, "w").write("\n".join(lines) + "\n")
