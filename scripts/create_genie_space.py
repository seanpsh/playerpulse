"""Create (or update) the PlayerPulse Genie space via the Genie REST API.

usage: python3 scripts/create_genie_space.py <profile> <catalog> <warehouse_id> [space_id_to_update] [--with-interventions]
"""
import json
import subprocess
import sys
import uuid

args = [a for a in sys.argv[1:] if not a.startswith("--")]
profile, C, wh = args[0], args[1], args[2]
space_id = args[3] if len(args) > 3 else None

TABLES = sorted([
    f"{C}.playerpulse_game.gold_daily_kpis",
    f"{C}.playerpulse_game.gold_retention_cohorts",
    f"{C}.playerpulse_game.gold_weekly_churn",
    f"{C}.playerpulse_game.gold_player_360_current",
    f"{C}.playerpulse_game.gold_liveops_assumptions",
    f"{C}.playerpulse_game.silver_liveops_calendar",
    f"{C}.playerpulse_ml.ticket_insights",
    f"{C}.playerpulse_ml.model_backtest_value",
    f"{C}.playerpulse_serving.player_retention_queue",
] + ([f"{C}.playerpulse_serving.interventions_snapshot"] if "--with-interventions" in sys.argv else []))

INSTRUCTIONS = """You answer questions for Emberforge Studios' LiveOps, product and executive teams about the mobile RPG Emberline: Rift Tactics.
Definitions:
- DAU = distinct players active on a day (gold_daily_kpis.dau; grain is date x platform x device_tier x region, so sum across them for title level). Crash rate = sum(crashes)/sum(sessions) (never average crash_rate_per_session). ARPDAU = net revenue / DAU. ARPPU = net revenue / payers.
- Lapse / churn: a player active in the prior 7 days who does not play in the next 14 days. gold_weekly_churn has lapse_rate_14d by week_start and payer_tier.
  For a period, compute sum(lapsed_14d) / sum(active_players); do not average rates.
- Payer tiers by trailing 90-day net spend: non_payer (0), minnow (<$20), dolphin ($20-100), whale ($100+).
- Seasons and releases are in silver_liveops_calendar: Season 6 (Mar 1-Jun 1 2026), Season 7 "Rift Energy" (Jun 2-Aug 31, energy rework),
  Season 8 (from Sep 1). Client v7.2 (Aug 12) introduced a crash regression on low-tier Android devices, fixed in v7.3 (Sep 24).
- Retention cohorts: d1/d7/d30_retention in gold_retention_cohorts (share of installs active exactly N days after install).
- Risk queue: player_retention_queue.churn_prob_14d is the model's probability of lapsing in the next 14 days; value_at_risk_usd = probability x 90-day spend;
  next_best_action is the root-cause intervention; paid_offer_eligible is false for minors and players without marketing consent.
- ticket_insights holds GenAI classifications of support tickets (category, sentiment, churn_intent, severity, summary).
- model_backtest_value compares PlayerPulse to the status-quo win-back rule at equal weekly capacity.
- Never return emails, device ids or birth years. Round money to 2 decimals and rates to 3 decimals."""

SAMPLES = [
    "How did the 14-day lapse rate of whales change from Season 6 to Season 7?",
    "What are high-risk payers complaining about, by ticket category?",
    "What was the crash rate by device tier before and after client v7.2?",
    "Show weekly DAU and ARPDAU since March",
    "What is D7 retention by acquisition channel for cohorts since June?",
    "How much incremental revenue does PlayerPulse deliver versus the current win-back rule?",
]

EXAMPLES = [
    ("What was the 14-day lapse rate by payer tier per season?",
     f"""SELECT CASE WHEN week_start < DATE'2026-06-02' THEN 'Season 6' WHEN week_start < DATE'2026-09-01' THEN 'Season 7' ELSE 'Season 8' END AS season,
  payer_tier, sum(active_players) AS player_weeks, round(sum(lapsed_14d) / sum(active_players), 4) AS lapse_rate_14d
FROM {C}.playerpulse_game.gold_weekly_churn GROUP BY ALL ORDER BY season, payer_tier"""),
    ("Weekly ARPDAU for the whole title",
     f"""SELECT CAST(date_trunc('week', kpi_date) AS DATE) AS week, round(sum(net_revenue_usd) / sum(dau), 4) AS arpdau_usd, round(sum(dau) / 7) AS avg_dau
FROM {C}.playerpulse_game.gold_daily_kpis GROUP BY 1 ORDER BY 1"""),
]


def hid():
    return uuid.uuid4().hex


space = {
    "version": 1,
    "config": {"sample_questions": sorted([{"id": hid(), "question": [q]} for q in SAMPLES], key=lambda x: x["id"])},
    "data_sources": {"tables": [{"identifier": t} for t in TABLES]},
    "instructions": {
        "text_instructions": [{"id": hid(), "content": [INSTRUCTIONS]}],
        "example_question_sqls": sorted([{"id": hid(), "question": [q], "sql": [s]} for q, s in EXAMPLES], key=lambda x: x["id"]),
    },
}
body = {
    "title": "PlayerPulse · Player Retention (Emberline)",
    "description": "Ask about DAU, revenue, retention cohorts, weekly churn by payer tier, ticket root causes, the risk queue and PlayerPulse value. Governed UC tables; no player PII.",
    "warehouse_id": wh,
    "serialized_space": json.dumps(space),
}
verb, path = ("patch", f"/api/2.0/genie/spaces/{space_id}") if space_id else ("post", "/api/2.0/genie/spaces")
out = subprocess.run(["databricks", "-p", profile, "api", verb, path, "--json", json.dumps(body)], capture_output=True, text=True)
print(out.stdout or out.stderr)
