# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Unity Catalog governance
# MAGIC * **Classification tags** on schemas, tables and PII / sensitive columns (email, device ad-id, birth year, minor flag)
# MAGIC * **Column masks** on player PII (declared in the Lakeflow pipeline; policy functions in `playerpulse_governance`)
# MAGIC * **Least-privilege grants**: analysts / Genie users get gold + serving only, never raw PII
# MAGIC * **Responsible-monetization evidence**: no minor or non-consenting player is ever eligible for a paid offer
# MAGIC * **Evidence**: masked query output, lineage from `system.access.table_lineage`, DQ expectation results

# COMMAND ----------

dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("analyst_group", "account users")
C = dbutils.widgets.get("catalog"); ANALYSTS = dbutils.widgets.get("analyst_group")
GAME, ML, SRV = f"{C}.playerpulse_game", f"{C}.playerpulse_ml", f"{C}.playerpulse_serving"

def run(sql):
    try:
        spark.sql(sql); print("OK  ", sql.strip().splitlines()[0][:150])
    except Exception as e:
        print("SKIP", sql.strip().splitlines()[0][:150], "->", str(e).splitlines()[0][:160])

# COMMAND ----------

# MAGIC %md ### Classification tags

# COMMAND ----------

for s, tier in [("playerpulse_raw", "landing"), ("playerpulse_game", "curated"), ("playerpulse_ml", "analytics"),
                ("playerpulse_serving", "operational"), ("playerpulse_governance", "policy")]:
    run(f"ALTER SCHEMA {C}.{s} SET TAGS ('project' = 'playerpulse', 'layer' = '{tier}', 'business_domain' = 'games_liveops')")
run(f"ALTER TABLE {GAME}.silver_players SET TAGS ('contains_pii' = 'true', 'data_owner' = 'player_support', 'regulation' = 'gdpr_coppa')")
for col, tag in [("email", "email"), ("device_id", "device_advertising_id"), ("birth_year", "date_of_birth")]:
    run(f"ALTER TABLE {GAME}.silver_players ALTER COLUMN {col} SET TAGS ('pii' = '{tag}')")
run(f"ALTER TABLE {GAME}.silver_players ALTER COLUMN is_minor SET TAGS ('sensitivity' = 'minor_status', 'policy' = 'no_paid_offers')")
run(f"ALTER TABLE {GAME}.silver_players ALTER COLUMN marketing_opt_in SET TAGS ('sensitivity' = 'consent')")
for t in ["gold_daily_kpis", "gold_retention_cohorts", "gold_weekly_churn", "gold_player_360_current", "gold_liveops_assumptions"]:
    run(f"ALTER TABLE {GAME}.{t} SET TAGS ('certified' = 'true', 'consumer' = 'genie_and_app')")
run(f"ALTER TABLE {SRV}.player_retention_queue SET TAGS ('certified' = 'true', 'published_to' = 'lakebase')")
run(f"ALTER TABLE {ML}.ticket_insights SET TAGS ('generated_by' = 'genai_ai_query')")
run(f"ALTER TABLE {ML}.ai_winback_messages SET TAGS ('generated_by' = 'genai_ai_query', 'requires_human_approval' = 'true')")

# COMMAND ----------

# MAGIC %md ### Least-privilege grants (analysts / Genie users: curated + serving only)

# COMMAND ----------

# (catalog-level USE CATALOG is managed by the shared catalog's owner; we grant at schema/table level only)
for s in ["playerpulse_game", "playerpulse_ml", "playerpulse_serving"]:
    run(f"GRANT USE SCHEMA ON SCHEMA {C}.{s} TO `{ANALYSTS}`")
for t in [f"{GAME}.gold_daily_kpis", f"{GAME}.gold_retention_cohorts", f"{GAME}.gold_weekly_churn", f"{GAME}.gold_player_360_current",
          f"{GAME}.gold_liveops_assumptions", f"{GAME}.silver_liveops_calendar", f"{SRV}.player_retention_queue",
          f"{ML}.model_backtest_value", f"{ML}.model_backtest_weekly", f"{ML}.ticket_insights"]:
    run(f"GRANT SELECT ON TABLE {t} TO `{ANALYSTS}`")
display(spark.sql(f"SHOW GRANTS ON TABLE {SRV}.player_retention_queue"))

# COMMAND ----------

# MAGIC %md ### Evidence: column masks in effect (caller is not in `playerpulse_player_support`)

# COMMAND ----------

print("current_user:", spark.sql("SELECT current_user()").first()[0],
      "| in playerpulse_player_support:", spark.sql("SELECT is_account_group_member('playerpulse_player_support')").first()[0])
spark.sql(f"SELECT player_id, email, device_id, birth_year, age_band, is_minor, platform, region FROM {GAME}.silver_players LIMIT 5").show(truncate=False)
spark.sql(f"""SELECT table_name, column_name, tag_name, tag_value FROM {C}.information_schema.column_tags
              WHERE schema_name LIKE 'playerpulse%' ORDER BY ALL""").show(truncate=False)

# COMMAND ----------

# MAGIC %md ### Evidence: responsible-monetization policy holds in the serving table

# COMMAND ----------

spark.sql(f"""
SELECT is_minor, marketing_opt_in, paid_offer_eligible, count(*) players,
  sum(CASE WHEN next_best_action = 'PERSONALISED_OFFER' THEN 1 ELSE 0 END) AS personalised_offers
FROM {SRV}.player_retention_queue GROUP BY ALL ORDER BY ALL""").show()
bad = spark.sql(f"SELECT count(*) n FROM {SRV}.player_retention_queue WHERE (is_minor OR NOT marketing_opt_in) AND (paid_offer_eligible OR next_best_action = 'PERSONALISED_OFFER')").first().n
print("policy violations (minor/no-consent with paid offer):", bad)
assert bad == 0

# COMMAND ----------

# MAGIC %md ### Evidence: end-to-end lineage captured automatically by Unity Catalog

# COMMAND ----------

try:
    spark.sql(f"""
    SELECT DISTINCT source_table_full_name, target_table_full_name, entity_type
    FROM system.access.table_lineage
    WHERE (target_table_full_name LIKE '{C}.playerpulse%' OR source_table_full_name LIKE '{C}.playerpulse%')
      AND source_table_full_name IS NOT NULL AND target_table_full_name IS NOT NULL
      AND event_date >= current_date() - INTERVAL 7 DAYS
    ORDER BY target_table_full_name, source_table_full_name""").show(80, truncate=False)
except Exception as e:
    print("system.access.table_lineage unavailable:", str(e)[:160])

# COMMAND ----------

# MAGIC %md ### Evidence: Lakeflow data-quality expectations (pipeline event log)

# COMMAND ----------

try:
    spark.sql(f"""
    WITH ev AS (
      SELECT explode(from_json(details:flow_progress:data_quality:expectations,
             'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
      FROM event_log(TABLE({GAME}.silver_player_daily))
      WHERE event_type = 'flow_progress' AND details:flow_progress:data_quality IS NOT NULL
    )
    SELECT e.dataset, e.name AS expectation, sum(e.passed_records) passed, sum(e.failed_records) failed
    FROM ev GROUP BY ALL ORDER BY 1, 2""").show(40, truncate=False)
except Exception as e:
    print("event_log query failed:", str(e)[:200])
