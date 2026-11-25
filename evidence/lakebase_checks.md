# Lakebase checks (real Postgres output via the playerpulse-lakebase-admin job, run 133204637048798)

```text
-- SELECT rolname FROM pg_roles WHERE rolname = '8ab0e2ad-8163-4a96-8e93-cec03a3904b9'
rolname
8ab0e2ad-8163-4a96-8e93-cec03a3904b9
-- GRANT USAGE ON SCHEMA playerpulse_serving TO "8ab0e2ad-8163-4a96-8e93-cec03a3904b9"
GRANT
-- GRANT SELECT ON ALL TABLES IN SCHEMA playerpulse_serving TO "8ab0e2ad-8163-4a96-8e93-cec03a3904b9"
GRANT
-- ALTER DEFAULT PRIVILEGES IN SCHEMA playerpulse_serving GRANT SELECT ON TABLES TO "8ab0e2ad-8163-4a96-8e93-cec03a3904b9"
ALTER DEFAULT PRIVILEGES
-- SELECT count(*) AS rows_in_lakebase FROM playerpulse_serving.player_retention_queue_synced
rows_in_lakebase
43874
```

## App write path: interventions approved in the app UI (Lakebase OLTP)

```text
-- job run 1022406190104364
-- SELECT intervention_id, player_id, action, channel, status, round(churn_prob_14d::numeric,3) AS p14, round(value_at_risk_usd::numeric,2) AS value_at_risk, approved_by, created_at FROM ops.interventions ORDER BY intervention_id
intervention_id | player_id | action | channel | status | p14 | value_at_risk | approved_by | created_at
1 | P0046644 | PERSONALISED_OFFER | in_game_mail | APPROVED | 0.724 | 1432.91 | shuheng.pi@databricks.com | 2026-11-25 15:18:42.816798+00:00
-- SELECT usename, application_name, count(*) FROM pg_stat_activity WHERE datname = 'playerpulse' GROUP BY 1,2
usename | application_name | count
8ab0e2ad-8163-4a96-8e93-cec03a3904b9 | playerpulse | 1
shuheng.pi@databricks.com |  | 1
```
