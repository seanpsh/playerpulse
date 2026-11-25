#!/usr/bin/env bash
# One-time wiring of Lakebase, the synced table, the Databricks App and its grants.
# Run after the first successful job run through `retention_queue_and_ai_messages`.
# usage: scripts/setup_lakebase_and_app.sh <profile> <catalog> <warehouse_id> <genie_space_id>
set -euo pipefail
P=$1; C=$2; WH=$3; GENIE=${4:-}
INST=playerpulse-lakebase; DB=playerpulse; APP=playerpulse
HERE=$(cd "$(dirname "$0")" && pwd)

# 1. Lakebase instance + Postgres database (created through the admin job; direct PG access from laptops may be blocked)
databricks -p "$P" database get-database-instance $INST >/dev/null 2>&1 || \
  databricks -p "$P" database create-database-instance $INST --capacity CU_1
python3 "$HERE/pg_admin.py" "$P" databricks_postgres "CREATE DATABASE $DB"

# 2. Synced table: Delta retention queue (CDF) -> Lakebase Postgres, triggered refresh (job task 06 triggers it)
databricks -p "$P" database get-synced-database-table "$C.playerpulse_serving.player_retention_queue_synced" >/dev/null 2>&1 || \
databricks -p "$P" database create-synced-database-table --json "{
  \"name\": \"$C.playerpulse_serving.player_retention_queue_synced\",
  \"database_instance_name\": \"$INST\",
  \"logical_database_name\": \"$DB\",
  \"spec\": {\"source_table_full_name\": \"$C.playerpulse_serving.player_retention_queue\",
           \"primary_key_columns\": [\"player_id\"],
           \"scheduling_policy\": \"TRIGGERED\",
           \"create_database_objects_if_missing\": true}}"

# 3. App with resources (Lakebase database, SQL warehouse, Genie space)
RES="[{\"name\":\"lakebase\",\"database\":{\"instance_name\":\"$INST\",\"database_name\":\"$DB\",\"permission\":\"CAN_CONNECT_AND_CREATE\"}},{\"name\":\"sql-warehouse\",\"sql_warehouse\":{\"id\":\"$WH\",\"permission\":\"CAN_USE\"}}"
[ -n "$GENIE" ] && RES="$RES,{\"name\":\"genie-space\",\"genie_space\":{\"name\":\"PlayerPulse\",\"space_id\":\"$GENIE\",\"permission\":\"CAN_RUN\"}}"
RES="$RES]"
databricks -p "$P" apps get $APP >/dev/null 2>&1 || databricks -p "$P" apps create --json "{\"name\":\"$APP\",\"description\":\"PlayerPulse LiveOps retention console (synthetic data)\"}"
databricks -p "$P" apps update $APP --json "{\"name\":\"$APP\",\"resources\":$RES}"
SP=$(databricks -p "$P" apps get $APP -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['service_principal_client_id'])")

# 4. UC grants for the app service principal (Genie runs as the SP): curated tables only, never raw PII
for stmt in \
  "GRANT USE CATALOG ON CATALOG $C TO \`$SP\`" \
  "GRANT USE SCHEMA ON SCHEMA $C.playerpulse_game TO \`$SP\`" \
  "GRANT USE SCHEMA ON SCHEMA $C.playerpulse_ml TO \`$SP\`" \
  "GRANT USE SCHEMA ON SCHEMA $C.playerpulse_serving TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_game.gold_daily_kpis TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_game.gold_retention_cohorts TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_game.gold_weekly_churn TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_game.gold_player_360_current TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_game.gold_liveops_assumptions TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_game.silver_liveops_calendar TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_ml.ticket_insights TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_ml.model_backtest_value TO \`$SP\`" \
  "GRANT SELECT ON TABLE $C.playerpulse_serving.player_retention_queue TO \`$SP\`"; do
  python3 "$HERE/sql.py" "$P" "$WH" "$stmt"
done

# 5. Postgres grants: app SP reads the synced serving schema (it owns its own ops schema)
python3 "$HERE/pg_admin.py" "$P" "$DB" "GRANT USAGE ON SCHEMA playerpulse_serving TO \"$SP\";; GRANT SELECT ON ALL TABLES IN SCHEMA playerpulse_serving TO \"$SP\";; ALTER DEFAULT PRIVILEGES IN SCHEMA playerpulse_serving GRANT SELECT ON TABLES TO \"$SP\""

# 6. Deploy app source (uploaded by `bundle deploy` to the bundle files path)
ROOT=$(databricks -p "$P" bundle validate -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['workspace']['file_path'])")
databricks -p "$P" apps deploy $APP --source-code-path "$ROOT/app"
