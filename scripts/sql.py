"""Run SQL on a Databricks SQL warehouse (Statement Execution API) and print a Markdown table.
usage: python3 scripts/sql.py <profile> <warehouse_id> "<sql>" """
import json, subprocess, sys
profile, wh, stmt = sys.argv[1:4]
body = {"warehouse_id": wh, "statement": stmt, "wait_timeout": "50s", "format": "JSON_ARRAY", "disposition": "INLINE"}
r = json.loads(subprocess.run(["databricks", "-p", profile, "api", "post", "/api/2.0/sql/statements", "--json", json.dumps(body)],
                              capture_output=True, text=True).stdout)
while r.get("status", {}).get("state") in ("PENDING", "RUNNING"):
    r = json.loads(subprocess.run(["databricks", "-p", profile, "api", "get", f"/api/2.0/sql/statements/{r['statement_id']}"],
                                  capture_output=True, text=True).stdout)
if r.get("status", {}).get("state") != "SUCCEEDED":
    print("ERROR:", json.dumps(r.get("status"))[:1500]); sys.exit(1)
cols = [c["name"] for c in r.get("manifest", {}).get("schema", {}).get("columns", [])]
if not cols:
    print("OK (no result set)"); sys.exit(0)
print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
for row in r.get("result", {}).get("data_array", []) or []:
    print("| " + " | ".join("" if v is None else str(v).replace("\n", " ") for v in row) + " |")
