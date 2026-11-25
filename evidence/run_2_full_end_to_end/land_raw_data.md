# land_raw_data — executed notebook output

- Notebook: `/Workspace/Users/shuheng.pi@databricks.com/.bundle/playerpulse/dev/files/src/notebooks/00_setup_and_land_raw_data`
- Job run: 931556335206949 · task run: 705259340653939 · result: **SUCCESS**
- Started 2026-11-25 14:50:01 UTC, duration 25s

# 00 · Setup Unity Catalog objects and land raw game data
**PlayerPulse — Emberforge Studios · "Emberline: Rift Tactics" (synthetic)**

Creates schemas, volumes and governance policy functions, then writes the raw exports the studio's systems
produce (account service, game-server telemetry, store receipts, helpdesk + in-game feedback, LiveOps calendar)
into the landing volume. Lakeflow ingests them incrementally from there.

```python
dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("force_regenerate", "false")
CATALOG = dbutils.widgets.get("catalog")
FORCE = dbutils.widgets.get("force_regenerate").lower() == "true"
```

```python
for schema, comment in [
    ("playerpulse_raw", "Landing-zone volumes for raw game-system exports"),
    ("playerpulse_game", "Lakeflow Declarative Pipeline output: bronze / silver / gold player & title tables"),
    ("playerpulse_ml", "Features, churn model, predictions and GenAI outputs"),
    ("playerpulse_serving", "Curated retention queue published to Lakebase for the LiveOps app and game backend"),
    ("playerpulse_governance", "Column-mask policy functions"),
]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema} COMMENT '{comment}'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.playerpulse_raw.landing COMMENT 'Raw exports: accounts, telemetry, receipts, tickets, LiveOps calendar'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.playerpulse_raw.evidence COMMENT 'Run logs captured as execution evidence'")
display(spark.sql(f"SHOW SCHEMAS IN {CATALOG} LIKE 'playerpulse*'"))
```
**Output:**

| databaseName |
|---|
| playerpulse_game |
| playerpulse_governance |
| playerpulse_ml |
| playerpulse_raw |
| playerpulse_serving |

### Governance policy functions (must exist before the pipeline declares masked columns)
Player PII (email, device advertising id, birth year) is visible in clear text only to members of the
`playerpulse_player_support` account group. Analysts, Genie, the model and the app only see masked values.

```python
G = f"{CATALOG}.playerpulse_governance"
spark.sql(f"""
CREATE OR REPLACE FUNCTION {G}.mask_pii(val STRING)
RETURNS STRING
COMMENT 'PlayerPulse PII mask: clear text only for members of playerpulse_player_support'
RETURN CASE WHEN is_account_group_member('playerpulse_player_support') THEN val
            WHEN val IS NULL THEN NULL
            ELSE concat(left(val, 3), repeat('*', 6)) END
""")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {G}.mask_int(val INT)
RETURNS INT
COMMENT 'PlayerPulse numeric PII mask (birth year): NULL unless member of playerpulse_player_support'
RETURN CASE WHEN is_account_group_member('playerpulse_player_support') THEN val ELSE NULL END
""")
display(spark.sql(f"SHOW USER FUNCTIONS IN {G}"))
```
**Output:**

| function |
|---|
| aws_demo_catalog.playerpulse_governance.mask_int |
| aws_demo_catalog.playerpulse_governance.mask_pii |

```python
import os, sys, json
LANDING = f"/Volumes/{CATALOG}/playerpulse_raw/landing"
already = os.path.exists(f"{LANDING}/telemetry_daily") and len(os.listdir(f"{LANDING}/telemetry_daily")) > 0
print("landing already populated:", already)
```
**Output:**

```text
landing already populated: True
```

```python
# The simulator lives in ../common (workspace files deployed by the bundle)
nb_dir = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
sys.path.append(os.path.abspath(os.path.join("/Workspace" + nb_dir, "..")))
from common.simulator import simulate

if FORCE or not already:
    import shutil, tempfile
    tmp = tempfile.mkdtemp()
    stats = simulate(tmp)
    for sub in os.listdir(tmp):
        dst = f"{LANDING}/{sub}"
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(tmp, sub), dst)
    with open(f"/Volumes/{CATALOG}/playerpulse_raw/evidence/00_simulation_stats.json", "w") as f:
        json.dump(stats, f, indent=2, default=str)
else:
    stats = json.load(open(f"/Volumes/{CATALOG}/playerpulse_raw/evidence/00_simulation_stats.json"))
print(json.dumps(stats, indent=2, default=str))
```
**Output:**

```text
{
  "days": 245,
  "players": 64642,
  "minors": 7565,
  "telemetry_rows": 6169033,
  "purchases": 92136,
  "gross_revenue_usd": 1801660.96,
  "payers": 16039,
  "tickets": 27395,
  "churned_players": 20647,
  "churn_by_month": {
    "2026-03": 1405,
    "2026-04": 1375,
    "2026-05": 1520,
    "2026-06": 3242,
    "2026-07": 4088,
    "2026-08": 4834,
    "2026-09": 2535,
    "2026-10": 1648
  },
  "dau_by_month": {
    "2026-03": 21709.0,
    "2026-04": 24940.0,
    "2026-05": 26323.0,
    "2026-06": 24730.0,
    "2026-07": 24667.0,
    "2026-08": 22721.0,
    "2026-09": 26704.0,
    "2026-10": 29670.0
  },
  "revenue_by_month": {
    "2026-03": 181384.0,
    "2026-04": 204562.0,
    "2026-05": 181086.0,
    "2026-06": 231597.0,
    "2026-07": 258421.0,
    "2026-08": 203220.0,
    "2026-09": 306560.0,
    "2026-10": 234831.0
  }
}
```

```python
for sub in sorted(os.listdir(LANDING)):
    files = os.listdir(f"{LANDING}/{sub}")
    size = sum(os.path.getsize(f"{LANDING}/{sub}/{f}") for f in files)
    print(f"{sub:20s} files={len(files):3d}  size={size/1e6:7.1f} MB")
```
**Output:**

```text
liveops_calendar     files=  1  size=    0.0 MB
player_accounts      files=  1  size=    6.2 MB
store_transactions   files=  8  size=   17.4 MB
support_tickets      files=  8  size=    4.8 MB
telemetry_daily      files=  8  size=   72.9 MB
```
