# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Lakebase: refresh operational serving + close the loop
# MAGIC * Triggers the **synced table** pipeline: Delta `playerpulse_serving.player_retention_queue` (CDF) ➜ Lakebase Postgres
# MAGIC   `playerpulse.playerpulse_serving.player_retention_queue_synced`. The LiveOps app reads it, and the game backend can
# MAGIC   look up a player's approved intervention at login with a single-digit-ms primary-key query.
# MAGIC * Verifies the operational copy against the lakehouse source and measures point-lookup latency.
# MAGIC * Reads **interventions** approved in the app (Lakebase `ops.interventions`, OLTP) and snapshots them into Delta, so
# MAGIC   Genie and the next model retrain can measure "did contacted players stay?" (treatment feedback loop).

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade "databricks-sdk>=0.70" "psycopg[binary]>=3.2"
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("instance", "playerpulse-lakebase")
dbutils.widgets.text("database", "playerpulse")
C, INST, DB = (dbutils.widgets.get(k) for k in ("catalog", "instance", "database"))
SRV = f"{C}.playerpulse_serving"
SYNCED = f"{SRV}.player_retention_queue_synced"

import time, uuid
import pandas as pd, psycopg
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
st = w.database.get_synced_database_table(name=SYNCED)
pipeline_id = st.data_synchronization_status.pipeline_id
print("synced table:", SYNCED, "| pipeline:", pipeline_id, "| state:", st.data_synchronization_status.detailed_state)

# COMMAND ----------

def wait_idle():
    for _ in range(80):
        p = w.pipelines.get(pipeline_id=pipeline_id)
        if not p.latest_updates or p.latest_updates[0].state.value in ("COMPLETED", "FAILED", "CANCELED"):
            return p.latest_updates[0].state.value if p.latest_updates else None
        time.sleep(15)

print("previous update:", wait_idle())
upd = w.pipelines.start_update(pipeline_id=pipeline_id)
while True:
    u = w.pipelines.get_update(pipeline_id=pipeline_id, update_id=upd.update_id).update
    if u.state.value in ("COMPLETED", "FAILED", "CANCELED"):
        break
    time.sleep(15)
print("sync update", upd.update_id, "->", u.state.value)
assert u.state.value == "COMPLETED"

# COMMAND ----------

inst = w.database.get_database_instance(name=INST)
def pg():
    cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[INST])
    return psycopg.connect(host=inst.read_write_dns, dbname=DB, user=w.current_user.me().user_name,
                           password=cred.token, sslmode="require", autocommit=True)

def pg_df(sql, params=None):
    with pg() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])

src = spark.sql(f"SELECT count(*) n, CAST(max(refreshed_at) AS STRING) r FROM {SRV}.player_retention_queue").first()
dst = pg_df("SELECT count(*) n, max(refreshed_at)::text r FROM playerpulse_serving.player_retention_queue_synced").iloc[0]
print(f"delta rows={src.n} refreshed={src.r} | lakebase rows={dst.n} refreshed={dst.r}")
assert int(src.n) == int(dst.n)
print(pg_df("""SELECT priority_rank, player_id, payer_tier, round(churn_prob_14d::numeric, 3) AS p14, round(value_at_risk_usd::numeric, 2) AS value_at_risk,
                      next_best_action FROM playerpulse_serving.player_retention_queue_synced WHERE priority_rank <= 8 ORDER BY priority_rank""").to_string(index=False))

# COMMAND ----------

# Game-backend style point lookup at login (primary key)
ids = [r.player_id for r in spark.sql(f"SELECT player_id FROM {SRV}.player_retention_queue ORDER BY rand() LIMIT 50").collect()]
with pg() as conn, conn.cursor() as cur:
    cur.execute("SELECT 1")
    t1 = time.time()
    for pid in ids:
        cur.execute("""SELECT player_id, next_best_action, paid_offer_eligible, ai_message
                       FROM playerpulse_serving.player_retention_queue_synced WHERE player_id = %s""", (pid,))
        cur.fetchall()
    print(f"login lookup latency: avg {(time.time() - t1) / len(ids) * 1000:.1f} ms over {len(ids)} queries (warm connection, from serverless notebook)")

# COMMAND ----------

# MAGIC %md ### Feedback loop: app interventions (Lakebase OLTP) ➜ Delta

# COMMAND ----------

exists = pg_df("SELECT to_regclass('ops.interventions') IS NOT NULL AS e").iloc[0].e
if exists:
    iv = pg_df("SELECT * FROM ops.interventions")
    if len(iv):
        for c in ("created_at", "updated_at"):
            iv[c] = pd.to_datetime(iv[c], utc=True).dt.tz_localize(None)
        spark.createDataFrame(iv).createOrReplaceTempView("iv")
        spark.sql(f"""CREATE OR REPLACE TABLE {SRV}.interventions_snapshot
          COMMENT 'Snapshot of LiveOps interventions approved in the PlayerPulse app (source: Lakebase {INST}/{DB} ops.interventions). Treatment log for uplift measurement.'
          AS SELECT *, current_timestamp() AS snapshot_at FROM iv""")
        spark.sql(f"""SELECT i.status, i.action, count(*) n, round(avg(q.churn_prob_14d), 3) avg_risk, round(sum(q.value_at_risk_usd), 2) value_at_risk
                      FROM {SRV}.interventions_snapshot i LEFT JOIN {SRV}.player_retention_queue q USING (player_id)
                      GROUP BY ALL ORDER BY ALL""").show(truncate=False)
    else:
        print("interventions table is empty")
else:
    print("no interventions table yet (created by the app on first start)")
