# Job run 931556335206949: [dev shuheng_pi] playerpulse-daily-refresh

- Run page: https://fevm-aws-demo.cloud.databricks.com/?o=7474659338788077#job/656922230388324/run/931556335206949
- Started: 2026-11-25 14:50:01 UTC  Ended: 2026-11-25 14:59:06 UTC
- Result: SUCCESS

| task | state | result | start | duration (s) |
|---|---|---|---|---|
| land_raw_data | TERMINATED | SUCCESS | 2026-11-25 14:50:01 UTC | 25 |
| lakeflow_pipeline | TERMINATED | SUCCESS | 2026-11-25 14:50:26 UTC | 62 |
| genai_ticket_insights | TERMINATED | SUCCESS | 2026-11-25 14:51:28 UTC | 47 |
| train_and_score_churn_model | TERMINATED | SUCCESS | 2026-11-25 14:52:16 UTC | 166 |
| retention_queue_and_ai_messages | TERMINATED | SUCCESS | 2026-11-25 14:55:02 UTC | 171 |
| lakebase_sync_and_feedback | TERMINATED | SUCCESS | 2026-11-25 14:57:54 UTC | 72 |
| unity_catalog_governance | TERMINATED | SUCCESS | 2026-11-25 14:57:54 UTC | 26 |
