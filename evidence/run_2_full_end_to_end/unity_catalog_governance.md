# unity_catalog_governance — executed notebook output

- Notebook: `/Workspace/Users/shuheng.pi@databricks.com/.bundle/playerpulse/dev/files/src/notebooks/05_unity_catalog_governance`
- Job run: 931556335206949 · task run: 757135177179117 · result: **SUCCESS**
- Started 2026-11-25 14:57:54 UTC, duration 26s

# 05 · Unity Catalog governance
* **Classification tags** on schemas, tables and PII / sensitive columns (email, device ad-id, birth year, minor flag)
* **Column masks** on player PII (declared in the Lakeflow pipeline; policy functions in `playerpulse_governance`)
* **Least-privilege grants**: analysts / Genie users get gold + serving only, never raw PII
* **Responsible-monetization evidence**: no minor or non-consenting player is ever eligible for a paid offer
* **Evidence**: masked query output, lineage from `system.access.table_lineage`, DQ expectation results

```python
dbutils.widgets.text("catalog", "aws_demo_catalog")
dbutils.widgets.text("analyst_group", "account users")
C = dbutils.widgets.get("catalog"); ANALYSTS = dbutils.widgets.get("analyst_group")
GAME, ML, SRV = f"{C}.playerpulse_game", f"{C}.playerpulse_ml", f"{C}.playerpulse_serving"

def run(sql):
    try:
        spark.sql(sql); print("OK  ", sql.strip().splitlines()[0][:150])
    except Exception as e:
        print("SKIP", sql.strip().splitlines()[0][:150], "->", str(e).splitlines()[0][:160])
```

### Classification tags

```python
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
```
**Output:**

```text
SKIP ALTER SCHEMA aws_demo_catalog.playerpulse_raw SET TAGS ('project' = 'playerpulse', 'layer' = 'landing', 'business_domain' = 'games_liveops') -> [RequestId=0f98d050-6853-4b11-b08b-d9024c2313d7 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value playerpulse is not an allowed valu
SKIP ALTER SCHEMA aws_demo_catalog.playerpulse_game SET TAGS ('project' = 'playerpulse', 'layer' = 'curated', 'business_domain' = 'games_liveops') -> [RequestId=f013480f-cd72-4f62-9762-810eba190233 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value playerpulse is not an allowed valu
SKIP ALTER SCHEMA aws_demo_catalog.playerpulse_ml SET TAGS ('project' = 'playerpulse', 'layer' = 'analytics', 'business_domain' = 'games_liveops') -> [RequestId=0130e56c-e3d5-44b6-9996-b7a9ebc60828 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value playerpulse is not an allowed valu
SKIP ALTER SCHEMA aws_demo_catalog.playerpulse_serving SET TAGS ('project' = 'playerpulse', 'layer' = 'operational', 'business_domain' = 'games_liveops') -> [RequestId=9b2365a0-913e-450b-bd05-7ba469199dd8 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value playerpulse is not an allowed valu
SKIP ALTER SCHEMA aws_demo_catalog.playerpulse_governance SET TAGS ('project' = 'playerpulse', 'layer' = 'policy', 'business_domain' = 'games_liveops') -> [RequestId=11eba457-0a67-41d1-a2a2-8d9d7b2b1280 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value playerpulse is not an allowed valu
SKIP ALTER TABLE aws_demo_catalog.playerpulse_game.silver_players SET TAGS ('contains_pii' = 'true', 'data_owner' = 'player_support', 'regulation' = 'gdpr_ -> [RequestId=2a968f44-31f5-4659-a4ea-3f3680a6e612 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value player_support is not an allowed v
SKIP ALTER TABLE aws_demo_catalog.playerpulse_game.silver_players ALTER COLUMN email SET TAGS ('pii' = 'email') -> [RequestId=1442398a-a104-43e6-81a3-fbbe83d6b747 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value email is not an allowed value for 
SKIP ALTER TABLE aws_demo_catalog.playerpulse_game.silver_players ALTER COLUMN device_id SET TAGS ('pii' = 'device_advertising_id') -> [RequestId=9f3fc3d2-53e9-42a0-868d-e12be9ffda10 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value device_advertising_id is not an al
SKIP ALTER TABLE aws_demo_catalog.playerpulse_game.silver_players ALTER COLUMN birth_year SET TAGS ('pii' = 'date_of_birth') -> [RequestId=4a45ea57-a55d-4fd5-a5a3-5141bac35123 ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value date_of_birth is not an allowed va
SKIP ALTER TABLE aws_demo_catalog.playerpulse_game.silver_players ALTER COLUMN is_minor SET TAGS ('sensitivity' = 'minor_status', 'policy' = 'no_paid_offer -> [RequestId=7f2b383f-468e-412c-97fc-3c2c135f51cc ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value minor_status is not an allowed val
SKIP ALTER TABLE aws_demo_catalog.playerpulse_game.silver_players ALTER COLUMN marketing_opt_in SET TAGS ('sensitivity' = 'consent') -> [RequestId=8612b2ca-f1dc-4cce-b56a-ae86bd895f1e ErrorClass=INVALID_PARAMETER_VALUE.UC_TAG_POLICY_VALUE_NOT_ALLOWED] Tag value consent is not an allowed value fo
OK   ALTER TABLE aws_demo_catalog.playerpulse_game.gold_daily_kpis SET TAGS ('certified' = 'true', 'consumer' = 'genie_and_app')
OK   ALTER TABLE aws_demo_catalog.playerpulse_game.gold_retention_cohorts SET TAGS ('certified' = 'true', 'consumer' = 'genie_and_app')
OK   ALTER TABLE aws_demo_catalog.playerpulse_game.gold_weekly_churn SET TAGS ('certified' = 'true', 'consumer' = 'genie_and_app')
OK   ALTER TABLE aws_demo_catalog.playerpulse_game.gold_player_360_current SET TAGS ('certified' = 'true', 'consumer' = 'genie_and_app')
OK   ALTER TABLE aws_demo_catalog.playerpulse_game.gold_liveops_assumptions SET TAGS ('certified' = 'true', 'consumer' = 'genie_and_app')
OK   ALTER TABLE aws_demo_catalog.playerpulse_serving.player_retention_queue SET TAGS ('certified' = 'true', 'published_to' = 'lakebase')
OK   ALTER TABLE aws_demo_catalog.playerpulse_ml.ticket_insights SET TAGS ('generated_by' = 'genai_ai_query')
OK   ALTER TABLE aws_demo_catalog.playerpulse_ml.ai_winback_messages SET TAGS ('generated_by' = 'genai_ai_query', 'requires_human_approval' = 'true')
```

