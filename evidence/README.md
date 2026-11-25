# Execution evidence: real output from `fevm-aws-demo`

Everything here was captured from live runs on the workspace, as text. Nothing is mocked or hand-written.

| File | What it proves | Key results |
|---|---|---|
| `run_2_full_end_to_end/run_summary.md` | **One Lakeflow Job ran the whole journey: all 7 tasks SUCCESS** (job run `931556335206949`, ~10 min) | land → Lakeflow pipeline → GenAI → ML → queue + AI messages → governance → Lakebase sync |
| `run_2_full_end_to_end/land_raw_data.md` | Schemas, volumes and PII mask functions created; raw files landed | 5 schemas, 2 mask functions, 6 raw sources |
| `run_1_land_and_lakeflow/land_raw_data.md` | First run: the simulator generated the raw data | 64,642 players, 6.19M telemetry rows, 92K receipts, 27K tickets |
| `run_2_full_end_to_end/genai_ticket_insights.md` | Claude Haiku 5.5 (`ai_query`) classified every ticket | 27,395 tickets, 0 errors; negation handled ("not quitting lol" → no churn intent) |
| `run_2_full_end_to_end/train_and_score_churn_model.md` | Point-in-time features, out-of-time test, GenAI ablation, backtest, UC registration, scoring | AUC 0.886 vs 0.835 baseline; +78% net revenue retained vs status quo; model `@champion` |
| `run_2_full_end_to_end/retention_queue_and_ai_messages.md` | Next-best-action, Claude Sonnet 5.5 win-back drafts, guardrail | 200 drafts, **0 guardrail violations**; payment-issue whales get a fix, not an upsell |
| `run_2_full_end_to_end/unity_catalog_governance.md` | Tags, grants, masks in effect, responsible-monetization assertion, lineage, DQ results | **0** paid offers to minors or players without consent |
| `run_2_full_end_to_end/lakebase_sync_and_feedback.md` | Synced table refreshed Delta → Lakebase Postgres and verified | 43,874 = 43,874 rows; **3.1 ms** login lookup |
| `sql_checks.md` | 17 verification queries on the SQL warehouse | Layer row counts, DQ expectations (2,414 + 245 bad rows dropped), Season 7 churn spike, v7.2 crash spike, backtest tables, masks, policy, tags, lineage |
| `genie_conversations.md` | 6 real questions to the Genie space, with generated SQL and result rows | e.g. whale lapse 0.805% → 1.335%; low-tier crash spike after v7.2 |
| `lakebase_checks.md` | Postgres queries via the Lakebase admin job | App service-principal role exists; grants applied; 43,874 rows in Lakebase |
| `model_registry.md` | UC model registry entry | `aws_demo_catalog.playerpulse_ml.player_churn_risk`, alias `champion` |
| `app_check.md` | Databricks App deployed with Lakebase, SQL warehouse and Genie resources | App RUNNING, deployment SUCCEEDED |
