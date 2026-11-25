"""Run verification queries on a SQL warehouse and write the results to evidence/sql_checks.md.
usage: python3 scripts/sql_evidence.py <profile> <warehouse_id> <catalog> <out.md>"""
import subprocess
import sys
import time

profile, wh, C, out = sys.argv[1:5]
G, M, S = f"{C}.playerpulse_game", f"{C}.playerpulse_ml", f"{C}.playerpulse_serving"
CHECKS = [
    ("Lakeflow: row counts per layer (dedup + expectations drop bad rows)", f"""
SELECT 'bronze_telemetry_daily' tbl, count(*) n FROM {G}.bronze_telemetry_daily UNION ALL
SELECT 'silver_player_daily', count(*) FROM {G}.silver_player_daily UNION ALL
SELECT 'silver_players', count(*) FROM {G}.silver_players UNION ALL
SELECT 'silver_purchases', count(*) FROM {G}.silver_purchases UNION ALL
SELECT 'silver_support_tickets', count(*) FROM {G}.silver_support_tickets UNION ALL
SELECT 'gold_player_360_current', count(*) FROM {G}.gold_player_360_current UNION ALL
SELECT 'ml.ticket_insights', count(*) FROM {M}.ticket_insights UNION ALL
SELECT 'ml.player_features_pit', count(*) FROM {M}.player_features_pit UNION ALL
SELECT 'serving.player_retention_queue', count(*) FROM {S}.player_retention_queue"""),
    ("Lakeflow: data-quality expectation results (pipeline event log)", f"""
WITH ev AS (SELECT explode(from_json(details:flow_progress:data_quality:expectations,
  'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) e
  FROM event_log(TABLE({G}.silver_player_daily)) WHERE event_type='flow_progress' AND details:flow_progress:data_quality IS NOT NULL)
SELECT e.dataset, e.name AS expectation, sum(e.passed_records) passed, sum(e.failed_records) failed FROM ev GROUP BY ALL ORDER BY 1, 2"""),
    ("Business problem: 14-day lapse rate by season and payer tier", f"""
SELECT CASE WHEN week_start < DATE'2026-06-02' THEN 'S6 Ashen Crown' WHEN week_start < DATE'2026-09-01' THEN 'S7 Rift Energy' ELSE 'S8 Ember Tide' END season,
  payer_tier, sum(active_players) player_weeks, sum(lapsed_14d) lapsed, round(sum(lapsed_14d) / sum(active_players), 4) lapse_rate_14d,
  round(sum(lapsed_spend_90d_usd), 0) lapsed_spend_90d_usd
FROM {G}.gold_weekly_churn GROUP BY ALL ORDER BY payer_tier, season"""),
    ("Title KPIs by month (DAU, net revenue, ARPDAU, crash rate)", f"""
SELECT date_format(kpi_date, 'yyyy-MM') month, round(sum(dau) / count(DISTINCT kpi_date)) avg_dau, round(sum(net_revenue_usd)) net_revenue_usd,
  round(sum(net_revenue_usd) / sum(dau), 3) arpdau_usd, round(sum(crashes) / sum(sessions), 4) crash_rate
FROM {G}.gold_daily_kpis GROUP BY 1 ORDER BY 1"""),
    ("Root cause: crash rate by device tier around client v7.2 (Aug 12) and hotfix v7.3 (Sep 24)", f"""
SELECT p.device_tier, CASE WHEN d.activity_date < DATE'2026-08-12' THEN '1 before v7.2' WHEN d.activity_date < DATE'2026-09-24' THEN '2 v7.2' ELSE '3 after v7.3' END period,
  round(sum(d.crashes) / sum(d.sessions), 4) crash_rate_per_session
FROM {G}.silver_player_daily d JOIN {G}.silver_players p USING (player_id) WHERE d.activity_date >= DATE'2026-07-01' GROUP BY ALL ORDER BY 1, 2"""),
    ("Retention cohorts (D1/D7/D30) by install month", f"""
SELECT date_format(cohort_week, 'yyyy-MM') install_month, sum(installs) installs, round(sum(d1_retention * installs) / sum(installs), 3) d1,
  round(sum(d7_retention * installs) / sum(installs), 3) d7, round(sum(d30_retention * installs) / sum(installs), 3) d30
FROM {G}.gold_retention_cohorts GROUP BY 1 ORDER BY 1"""),
    ("GenAI: ticket classification summary", f"""
SELECT category, count(*) tickets, round(avg(sentiment), 2) avg_sentiment, sum(CAST(churn_intent AS INT)) churn_intent,
  sum(CASE WHEN extraction_error IS NOT NULL THEN 1 ELSE 0 END) errors
FROM {M}.ticket_insights GROUP BY 1 ORDER BY 2 DESC"""),
    ("GenAI: sample classifications (slang, negation, multi-issue)", f"""
SELECT message, category, sentiment, churn_intent, severity, summary FROM {M}.ticket_insights
WHERE message RLIKE '(?i)not quitting|charged twice|cash grab|7.2|guild is leaving' ORDER BY ticket_id LIMIT 12"""),
    ("GenAI signal value: lapse rate when a ticket shows churn intent / payment issue (features table)", f"""
SELECT 'all active player-weeks' segment, count(*) n, round(avg(lapsed_14d), 4) lapse_rate FROM {M}.player_features_pit WHERE labeled UNION ALL
SELECT 'ai_churn_intent_28d = 1', count(*), round(avg(lapsed_14d), 4) FROM {M}.player_features_pit WHERE labeled AND ai_churn_intent_28d = 1 UNION ALL
SELECT 'ai_payment_issue_28d = 1', count(*), round(avg(lapsed_14d), 4) FROM {M}.player_features_pit WHERE labeled AND ai_payment_issue_28d = 1 UNION ALL
SELECT 'ai_toxicity_28d = 1', count(*), round(avg(lapsed_14d), 4) FROM {M}.player_features_pit WHERE labeled AND ai_toxicity_28d = 1"""),
    ("ML: backtest value vs. status-quo win-back (equal weekly capacity)", f"SELECT metric, value FROM {M}.model_backtest_value"),
    ("ML: weekly backtest detail", f"""
SELECT policy, date_format(as_of_date, 'yyyy-MM-dd') week, contacted, lapsers_reached, round(revenue_at_risk_reached) rev_at_risk_reached,
  round(expected_revenue_saved) expected_saved, round(offer_cost) offer_cost, round(total_revenue_at_risk) total_rev_at_risk
FROM {M}.model_backtest_weekly ORDER BY week, policy"""),
    ("Serving: retention queue by next-best-action", f"""
SELECT next_best_action, count(*) players, sum(CASE WHEN risk_tier='HIGH' THEN 1 ELSE 0 END) high_risk, round(sum(value_at_risk_usd), 2) revenue_at_risk_usd,
  sum(CASE WHEN paid_offer_eligible THEN 1 ELSE 0 END) offer_eligible
FROM {S}.player_retention_queue GROUP BY 1 ORDER BY 4 DESC"""),
    ("Serving: top 10 of the queue with reason codes and AI message", f"""
SELECT priority_rank, player_id, payer_tier, round(churn_prob_14d, 3) p14, round(value_at_risk_usd, 2) value_at_risk, next_best_action,
  top_drivers, last_ticket_summary, ai_message FROM {S}.player_retention_queue ORDER BY priority_rank LIMIT 10"""),
    ("Governance: masked PII as seen by a non-privileged user", f"SELECT player_id, email, device_id, birth_year, age_band, is_minor FROM {G}.silver_players LIMIT 5"),
    ("Governance: responsible-monetization policy (no paid offers to minors / no consent)", f"""
SELECT is_minor, marketing_opt_in, paid_offer_eligible, count(*) players, sum(CASE WHEN next_best_action='PERSONALISED_OFFER' THEN 1 ELSE 0 END) personalised_offers
FROM {S}.player_retention_queue GROUP BY ALL ORDER BY ALL"""),
    ("Governance: column tags", f"SELECT schema_name, table_name, column_name, tag_name, tag_value FROM {C}.information_schema.column_tags WHERE schema_name LIKE 'playerpulse%' ORDER BY ALL"),
    ("Governance: lineage captured by Unity Catalog", f"""
SELECT DISTINCT source_table_full_name, target_table_full_name FROM system.access.table_lineage
WHERE target_table_full_name LIKE '{C}.playerpulse%' AND source_table_full_name IS NOT NULL AND event_date >= current_date() - INTERVAL 7 DAYS
ORDER BY 2, 1"""),
]
lines = ["# SQL verification queries (real results from the Databricks SQL warehouse)", "",
         f"Captured {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} · warehouse `{wh}` · catalog `{C}`", ""]
here = __file__.rsplit("/", 1)[0]
for title, q in CHECKS:
    r = subprocess.run(["python3", "-I", f"{here}/sql.py", profile, wh, q.strip()], capture_output=True, text=True)
    lines += [f"## {title}", "", "```sql", q.strip(), "```", "", (r.stdout or r.stderr).strip(), ""]
    print("done:", title)
open(out, "w").write("\n".join(lines) + "\n")