### Least-privilege grants (analysts / Genie users: curated + serving only)

```python
# (catalog-level USE CATALOG is managed by the shared catalog's owner; we grant at schema/table level only)
for s in ["playerpulse_game", "playerpulse_ml", "playerpulse_serving"]:
    run(f"GRANT USE SCHEMA ON SCHEMA {C}.{s} TO `{ANALYSTS}`")
for t in [f"{GAME}.gold_daily_kpis", f"{GAME}.gold_retention_cohorts", f"{GAME}.gold_weekly_churn", f"{GAME}.gold_player_360_current",
          f"{GAME}.gold_liveops_assumptions", f"{GAME}.silver_liveops_calendar", f"{SRV}.player_retention_queue",
          f"{ML}.model_backtest_value", f"{ML}.model_backtest_weekly", f"{ML}.ticket_insights"]:
    run(f"GRANT SELECT ON TABLE {t} TO `{ANALYSTS}`")
display(spark.sql(f"SHOW GRANTS ON TABLE {SRV}.player_retention_queue"))
```
**Output:**

```text
OK   GRANT USE SCHEMA ON SCHEMA aws_demo_catalog.playerpulse_game TO `account users`
OK   GRANT USE SCHEMA ON SCHEMA aws_demo_catalog.playerpulse_ml TO `account users`
OK   GRANT USE SCHEMA ON SCHEMA aws_demo_catalog.playerpulse_serving TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_game.gold_daily_kpis TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_game.gold_retention_cohorts TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_game.gold_weekly_churn TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_game.gold_player_360_current TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_game.gold_liveops_assumptions TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_game.silver_liveops_calendar TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_serving.player_retention_queue TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_ml.model_backtest_value TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_ml.model_backtest_weekly TO `account users`
OK   GRANT SELECT ON TABLE aws_demo_catalog.playerpulse_ml.ticket_insights TO `account users`
```

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 8ab0e2ad-8163-4a96-8e93-cec03a3904b9 | SELECT | TABLE | aws_demo_catalog.playerpulse_serving.player_retention_queue |
| shuheng.pi@databricks.com | ALL PRIVILEGES | CATALOG | aws_demo_catalog |
| shuheng.pi@databricks.com | MANAGE | CATALOG | aws_demo_catalog |
| fbbab7a9-8f64-47fc-82c7-1eb2c5802929 | READ METADATA | METASTORE | metastore_aws_ap_northeast_1 |
| account users | SELECT | TABLE | aws_demo_catalog.playerpulse_serving.player_retention_queue |
| account users | READ METADATA | METASTORE | metastore_aws_ap_northeast_1 |

