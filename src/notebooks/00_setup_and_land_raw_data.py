# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup Unity Catalog objects and land raw game data
# MAGIC **PlayerPulse — Emberforge Studios · "Emberline: Rift Tactics" (synthetic)**
# MAGIC
# MAGIC Creates schemas, volumes and governance policy functions, then writes the raw exports the studio's systems
# MAGIC produce (account service, game-server telemetry, store receipts, helpdesk + in-game feedback, LiveOps calendar)
# MAGIC into the landing volume. Lakeflow ingests them incrementally from there.

# COMMAND ----------

dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("force_regenerate", "false")
CATALOG = dbutils.widgets.get("catalog")
FORCE = dbutils.widgets.get("force_regenerate").lower() == "true"

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md
# MAGIC ### Governance policy functions (must exist before the pipeline declares masked columns)
# MAGIC Player PII (email, device advertising id, birth year) is visible in clear text only to members of the
# MAGIC `playerpulse_player_support` account group. Analysts, Genie, the model and the app only see masked values.

# COMMAND ----------

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

# COMMAND ----------

import os, sys, json
LANDING = f"/Volumes/{CATALOG}/playerpulse_raw/landing"
already = os.path.exists(f"{LANDING}/telemetry_daily") and len(os.listdir(f"{LANDING}/telemetry_daily")) > 0
print("landing already populated:", already)

# COMMAND ----------

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

# COMMAND ----------

for sub in sorted(os.listdir(LANDING)):
    files = os.listdir(f"{LANDING}/{sub}")
    size = sum(os.path.getsize(f"{LANDING}/{sub}/{f}") for f in files)
    print(f"{sub:20s} files={len(files):3d}  size={size/1e6:7.1f} MB")
