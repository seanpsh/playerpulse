"""Run Postgres statements on Lakebase through the playerpulse-lakebase-admin job and print the output.
Uses `jobs run-now` with JSON job_parameters (bundle `--params` is CSV-parsed and breaks on quotes / '=').
usage: python3 scripts/pg_admin.py <profile> <database> "<stmt1>;; <stmt2>" """
import json
import subprocess
import sys

profile, db, sql = sys.argv[1:4]
cli = lambda *a: json.loads(subprocess.run(["databricks", "-p", profile, *a, "-o", "json"], capture_output=True, text=True, check=True).stdout)
job = [j["job_id"] for j in cli("jobs", "list") if "playerpulse-lakebase-admin" in j["settings"]["name"]][0]
run = cli("jobs", "run-now", "--json", json.dumps({"job_id": job, "job_parameters": {"database": db, "sql": sql}}))
task = cli("jobs", "get-run", str(run["run_id"]))["tasks"][0]["run_id"]
out = cli("jobs", "get-run-output", str(task))
print(f"-- job run {run['run_id']}")
print(out.get("notebook_output", {}).get("result") or out.get("error"))