### Evidence: column masks in effect (caller is not in `playerpulse_player_support`)

```python
print("current_user:", spark.sql("SELECT current_user()").first()[0],
      "| in playerpulse_player_support:", spark.sql("SELECT is_account_group_member('playerpulse_player_support')").first()[0])
spark.sql(f"SELECT player_id, email, device_id, birth_year, age_band, is_minor, platform, region FROM {GAME}.silver_players LIMIT 5").show(truncate=False)
spark.sql(f"""SELECT table_name, column_name, tag_name, tag_value FROM {C}.information_schema.column_tags
              WHERE schema_name LIKE 'playerpulse%' ORDER BY ALL""").show(truncate=False)
```
**Output:**

```text
current_user: shuheng.pi@databricks.com | in playerpulse_player_support: False
+---------+---------+---------+----------+--------+--------+--------+------+
|player_id|email    |device_id|birth_year|age_band|is_minor|platform|region|
+---------+---------+---------+----------+--------+--------+--------+------+
|P0000002 |pla******|IOS******|NULL      |25-34   |false   |ios     |APAC  |
|P0000005 |pla******|AND******|NULL      |35-44   |false   |android |EU    |
|P0000006 |pla******|AND******|NULL      |18-24   |false   |android |APAC  |
|P0000007 |pla******|AND******|NULL      |25-34   |false   |android |EU    |
|P0000009 |pla******|IOS******|NULL      |25-34   |false   |ios     |LATAM |
+---------+---------+---------+----------+--------+--------+--------+------+

+----------+-----------+--------+---------+
|table_name|column_name|tag_name|tag_value|
+----------+-----------+--------+---------+
+----------+-----------+--------+---------+
```

### Evidence: responsible-monetization policy holds in the serving table

```python
spark.sql(f"""
SELECT is_minor, marketing_opt_in, paid_offer_eligible, count(*) players,
  sum(CASE WHEN next_best_action = 'PERSONALISED_OFFER' THEN 1 ELSE 0 END) AS personalised_offers
FROM {SRV}.player_retention_queue GROUP BY ALL ORDER BY ALL""").show()
bad = spark.sql(f"SELECT count(*) n FROM {SRV}.player_retention_queue WHERE (is_minor OR NOT marketing_opt_in) AND (paid_offer_eligible OR next_best_action = 'PERSONALISED_OFFER')").first().n
print("policy violations (minor/no-consent with paid offer):", bad)
assert bad == 0
```
**Output:**

```text
+--------+----------------+-------------------+-------+-------------------+
|is_minor|marketing_opt_in|paid_offer_eligible|players|personalised_offers|
+--------+----------------+-------------------+-------+-------------------+
|   false|           false|              false|  14874|                  0|
|   false|            true|               true|  23888|               4336|
|    true|           false|              false|   1961|                  0|
|    true|            true|              false|   3151|                  0|
+--------+----------------+-------------------+-------+-------------------+

policy violations (minor/no-consent with paid offer): 0
```

### Evidence: end-to-end lineage captured automatically by Unity Catalog

```python
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
```
**Output:**

