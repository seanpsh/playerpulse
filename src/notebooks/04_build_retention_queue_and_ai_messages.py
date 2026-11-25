# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Retention queue: next-best-action + GenAI win-back messages
# MAGIC One row per currently active player: lapse risk, revenue at risk, reason codes, latest GenAI ticket insight, and a
# MAGIC **root-cause next-best-action** (fix the problem first, discount last), and responsible-monetization guardrails:
# MAGIC minors and non-consenting players never receive paid offers.
# MAGIC For the top-N by revenue at risk, Claude drafts a player-facing in-game mail message and an internal rationale.
# MAGIC The result (`playerpulse_serving.player_retention_queue`) is synced to **Lakebase** for the LiveOps app and the game
# MAGIC backend (offer lookup at login).

# COMMAND ----------

dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("message_model", "databricks-claude-sonnet-5-5")
dbutils.widgets.text("n_messages", "200")
C = dbutils.widgets.get("catalog"); MODEL = dbutils.widgets.get("message_model"); N = int(dbutils.widgets.get("n_messages"))
GAME, ML, SRV = f"{C}.playerpulse_game", f"{C}.playerpulse_ml", f"{C}.playerpulse_serving"

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {SRV}.player_retention_queue_stage AS
WITH last_ticket AS (
  SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY player_id ORDER BY created_date DESC, ticket_id DESC) rn
                 FROM {ML}.ticket_insights WHERE created_date > date_sub((SELECT max(as_of_date) FROM {ML}.player_churn_scores), 28))
  WHERE rn = 1
),
j AS (
  SELECT s.player_id, s.as_of_date, s.churn_prob_14d, s.value_at_risk_usd, s.top_drivers, s.model_version,
    p.platform, p.device_tier, p.region, p.country_code, p.age_band, p.is_minor, p.marketing_opt_in, p.acquisition_channel,
    h.tenure_days, h.days_since_last_play, h.lifecycle_stage, h.active_days_7d, h.active_days_28d, h.minutes_7d,
    h.crashes_7d, h.energy_walls_7d, h.in_guild, h.level, h.client_version,
    h.lifetime_spend_usd, h.spend_90d_usd, h.payer_tier, h.tickets_28d,
    t.category AS last_ticket_category, t.summary AS last_ticket_summary, t.message AS last_ticket_message,
    t.churn_intent AS last_ticket_churn_intent, t.severity AS last_ticket_severity
  FROM {ML}.player_churn_scores s
  JOIN {GAME}.silver_players p USING (player_id)
  JOIN {GAME}.gold_player_360_current h USING (player_id)
  LEFT JOIN last_ticket t USING (player_id)
)
SELECT *,
  CASE WHEN churn_prob_14d >= 0.30 THEN 'HIGH' WHEN churn_prob_14d >= 0.10 THEN 'MEDIUM' ELSE 'LOW' END AS risk_tier,
  -- root-cause next-best-action: fix first, gift second, discount last
  CASE
    WHEN last_ticket_category = 'PAYMENT_ENTITLEMENT' THEN 'SUPPORT_ESCALATION'
    WHEN last_ticket_category = 'TOXICITY' THEN 'SAFETY_REVIEW'
    WHEN last_ticket_category = 'CRASH_BUG' OR crashes_7d >= 2 THEN 'TECH_FIX_AND_APOLOGY_GIFT'
    WHEN energy_walls_7d >= 3 OR last_ticket_category = 'ENERGY_ECONOMY' THEN 'ENERGY_REFILL_GIFT'
    WHEN NOT in_guild AND tenure_days < 60 THEN 'GUILD_MATCH_INVITE'
    WHEN spend_90d_usd > 0 AND NOT is_minor AND marketing_opt_in THEN 'PERSONALISED_OFFER'
    ELSE 'EVENT_REENGAGEMENT_PUSH' END AS next_best_action,
  (NOT is_minor AND marketing_opt_in) AS paid_offer_eligible
FROM j
""")
spark.sql(f"""
CREATE OR REPLACE TABLE {SRV}.player_retention_queue_stage AS
SELECT *, CAST(row_number() OVER (ORDER BY value_at_risk_usd DESC, churn_prob_14d DESC) AS INT) AS priority_rank,
       current_timestamp() AS refreshed_at
FROM {SRV}.player_retention_queue_stage
""")
spark.sql(f"""SELECT next_best_action, count(*) players, round(sum(value_at_risk_usd)) revenue_at_risk,
              sum(CASE WHEN risk_tier='HIGH' THEN 1 ELSE 0 END) high_risk
              FROM {SRV}.player_retention_queue_stage GROUP BY 1 ORDER BY 3 DESC""").show(truncate=False)

# COMMAND ----------

# MAGIC %md ### GenAI: draft in-game win-back messages for the top-N (policy-constrained)

# COMMAND ----------

PROMPT = """You write in-game mailbox messages for Emberline: Rift Tactics, a fantasy mobile RPG.
Write for ONE player using the JSON context. Rules (responsible monetization & privacy):
- Warm, specific to their situation, in the game's voice; max 55 words; no fake urgency, no countdowns, no guilt.
- Address the root cause in next_best_action first (e.g. confirm the purchase issue is being fixed and items restored;
  apologise for crashes and mention the fix; gift energy). Only mention a discount if next_best_action is PERSONALISED_OFFER.
