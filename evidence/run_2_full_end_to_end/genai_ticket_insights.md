# genai_ticket_insights — executed notebook output

- Notebook: `/Workspace/Users/shuheng.pi@databricks.com/.bundle/playerpulse/dev/files/src/notebooks/02_genai_ticket_insights`
- Job run: 931556335206949 · task run: 567991319361336 · result: **SUCCESS**
- Started 2026-11-25 14:51:28 UTC, duration 47s

# 02 · GenAI: turn support tickets & in-game feedback into churn signals
Players write ~27K free-text tickets per season ("app closes mid match since 7.2", "charged twice for gem pack",
"energy system is a cash grab... uninstalling"). `ai_query` (Claude Haiku 5.5) classifies each one into a root-cause
category, sentiment, severity and **explicit churn intent** (handling negation like "not quitting lol").
The output feeds (1) churn-model features, (2) the **next-best-action** (fix the root cause, don't just discount),
and (3) Genie questions like "what are churning whales complaining about?". Incremental: only new tickets are sent.

```python
dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("extraction_model", "databricks-claude-haiku-5-5")
C = dbutils.widgets.get("catalog"); MODEL = dbutils.widgets.get("extraction_model")
T = f"{C}.playerpulse_ml.ticket_insights"
print("catalog:", C, "| model:", MODEL)
```
**Output:**

```text
catalog: aws_demo_catalog | model: databricks-claude-haiku-5-5
```

```python
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
```

```python
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
# sentiment/severity parsed as STRING then try_cast: a stray word ("neutral") must not null out the whole record
SCHEMA = "category STRING, sentiment STRING, churn_intent BOOLEAN, spend_stop_intent BOOLEAN, severity STRING, summary STRING"

# Newer Claude models reject ai_query's forced-tool structured output (responseFormat), so we ask for strict JSON in
# the prompt and parse with from_json. Unparseable rows keep extraction_error and are retried on the next run.
spark.sql(f"DELETE FROM {T} WHERE extraction_error IS NOT NULL")
todo = spark.sql(f"SELECT count(*) n FROM {C}.playerpulse_game.silver_support_tickets s LEFT ANTI JOIN {T} f USING (ticket_id)").first().n
print("tickets to classify:", todo)
```
**Output:**

```text
tickets to classify: 0
```

```python
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
      upper(r.category), try_cast(r.sentiment AS INT), r.churn_intent, r.spend_stop_intent, try_cast(r.severity AS INT), r.summary,
      '{MODEL}', current_timestamp(),
      coalesce(resp.errorMessage, CASE WHEN r.category IS NULL THEN concat('unparsed: ', left(resp.result, 200)) END)
    FROM parsed
    """)
```

### Results

```python
spark.sql(f"""
SELECT count(*) tickets, sum(CASE WHEN extraction_error IS NOT NULL THEN 1 ELSE 0 END) errors,
  sum(CAST(churn_intent AS INT)) churn_intent, sum(CAST(spend_stop_intent AS INT)) spend_stop, round(avg(sentiment), 2) avg_sentiment
FROM {T}""").show()
spark.sql(f"SELECT category, count(*) n, round(avg(sentiment),2) sentiment, sum(CAST(churn_intent AS INT)) churn_intent FROM {T} GROUP BY 1 ORDER BY 2 DESC").show()
```
**Output:**

```text
+-------+------+------------+----------+-------------+
|tickets|errors|churn_intent|spend_stop|avg_sentiment|
+-------+------+------------+----------+-------------+
|  27395|     0|        2463|       492|        -0.76|
+-------+------+------------+----------+-------------+

+--------------------+----+---------+------------+
|            category|   n|sentiment|churn_intent|
+--------------------+----+---------+------------+
|           CRASH_BUG|8918|    -1.36|         589|
|      ENERGY_ECONOMY|5374|    -1.51|         520|
|        ACCOUNT_HELP|3321|    -0.03|         100|
|               OTHER|3197|    -0.45|          89|
|   POSITIVE_FEEDBACK|3094|     1.96|          75|
| PAYMENT_ENTITLEMENT|1628|    -1.59|         666|
|MATCHMAKING_DIFFI...|1052|     -1.1|          58|
|            TOXICITY| 811|    -1.56|         366|
+--------------------+----+---------+------------+
```

```python
# Spot-check shorthand, negation and mixed messages
spark.sql(f"""
SELECT message, category, sentiment AS sent, churn_intent AS quit, severity AS sev, summary FROM {T}
WHERE message RLIKE '(?i)not quitting|charged twice|7.2|whales|cash grab|guild is leaving'
ORDER BY ticket_id LIMIT 14""").show(truncate=60)
```
**Output:**

```text
+------------------------------------------------------------+-------------------+----+-----+---+------------------------------------------------------------+
|                                                     message|           category|sent| quit|sev|                                                     summary|
+------------------------------------------------------------+-------------------+----+-----+---+------------------------------------------------------------+
|Charged twice for gem pack, want refund not spending anot...|PAYMENT_ENTITLEMENT|  -2|false|  3|Player reports being charged twice for a gem pack, reques...|
|     not quitting lol just wondering when next season starts|              OTHER|   0|false|  1|Player asks when the next season starts; explicitly not q...|
|APP CLOSES MID MATCH SINCE 7.2, LOST 3 RANKED GAMES IN A ROW|          CRASH_BUG|  -2|false|  3|App crashes mid-match since client 7.2; player lost three...|
|     Not quitting lol just wondering when next season starts|              OTHER|   0|false|  1|Player asks when the next season starts and says they are...|
|Charged twice for gem pack, want refund probably moving t...|PAYMENT_ENTITLEMENT|  -2| true|  3|Player reports being charged twice for a gem pack and req...|
|     Not quitting lol just wondering when next season starts|              OTHER|   0|false|  1|Player asks when the next season starts; explicitly not q...|
|App closes mid match since 7.2, lost 3 ranked games in a row|          CRASH_BUG|  -1|false|  3|App crashes mid-match since client version 7.2, causing c...|
|                     charged twice for gem pack, want refund|PAYMENT_ENTITLEMENT|  -1|false|  3|Player reports double charge for gem pack and requests a ...|
|app closes mid match since 7.2, lost 3 ranked games in a row|          CRASH_BUG|  -1|false|  2|App closes mid-match since client version 7.2; player los...|
|     Not quitting lol just wondering when next season starts|              OTHER|   0|false|  1|Player asks when the next season starts and says they are...|
|     NOT QUITTING LOL JUST WONDERING WHEN NEXT SEASON STARTS|              OTHER|   0|false|  0|Player asks when the next season starts and says they are...|
|     not quitting lol just wondering when next season starts|              OTHER|   0|false|  1|Player asks when the next season starts and states they a...|
|bought the season pass but didnt get the rewards my whole...|PAYMENT_ENTITLEMENT|  -2| true|  3|Player bought season pass but did not receive rewards; re...|
|     not quitting lol just wondering when next season starts|              OTHER|   0|false|  1|Player asks when the next season starts; states they are ...|
+------------------------------------------------------------+-------------------+----+-----+---+------------------------------------------------------------+
```

```python
# Where a keyword rule would get it wrong: "quit" keyword vs. LLM churn_intent
spark.sql(f"""
SELECT (message RLIKE '(?i)quit') AS keyword_quit, churn_intent AS llm_churn_intent, count(*) n
FROM {T} GROUP BY ALL ORDER BY ALL""").show()
```
**Output:**

```text
+------------+----------------+-----+
|keyword_quit|llm_churn_intent|    n|
+------------+----------------+-----+
|       false|           false|23374|
|       false|            true| 1927|
|        true|           false| 1558|
|        true|            true|  536|
+------------+----------------+-----+
```

```python
# Root cause by week around the v7.2 crash regression (product insight, also available in Genie)
spark.sql(f"""
SELECT CAST(date_trunc('week', created_date) AS DATE) wk, count(*) tickets,
  sum(CASE WHEN category='CRASH_BUG' THEN 1 ELSE 0 END) crash, sum(CASE WHEN category='ENERGY_ECONOMY' THEN 1 ELSE 0 END) energy,
  sum(CASE WHEN category='PAYMENT_ENTITLEMENT' THEN 1 ELSE 0 END) payment, sum(CAST(churn_intent AS INT)) churn_intent
FROM {T} WHERE created_date >= DATE'2026-07-20' GROUP BY 1 ORDER BY 1""").show(20)
```
**Output:**

```text
+----------+-------+-----+------+-------+------------+
|        wk|tickets|crash|energy|payment|churn_intent|
+----------+-------+-----+------+-------+------------+
|2026-07-20|    973|  190|   420|     61|          95|
|2026-07-27|    876|  184|   381|     39|          94|
|2026-08-03|    804|  158|   389|     26|          88|
|2026-08-10|   1112|  348|   425|     49|         153|
|2026-08-17|   1161|  416|   408|     37|         175|
|2026-08-24|   1026|  357|   394|     38|         156|
|2026-08-31|    831|  385|    51|     59|         116|
|2026-09-07|    875|  453|     0|     55|         110|
|2026-09-14|   1015|  536|     0|     58|          88|
|2026-09-21|    932|  398|     0|     73|          70|
|2026-09-28|    704|  239|     0|     59|          35|
|2026-10-05|    773|  264|     0|     52|          40|
|2026-10-12|    771|  270|     0|     40|          43|
|2026-10-19|    749|  242|     0|     48|          44|
|2026-10-26|    667|  222|     0|     42|          37|
+----------+-------+-----+------+-------+------------+
```