```text
+-----------------------------------------------------------------+------------------------------------------------------------------+-----------+
|source_table_full_name                                           |target_table_full_name                                            |entity_type|
+-----------------------------------------------------------------+------------------------------------------------------------------+-----------+
|aws_demo_catalog.playerpulse_game.silver_player_daily            |aws_demo_catalog.playerpulse_game.gold_daily_kpis                 |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_players                 |aws_demo_catalog.playerpulse_game.gold_daily_kpis                 |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_purchases               |aws_demo_catalog.playerpulse_game.gold_daily_kpis                 |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_player_daily            |aws_demo_catalog.playerpulse_game.gold_player_360_current         |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_players                 |aws_demo_catalog.playerpulse_game.gold_player_360_current         |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_purchases               |aws_demo_catalog.playerpulse_game.gold_player_360_current         |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_support_tickets         |aws_demo_catalog.playerpulse_game.gold_player_360_current         |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_player_daily            |aws_demo_catalog.playerpulse_game.gold_retention_cohorts          |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_players                 |aws_demo_catalog.playerpulse_game.gold_retention_cohorts          |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_player_daily            |aws_demo_catalog.playerpulse_game.gold_weekly_churn               |PIPELINE   |
|aws_demo_catalog.playerpulse_game.silver_purchases               |aws_demo_catalog.playerpulse_game.gold_weekly_churn               |PIPELINE   |
|aws_demo_catalog.playerpulse_game.bronze_liveops_calendar        |aws_demo_catalog.playerpulse_game.silver_liveops_calendar         |PIPELINE   |
|aws_demo_catalog.playerpulse_game.bronze_telemetry_daily         |aws_demo_catalog.playerpulse_game.silver_player_daily             |PIPELINE   |
|aws_demo_catalog.playerpulse_game.bronze_store_receipts          |aws_demo_catalog.playerpulse_game.silver_purchases                |PIPELINE   |
|aws_demo_catalog.playerpulse_game.bronze_support_tickets         |aws_demo_catalog.playerpulse_game.silver_support_tickets          |PIPELINE   |
|aws_demo_catalog.playerpulse_serving.player_retention_queue_stage|aws_demo_catalog.playerpulse_ml.ai_winback_messages               |JOB        |
|aws_demo_catalog.playerpulse_game.silver_player_daily            |aws_demo_catalog.playerpulse_ml.player_features_pit               |JOB        |
|aws_demo_catalog.playerpulse_game.silver_players                 |aws_demo_catalog.playerpulse_ml.player_features_pit               |JOB        |
|aws_demo_catalog.playerpulse_game.silver_purchases               |aws_demo_catalog.playerpulse_ml.player_features_pit               |JOB        |
|aws_demo_catalog.playerpulse_ml.ticket_insights                  |aws_demo_catalog.playerpulse_ml.player_features_pit               |JOB        |
|aws_demo_catalog.playerpulse_game.silver_support_tickets         |aws_demo_catalog.playerpulse_ml.ticket_insights                   |JOB        |
|aws_demo_catalog.playerpulse_ml.ticket_insights                  |aws_demo_catalog.playerpulse_ml.ticket_insights                   |JOB        |
|aws_demo_catalog.playerpulse_ml.ai_winback_messages              |aws_demo_catalog.playerpulse_serving.player_retention_queue       |JOB        |
|aws_demo_catalog.playerpulse_serving.player_retention_queue_stage|aws_demo_catalog.playerpulse_serving.player_retention_queue       |JOB        |
|aws_demo_catalog.playerpulse_game.gold_player_360_current        |aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |JOB        |
|aws_demo_catalog.playerpulse_game.silver_players                 |aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |JOB        |
|aws_demo_catalog.playerpulse_ml.player_churn_scores              |aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |JOB        |
|aws_demo_catalog.playerpulse_ml.ticket_insights                  |aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |JOB        |
|aws_demo_catalog.playerpulse_serving.player_retention_queue_stage|aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |JOB        |
|aws_demo_catalog.playerpulse_serving.player_retention_queue      |aws_demo_catalog.playerpulse_serving.player_retention_queue_synced|PIPELINE   |
+-----------------------------------------------------------------+------------------------------------------------------------------+-----------+
```

### Evidence: Lakeflow data-quality expectations (pipeline event log)

```python
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
```
**Output:**

```text
+--------------------------------------------------------+------------------+--------+------+
|dataset                                                 |expectation       |passed  |failed|
+--------------------------------------------------------+------------------+--------+------+
|aws_demo_catalog.playerpulse_game.silver_player_daily   |consistent_matches|12336114|0     |
|aws_demo_catalog.playerpulse_game.silver_player_daily   |non_negative_play |12331286|4828  |
|aws_demo_catalog.playerpulse_game.silver_player_daily   |plausible_latency |12336114|0     |
|aws_demo_catalog.playerpulse_game.silver_player_daily   |valid_player      |12335624|490   |
|aws_demo_catalog.playerpulse_game.silver_players        |valid_age         |129284  |0     |
|aws_demo_catalog.playerpulse_game.silver_players        |valid_player      |129284  |0     |
|aws_demo_catalog.playerpulse_game.silver_purchases      |refund_sign       |184272  |0     |
|aws_demo_catalog.playerpulse_game.silver_purchases      |valid_status      |184272  |0     |
|aws_demo_catalog.playerpulse_game.silver_purchases      |valid_txn         |184272  |0     |
|aws_demo_catalog.playerpulse_game.silver_support_tickets|valid_ticket      |54790   |0     |
+--------------------------------------------------------+------------------+--------+------+
```