- If paid_offer_eligible is false, never mention purchases, prices, discounts or the shop.
- Never mention personal data, spend amounts, risk scores, or that they might quit.
Then write a one-sentence internal rationale for the LiveOps manager citing the data.
Output exactly two lines:
MESSAGE: <player-facing text>
RATIONALE: <internal text>
CONTEXT: """

spark.sql(f"""
CREATE OR REPLACE TABLE {ML}.ai_winback_messages
COMMENT 'GenAI (ai_query) drafted in-game win-back messages + LiveOps rationale for the top-{N} players by revenue at risk. Drafts require human approval in the app.'
AS WITH gen AS (
  SELECT player_id, priority_rank, '{MODEL}' AS message_model, current_timestamp() AS generated_at,
    ai_query('{MODEL}', concat('{PROMPT.replace("'", "''")}', to_json(named_struct(
      'next_best_action', next_best_action, 'paid_offer_eligible', paid_offer_eligible, 'payer_tier', payer_tier,
      'risk_drivers', top_drivers, 'last_ticket_summary', last_ticket_summary, 'last_ticket_category', last_ticket_category,
      'in_guild', in_guild, 'level', level, 'device_tier', device_tier, 'client_version', client_version,
      'energy_walls_7d', energy_walls_7d, 'crashes_7d', crashes_7d, 'tenure_days', tenure_days))),
      failOnError => false) AS r
  FROM {SRV}.player_retention_queue_stage WHERE priority_rank <= {N}
)
SELECT player_id, priority_rank, message_model, generated_at,
  trim(regexp_extract(r.result, '(?s)MESSAGE:\\\\s*(.*?)\\\\s*RATIONALE:', 1)) AS ai_message,
  trim(regexp_extract(r.result, '(?s)RATIONALE:\\\\s*(.*)$', 1)) AS ai_rationale,
  r.errorMessage AS generation_error
FROM gen
""")
spark.sql(f"SELECT count(*) n, sum(CASE WHEN ai_message = '' OR ai_message IS NULL THEN 1 ELSE 0 END) empty FROM {ML}.ai_winback_messages").show()

# COMMAND ----------

# Guardrail check: no paid-offer language for ineligible players (minors / no consent)
viol = spark.sql(f"""
SELECT m.player_id, q.is_minor, q.marketing_opt_in, m.ai_message FROM {ML}.ai_winback_messages m
JOIN {SRV}.player_retention_queue_stage q USING (player_id)
WHERE NOT q.paid_offer_eligible AND m.ai_message RLIKE '(?i)discount|% off|\\\\$|price|sale|shop|bundle'""")
print("guardrail violations:", viol.count())
viol.show(truncate=100)
blocked = [r.player_id for r in viol.collect()]
if blocked:  # never publish a non-compliant draft
    spark.createDataFrame([(b,) for b in blocked], "player_id string").createOrReplaceTempView("blocked")
    spark.sql(f"UPDATE {ML}.ai_winback_messages SET ai_message = NULL, generation_error = 'blocked_by_guardrail' WHERE player_id IN (SELECT player_id FROM blocked)")

# COMMAND ----------

# MAGIC %md ### Publish: stable CDF-enabled table (MERGE keeps the Lakebase synced table incremental)

# COMMAND ----------

T = f"{SRV}.player_retention_queue"
spark.sql(f"""CREATE OR REPLACE TEMP VIEW publish AS
  SELECT s.*, m.ai_message, m.ai_rationale FROM {SRV}.player_retention_queue_stage s
  LEFT JOIN {ML}.ai_winback_messages m USING (player_id)""")
if not spark.catalog.tableExists(T):
    spark.sql(f"""CREATE TABLE {T}
      COMMENT 'Retention queue: one row per active player with 14-day lapse risk, revenue at risk, reason codes, GenAI ticket root cause, next-best-action, offer eligibility and AI-drafted message. Synced to Lakebase.'
      TBLPROPERTIES (delta.enableChangeDataFeed = true)
      AS SELECT * FROM publish""")
    spark.sql(f"ALTER TABLE {T} ALTER COLUMN player_id SET NOT NULL")
    spark.sql(f"ALTER TABLE {T} ADD CONSTRAINT pk_player_retention_queue PRIMARY KEY (player_id)")
else:
    spark.sql(f"""MERGE WITH SCHEMA EVOLUTION INTO {T} t USING publish s ON t.player_id = s.player_id
      WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *
      WHEN NOT MATCHED BY SOURCE THEN DELETE""")
print(spark.table(T).count(), "rows in", T)

# COMMAND ----------

for r in spark.sql(f"""SELECT priority_rank, player_id, payer_tier, round(churn_prob_14d,3) p, next_best_action, paid_offer_eligible,
                       top_drivers, last_ticket_summary, ai_message, ai_rationale FROM {T} WHERE ai_message IS NOT NULL
                       ORDER BY priority_rank LIMIT 5""").collect():
    print(f"#{r.priority_rank} {r.player_id} [{r.payer_tier}] p={r.p} action={r.next_best_action} offer_ok={r.paid_offer_eligible}")
    print(f"   drivers: {r.top_drivers} | last ticket: {r.last_ticket_summary}")
    print(f"   MESSAGE: {r.ai_message}\n   RATIONALE: {r.ai_rationale}\n")
