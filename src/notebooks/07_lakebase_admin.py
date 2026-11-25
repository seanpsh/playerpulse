# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · Lakebase admin (bootstrap & checks)
# MAGIC Runs Postgres statements against the PlayerPulse Lakebase instance with a short-lived OAuth credential.
# MAGIC Used to create the `playerpulse` database, grant the app's service principal access to the synced serving
# MAGIC schema, and capture operational query evidence. Pass statements separated by `;;`.

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade "databricks-sdk>=0.70" "psycopg[binary]>=3.2"
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("instance", "playerpulse-lakebase")
dbutils.widgets.text("database", "databricks_postgres")
dbutils.widgets.text("sql", "SELECT current_user, version()")
INST, DB, SQL = (dbutils.widgets.get(k) for k in ("instance", "database", "sql"))

import uuid, psycopg
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
inst = w.database.get_database_instance(name=INST)
cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[INST])
user = w.current_user.me().user_name
out = []
with psycopg.connect(host=inst.read_write_dns, dbname=DB, user=user, password=cred.token, sslmode="require", autocommit=True) as conn:
    for stmt in [s.strip() for s in SQL.split(";;") if s.strip()]:
        with conn.cursor() as cur:
            try:
                cur.execute(stmt)
                out.append(f"-- {stmt}")
                if cur.description:
                    out.append(" | ".join(c.name for c in cur.description))
                    out += [" | ".join("" if v is None else str(v) for v in r) for r in cur.fetchall()]
                else:
                    out.append(cur.statusmessage)
            except Exception as e:
                out.append(f"-- {stmt}\nERROR: {e}")
result = "\n".join(out)
print(result)
dbutils.notebook.exit(result[:9000])
