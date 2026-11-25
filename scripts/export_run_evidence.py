"""Export a Databricks job run's notebook tasks (code + real cell outputs) to readable Markdown.

usage: python3 scripts/export_run_evidence.py <profile> <job_run_id> <out_dir>
Writes <out_dir>/<task_key>.md for each notebook task, plus <out_dir>/run_summary.md.
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone

profile, run_id, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out_dir, exist_ok=True)


def cli(*args):
    r = subprocess.run(["databricks", "-p", profile, *args, "-o", "json"], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ms else ""


def render_result(r):
    if not r:
        return ""
    blocks = []
    items = r.get("data") if r.get("type") == "listResults" else [r]
    for it in items or []:
        t = it.get("type")
        data = it.get("data")
        if t in ("ansi", "text", "html") and isinstance(data, str):
            txt = re.sub(r"\x1b\[[0-9;]*m", "", data)
            if t == "html":
                txt = re.sub(r"<[^>]+>", " ", txt)
            if txt.strip():
                blocks.append("```text\n" + txt.rstrip()[:20000] + "\n```")
        elif t == "table":
            cols = [c["name"] for c in it.get("schema", [])]
            rows = data or []
            md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            for row in rows[:60]:
                md.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ")[:160] for v in row) + " |")
            if len(rows) > 60:
                md.append(f"\n_({len(rows)} rows, first 60 shown)_")
            blocks.append("\n".join(md))
        elif t == "error" or it.get("name") == "stderr":
            blocks.append("```text\n" + str(data)[:5000] + "\n```")
    return "\n\n".join(blocks)


run = cli("jobs", "get-run", run_id)
summary = [f"# Job run {run_id}: {run.get('run_name')}", "",
           f"- Run page: {run.get('run_page_url')}",
           f"- Started: {ts(run.get('start_time'))}  Ended: {ts(run.get('end_time'))}",
           f"- Result: {run.get('state', {}).get('result_state')}", "",
           "| task | state | result | start | duration (s) |", "|---|---|---|---|---|"]
for t in sorted(run["tasks"], key=lambda x: x.get("start_time", 0) or 0):
    st = t.get("state", {})
    dur = round(((t.get("end_time") or 0) - (t.get("start_time") or 0)) / 1000) if t.get("end_time") else ""
    summary.append(f"| {t['task_key']} | {st.get('life_cycle_state')} | {st.get('result_state')} | {ts(t.get('start_time'))} | {dur} |")
    if "notebook_task" not in t or st.get("result_state") in (None, "EXCLUDED") or st.get("life_cycle_state") == "SKIPPED":
        continue
    exp = cli("jobs", "export-run", str(t["run_id"]), "--views-to-export", "CODE")
    html = exp["views"][0]["content"]
    m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html)
    nb = json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()))
    lines = [f"# {t['task_key']} — executed notebook output", "",
             f"- Notebook: `{t['notebook_task']['notebook_path']}`",
             f"- Job run: {run_id} · task run: {t['run_id']} · result: **{st.get('result_state')}**",
             f"- Started {ts(t.get('start_time'))}, duration {dur}s", ""]
    for c in sorted(nb["commands"], key=lambda c: c["position"]):
        code = c["command"]
        if code.lstrip().startswith("%md"):
            lines.append(code.lstrip()[3:].strip() + "\n")
            continue
        lines.append("```python\n" + code.strip() + "\n```")
        out = render_result(c.get("results"))
        if c.get("error"):
            out += "\n```text\nERROR: " + re.sub(r"<[^>]+>", "", str(c.get("error")))[:3000] + "\n```"
        if out:
            lines.append("**Output:**\n\n" + out)
        lines.append("")
    with open(os.path.join(out_dir, f"{t['task_key']}.md"), "w") as f:
        f.write("\n".join(lines))
    print("wrote", t["task_key"])
with open(os.path.join(out_dir, "run_summary.md"), "w") as f:
    f.write("\n".join(summary) + "\n")
print("\n".join(summary))
