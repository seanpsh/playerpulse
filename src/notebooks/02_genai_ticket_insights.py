# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · GenAI: turn support tickets & in-game feedback into churn signals
# MAGIC Players write ~27K free-text tickets per season ("app closes mid match since 7.2", "charged twice for gem pack",
# MAGIC "energy system is a cash grab... uninstalling"). `ai_query` (Claude Haiku 5.5) classifies each one into a root-cause
# MAGIC category, sentiment, severity and **explicit churn intent** (handling negation like "not quitting lol").
# MAGIC The output feeds (1) churn-model features, (2) the **next-best-action** (fix the root cause, don't just discount),
# MAGIC and (3) Genie questions like "what are churning whales complaining about?". Incremental: only new tickets are sent.

# COMMAND ----------

dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("extraction_model", "databricks-claude-haiku-5-5")
C = dbutils.widgets.get("catalog"); MODEL = dbutils.widgets.get("extraction_model")
T = f"{C}.playerpulse_ml.ticket_insights"
print("catalog:", C, "| model:", MODEL)

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {T} (
  ticket_id STRING, player_id STRING, created_date DATE, channel STRING, message STRING,
  category STRING COMMENT 'CRASH_BUG | ENERGY_ECONOMY | MATCHMAKING_DIFFICULTY | PAYMENT_ENTITLEMENT | TOXICITY | ACCOUNT_HELP | POSITIVE_FEEDBACK | OTHER',
  sentiment INT COMMENT '-2 very negative .. +2 very positive',
  churn_intent BOOLEAN COMMENT 'Player explicitly signals quitting / uninstalling / stopping spend (negations excluded)',
  spend_stop_intent BOOLEAN COMMENT 'Player says they will stop spending',
  severity INT COMMENT '0 none, 1 low, 2 needs follow-up, 3 urgent (money lost, account at risk, unplayable)',
  summary STRING COMMENT '<= 15 word summary for LiveOps / support',
  extraction_model STRING, extracted_at TIMESTAMP, extraction_error STRING
) COMMENT 'GenAI (ai_query) root-cause classification of support tickets and in-game feedback. Feeds churn features, next-best-action and Genie.'
""")

# COMMAND ----------

PROMPT = """You triage player support tickets and in-game feedback for a free-to-play mobile RPG (Emberline: Rift Tactics).
Players use slang and shorthand (f2p = free to play, whales = big spenders, pls = please, 7.2 = client version).
Classify the message:
- category: exactly one of CRASH_BUG, ENERGY_ECONOMY, MATCHMAKING_DIFFICULTY, PAYMENT_ENTITLEMENT, TOXICITY,
  ACCOUNT_HELP, POSITIVE_FEEDBACK, OTHER. Billing problems, double charges, missing purchased items -> PAYMENT_ENTITLEMENT.
- sentiment: integer -2..2.
- churn_intent: true only if the player explicitly signals quitting, uninstalling, leaving for another game, or their guild
  leaving. Negations or jokes ("not quitting lol") -> false.
- spend_stop_intent: true if they say they will stop spending money.
- severity: 0 none, 1 low, 2 needs follow-up, 3 urgent (money taken without items, unplayable crash, harassment).
- summary: <= 15 words, neutral tone, no personal data.
Respond with ONLY a JSON object with keys category, sentiment, churn_intent, spend_stop_intent, severity, summary.
No prose, no code fences.
Message: """
SCHEMA = "category STRING, sentiment INT, churn_intent BOOLEAN, spend_stop_intent BOOLEAN, severity INT, summary STRING"

# Newer Claude models reject ai_query's forced-tool structured output (responseFormat), so we ask for strict JSON in
# the prompt and parse with from_json. Unparseable rows keep extraction_error and are retried on the next run.
spark.sql(f"DELETE FROM {T} WHERE extraction_error IS NOT NULL")
todo = spark.sql(f"SELECT count(*) n FROM {C}.playerpulse_game.silver_support_tickets s LEFT ANTI JOIN {T} f USING (ticket_id)").first().n
print("tickets to classify:", todo)

# COMMAND ----------

if todo > 0:
    spark.sql(f"""
    INSERT INTO {T}
    WITH todo AS (
      SELECT s.* FROM {C}.playerpulse_game.silver_support_tickets s LEFT ANTI JOIN {T} f USING (ticket_id)
    ),
    scored AS (
      SELECT *, ai_query('{MODEL}', concat('{PROMPT.replace("'", "''")}', message), failOnError => false) AS resp FROM todo
    ),
    parsed AS (SELECT *, from_json(regexp_extract(resp.result, '(?s)[{{].*[}}]', 0), '{SCHEMA}') AS r FROM scored)
    SELECT ticket_id, player_id, created_date, channel, message,
      upper(r.category), r.sentiment, r.churn_intent, r.spend_stop_intent, r.severity, r.summary,
      '{MODEL}', current_timestamp(),
      coalesce(resp.errorMessage, CASE WHEN r.category IS NULL THEN concat('unparsed: ', left(resp.result, 200)) END)
    FROM parsed
    """)

# COMMAND ----------

# MAGIC %md ### Results

# COMMAND ----------

spark.sql(f"""
SELECT count(*) tickets, sum(CASE WHEN extraction_error IS NOT NULL THEN 1 ELSE 0 END) errors,
  sum(CAST(churn_intent AS INT)) churn_intent, sum(CAST(spend_stop_intent AS INT)) spend_stop, round(avg(sentiment), 2) avg_sentiment
FROM {T}""").show()
spark.sql(f"SELECT category, count(*) n, round(avg(sentiment),2) sentiment, sum(CAST(churn_intent AS INT)) churn_intent FROM {T} GROUP BY 1 ORDER BY 2 DESC").show()

# COMMAND ----------

# Spot-check shorthand, negation and mixed messages
spark.sql(f"""
SELECT message, category, sentiment AS sent, churn_intent AS quit, severity AS sev, summary FROM {T}
WHERE message RLIKE '(?i)not quitting|charged twice|7.2|whales|cash grab|guild is leaving'
ORDER BY ticket_id LIMIT 14""").show(truncate=60)

# COMMAND ----------

# Where a keyword rule would get it wrong: "quit" keyword vs. LLM churn_intent
spark.sql(f"""
SELECT (message RLIKE '(?i)quit') AS keyword_quit, churn_intent AS llm_churn_intent, count(*) n
FROM {T} GROUP BY ALL ORDER BY ALL""").show()

# COMMAND ----------

# Root cause by week around the v7.2 crash regression (product insight, also available in Genie)
spark.sql(f"""
SELECT CAST(date_trunc('week', created_date) AS DATE) wk, count(*) tickets,
  sum(CASE WHEN category='CRASH_BUG' THEN 1 ELSE 0 END) crash, sum(CASE WHEN category='ENERGY_ECONOMY' THEN 1 ELSE 0 END) energy,
  sum(CASE WHEN category='PAYMENT_ENTITLEMENT' THEN 1 ELSE 0 END) payment, sum(CAST(churn_intent AS INT)) churn_intent
FROM {T} WHERE created_date >= DATE'2026-07-20' GROUP BY 1 ORDER BY 1""").show(20)
