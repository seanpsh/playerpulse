# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · ML: 14-day lapse (churn) model for active players
# MAGIC * **Point-in-time weekly snapshots** (Sundays): only data on/before each `as_of_date` is used. Population = players
# MAGIC   active in the prior 7 days.
# MAGIC * **Features**: engagement level & trend, win/loss, energy walls (Season 7 economy), crashes, latency, guild,
# MAGIC   spend recency/monetary, tenure, device, and **GenAI ticket signals** (root cause, churn intent, severity).
# MAGIC * **Label**: no play in the next 14 days.
# MAGIC * **Out-of-time validation**: train on snapshots to 19-Jul-2026, test on 9-Aug → 11-Oct-2026 (3-week gap, no label overlap).
# MAGIC * **Business backtest** vs. the studio's current win-back rule ("payers quiet for 3+ days, highest spend first")
# MAGIC   at the same weekly LiveOps capacity.
# MAGIC * Registered in **Unity Catalog** as `<catalog>.playerpulse_ml.player_churn_risk@champion`; scores the active base with reason codes.

# COMMAND ----------

# MAGIC %pip install --quiet "mlflow>=2.20" "scikit-learn>=1.4,<1.7"
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "aws_demo_catalog")
C = dbutils.widgets.get("catalog")
GAME, ML = f"{C}.playerpulse_game", f"{C}.playerpulse_ml"

import json, numpy as np, pandas as pd, mlflow
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

A = {r.assumption: float(r.value) for r in spark.table(f"{GAME}.gold_liveops_assumptions").collect()}
K = int(A["weekly_intervention_capacity"])
asof_max = spark.sql(f"SELECT max(activity_date) d FROM {GAME}.silver_player_daily").first().d
print("data as of:", asof_max, "| weekly capacity:", K, "| assumptions:", A)

# COMMAND ----------

# MAGIC %md ### Point-in-time feature snapshots

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW snapshots AS
SELECT explode(sequence(DATE'2026-04-05', DATE'2026-10-11', INTERVAL 7 DAY)) AS as_of_date, true AS labeled
UNION ALL SELECT DATE'{asof_max}', false
""")

features_sql = f"""
WITH act28 AS (
  SELECT s.as_of_date, s.labeled, d.player_id,
    count(*) AS active_days_28d,
    sum(CASE WHEN d.activity_date > date_sub(s.as_of_date, 7) THEN 1 ELSE 0 END) AS active_days_7d,
    datediff(s.as_of_date, max(d.activity_date)) AS days_since_last_play,
    sum(d.minutes_played) AS minutes_28d,
    sum(CASE WHEN d.activity_date > date_sub(s.as_of_date, 7) THEN d.minutes_played ELSE 0 END) AS minutes_7d,
    sum(d.matches) AS matches_28d,
    sum(d.wins) / greatest(sum(d.matches), 1) AS win_rate_28d,
    sum(CASE WHEN d.activity_date > date_sub(s.as_of_date, 7) THEN d.wins ELSE 0 END)
      / greatest(sum(CASE WHEN d.activity_date > date_sub(s.as_of_date, 7) THEN d.matches ELSE 0 END), 1) AS win_rate_7d,
    sum(d.energy_walls) AS energy_walls_28d,
    sum(CASE WHEN d.activity_date > date_sub(s.as_of_date, 7) THEN d.energy_walls ELSE 0 END) AS energy_walls_7d,
    sum(d.crashes) AS crashes_28d,
    sum(CASE WHEN d.activity_date > date_sub(s.as_of_date, 7) THEN d.crashes ELSE 0 END) AS crashes_7d,
    avg(d.avg_latency_ms) AS latency_28d,
    max_by(CAST(d.in_guild AS INT), d.activity_date) AS in_guild,
    max(d.max_level) AS level
  FROM snapshots s JOIN {GAME}.silver_player_daily d
    ON d.activity_date <= s.as_of_date AND d.activity_date > date_sub(s.as_of_date, 28)
  GROUP BY ALL
  HAVING days_since_last_play < 7
),
spend AS (
  SELECT s.as_of_date, p.player_id,
    sum(CASE WHEN p.purchase_date > date_sub(s.as_of_date, 90) THEN p.amount_usd ELSE 0 END) AS spend_90d,
    sum(CASE WHEN p.purchase_date > date_sub(s.as_of_date, 28) THEN p.amount_usd ELSE 0 END) AS spend_28d,
    sum(p.amount_usd) AS lifetime_spend,
    datediff(s.as_of_date, max(p.purchase_date)) AS days_since_purchase,
    sum(CASE WHEN p.purchase_date > date_sub(s.as_of_date, 90) AND p.sku = 'season_pass' THEN 1 ELSE 0 END) AS season_pass_90d
  FROM snapshots s JOIN {GAME}.silver_purchases p ON p.purchase_date <= s.as_of_date
  GROUP BY ALL
),
tix AS (
  SELECT s.as_of_date, t.player_id,
    count(*) AS tickets_28d,
    max(CAST(t.churn_intent AS INT)) AS ai_churn_intent_28d,
    max(CAST(t.spend_stop_intent AS INT)) AS ai_spend_stop_28d,
    max(CASE WHEN t.category = 'PAYMENT_ENTITLEMENT' THEN 1 ELSE 0 END) AS ai_payment_issue_28d,
    max(CASE WHEN t.category = 'CRASH_BUG' THEN 1 ELSE 0 END) AS ai_crash_ticket_28d,
    max(CASE WHEN t.category = 'ENERGY_ECONOMY' THEN 1 ELSE 0 END) AS ai_energy_complaint_28d,
    max(CASE WHEN t.category = 'TOXICITY' THEN 1 ELSE 0 END) AS ai_toxicity_28d,
    min(t.sentiment) AS ai_min_sentiment_28d,
    max(t.severity) AS ai_max_severity_28d
  FROM snapshots s JOIN {ML}.ticket_insights t
    ON t.created_date <= s.as_of_date AND t.created_date > date_sub(s.as_of_date, 28)
  GROUP BY ALL
),
fut AS (
  SELECT DISTINCT s.as_of_date, d.player_id
  FROM snapshots s JOIN {GAME}.silver_player_daily d
    ON s.labeled AND d.activity_date > s.as_of_date AND d.activity_date <= date_add(s.as_of_date, 14)
)
SELECT a.*, datediff(a.as_of_date, p.install_date) AS tenure_days,
  CASE WHEN p.platform = 'android' THEN 1 ELSE 0 END AS is_android,
  CASE WHEN p.device_tier = 'low' THEN 1 ELSE 0 END AS is_low_tier_device,
  CASE WHEN p.acquisition_channel = 'paid_ua' THEN 1 ELSE 0 END AS is_paid_ua,
  p.is_minor, p.marketing_opt_in, p.region,
  coalesce(sp.spend_90d, 0) AS spend_90d, coalesce(sp.spend_28d, 0) AS spend_28d, coalesce(sp.lifetime_spend, 0) AS lifetime_spend,
  sp.days_since_purchase, coalesce(sp.season_pass_90d, 0) AS season_pass_90d,
  coalesce(t.tickets_28d, 0) AS tickets_28d,
  coalesce(t.ai_churn_intent_28d, 0) AS ai_churn_intent_28d, coalesce(t.ai_spend_stop_28d, 0) AS ai_spend_stop_28d,
  coalesce(t.ai_payment_issue_28d, 0) AS ai_payment_issue_28d, coalesce(t.ai_crash_ticket_28d, 0) AS ai_crash_ticket_28d,
  coalesce(t.ai_energy_complaint_28d, 0) AS ai_energy_complaint_28d, coalesce(t.ai_toxicity_28d, 0) AS ai_toxicity_28d,
  coalesce(t.ai_min_sentiment_28d, 0) AS ai_min_sentiment_28d, coalesce(t.ai_max_severity_28d, 0) AS ai_max_severity_28d,
  CASE WHEN a.labeled THEN CASE WHEN f.player_id IS NULL THEN 1 ELSE 0 END END AS lapsed_14d
FROM act28 a
JOIN {GAME}.silver_players p USING (player_id)
LEFT JOIN spend sp USING (as_of_date, player_id)
LEFT JOIN tix t USING (as_of_date, player_id)
LEFT JOIN fut f USING (as_of_date, player_id)
"""
spark.sql(f"CREATE OR REPLACE TABLE {ML}.player_features_pit COMMENT 'Point-in-time weekly feature snapshots of active players + 14-day lapse label (training) and current snapshot (scoring)' AS {features_sql}")
fs = spark.table(f"{ML}.player_features_pit")
display(fs.groupBy("labeled").agg({"*": "count", "lapsed_14d": "avg"}))

# COMMAND ----------

pdf = fs.toPandas()
pdf["trend_7d_vs_28d"] = pdf.active_days_7d / (pdf.active_days_28d / 4.0)
pdf["minutes_per_day_7d"] = pdf.minutes_7d / pdf.active_days_7d.clip(lower=1)
FEATURES = ["active_days_28d", "active_days_7d", "days_since_last_play", "minutes_28d", "minutes_7d", "matches_28d",
            "win_rate_28d", "win_rate_7d", "energy_walls_28d", "energy_walls_7d", "crashes_28d", "crashes_7d", "latency_28d",
            "in_guild", "level", "tenure_days", "is_android", "is_low_tier_device", "is_paid_ua",
            "spend_90d", "spend_28d", "lifetime_spend", "days_since_purchase", "season_pass_90d",
            "trend_7d_vs_28d", "minutes_per_day_7d", "tickets_28d",
            "ai_churn_intent_28d", "ai_spend_stop_28d", "ai_payment_issue_28d", "ai_crash_ticket_28d",
            "ai_energy_complaint_28d", "ai_toxicity_28d", "ai_min_sentiment_28d", "ai_max_severity_28d"]
AI_FEATURES = [f for f in FEATURES if f.startswith("ai_")]
pdf[FEATURES] = pdf[FEATURES].astype(float)
pdf["as_of_date"] = pd.to_datetime(pdf.as_of_date)
lab = pdf[pdf.labeled == True].copy()
train = lab[lab.as_of_date <= "2026-07-19"]
test = lab[lab.as_of_date >= "2026-08-09"].copy()
print(f"train rows {len(train):,} (lapse rate {train.lapsed_14d.mean():.3%}) | test rows {len(test):,} (lapse rate {test.lapsed_14d.mean():.3%})")

# COMMAND ----------

# MAGIC %md ### Train (out-of-time), evaluate, ablate GenAI features, backtest vs. status-quo win-back

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
user = spark.sql("SELECT current_user() u").first().u
mlflow.set_experiment(f"/Users/{user}/playerpulse_churn")
PARAMS = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0, random_state=11)
NO_AI = [f for f in FEATURES if f not in AI_FEATURES]

def weekly_program(df, policy):
    """Simulate one weekly LiveOps program at capacity K. Eligible: not minors (responsible monetization)."""
    rows = []
    for d, g in df[df.is_minor == False].groupby("as_of_date"):
        if policy == "status_quo":   # payers quiet for 3+ days, biggest spenders first
            pick = g[(g.days_since_last_play >= 3) & (g.spend_90d > 0)].nlargest(K, "spend_90d")
        else:                        # PlayerPulse: expected revenue at risk = P(lapse) x 90-day spend (+ small LTV floor)
            pick = g.assign(v=g[policy] * (g.spend_90d + 0.50)).nlargest(K, "v")
        lapsers = pick[pick.lapsed_14d == 1]
        save = np.where(lapsers.days_since_last_play < 3, A["save_rate_proactive"], A["save_rate_reactive"])
        rows.append(dict(as_of_date=d, contacted=len(pick), lapsers_reached=len(lapsers),
                         payer_lapsers_reached=int((lapsers.spend_90d > 0).sum()),
                         revenue_at_risk_reached=float(lapsers.spend_90d.sum()),
                         expected_players_saved=float(save.sum()),
                         expected_revenue_saved=float((save * lapsers.spend_90d * A["forward_revenue_multiplier"]).sum()),
                         offer_cost=len(pick) * A["offer_cost_usd"],
                         total_payer_lapsers=int(((g.lapsed_14d == 1) & (g.spend_90d > 0)).sum()),
                         total_revenue_at_risk=float(g[g.lapsed_14d == 1].spend_90d.sum())))
    return pd.DataFrame(rows)

with mlflow.start_run(run_name="hgb_oot_validation") as run:
    model = HistGradientBoostingClassifier(**PARAMS).fit(train[FEATURES], train.lapsed_14d)
    test["p"] = model.predict_proba(test[FEATURES])[:, 1]
    m_noai = HistGradientBoostingClassifier(**PARAMS).fit(train[NO_AI], train.lapsed_14d)
    test["p_noai"] = m_noai.predict_proba(test[NO_AI])[:, 1]
    tk = test[test.tickets_28d > 0]
    metrics = {
        "test_auc": roc_auc_score(test.lapsed_14d, test.p),
        "test_pr_auc": average_precision_score(test.lapsed_14d, test.p),
        "test_brier": brier_score_loss(test.lapsed_14d, test.p),
        "test_auc_without_genai_features": roc_auc_score(test.lapsed_14d, test.p_noai),
        "test_auc_ticket_filers": roc_auc_score(tk.lapsed_14d, tk.p),
        "test_auc_ticket_filers_without_genai": roc_auc_score(tk.lapsed_14d, tk.p_noai),
        "test_auc_days_since_last_play_only": roc_auc_score(test.lapsed_14d, test.days_since_last_play),
        "test_base_lapse_rate": test.lapsed_14d.mean(),
        "lapse_rate_ai_churn_intent": test[test.ai_churn_intent_28d == 1].lapsed_14d.mean(),
        "lapse_rate_ai_payment_issue": test[test.ai_payment_issue_28d == 1].lapsed_14d.mean(),
    }
    sq, pp, pp_noai = weekly_program(test, "status_quo"), weekly_program(test, "p"), weekly_program(test, "p_noai")
    for name, b in [("status_quo", sq), ("playerpulse", pp), ("playerpulse_no_genai", pp_noai)]:
        metrics[f"bt_{name}_lapsers_reached"] = b.lapsers_reached.sum()
        metrics[f"bt_{name}_revenue_at_risk_reached"] = b.revenue_at_risk_reached.sum()
        metrics[f"bt_{name}_expected_revenue_saved"] = b.expected_revenue_saved.sum()
    mlflow.log_params({**PARAMS, "weekly_capacity": K, "n_features": len(FEATURES)})
    mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
    print(json.dumps({k: round(float(v), 4) for k, v in metrics.items()}, indent=2))
    cmp = sq[["as_of_date", "total_payer_lapsers", "total_revenue_at_risk"]].copy()
    cmp["status_quo_reached_$"] = sq.revenue_at_risk_reached.round(0)
    cmp["playerpulse_reached_$"] = pp.revenue_at_risk_reached.round(0)
    cmp["status_quo_saved_$"] = sq.expected_revenue_saved.round(0)
    cmp["playerpulse_saved_$"] = pp.expected_revenue_saved.round(0)
    print(cmp.to_string(index=False))
    oot_run_id = run.info.run_id

# COMMAND ----------

# MAGIC %md ### Business value of the backtest (same weekly capacity, better targeting, earlier contact)

# COMMAND ----------

weeks = len(pp)
ann = 52 / weeks
dau = spark.sql(f"SELECT avg(dau) d FROM (SELECT kpi_date, sum(dau) dau FROM {GAME}.gold_daily_kpis WHERE kpi_date >= DATE'2026-08-09' GROUP BY 1)").first().d
rev = spark.sql(f"SELECT sum(net_revenue_usd) r FROM {GAME}.gold_daily_kpis WHERE kpi_date >= DATE'2026-08-09' AND kpi_date <= DATE'2026-10-24'").first().r
net_pp = pp.expected_revenue_saved.sum() - pp.offer_cost.sum()
net_sq = sq.expected_revenue_saved.sum() - sq.offer_cost.sum()
value = pd.DataFrame([
    ("Backtest weeks (out-of-time, Aug-Oct 2026)", weeks),
    ("Weekly intervention capacity", K),
    ("Avg DAU in backtest window", round(dau)),
    ("Net revenue in backtest window ($)", round(rev)),
    ("Payer lapsers (all weeks)", int(pp.total_payer_lapsers.sum())),
    ("Revenue at risk from lapsers, 90d spend ($)", round(pp.total_revenue_at_risk.sum())),
    ("Status quo: lapsers reached", int(sq.lapsers_reached.sum())),
    ("PlayerPulse: lapsers reached", int(pp.lapsers_reached.sum())),
    ("Status quo: revenue at risk reached ($)", round(sq.revenue_at_risk_reached.sum())),
    ("PlayerPulse: revenue at risk reached ($)", round(pp.revenue_at_risk_reached.sum())),
    ("PlayerPulse w/o GenAI features: revenue at risk reached ($)", round(pp_noai.revenue_at_risk_reached.sum())),
    ("Status quo: expected revenue saved, net of offer cost ($)", round(net_sq)),
    ("PlayerPulse: expected revenue saved, net of offer cost ($)", round(net_pp)),
    ("Incremental net revenue vs status quo, annualised ($)", round((net_pp - net_sq) * ann)),
    ("Incremental net revenue per 1M DAU, annualised ($)", round((net_pp - net_sq) * ann / dau * 1e6)),
    ("Players retained per year (PlayerPulse)", round(pp.expected_players_saved.sum() * ann)),
    ("Players retained per year (status quo)", round(sq.expected_players_saved.sum() * ann)),
], columns=["metric", "value"])
value["value"] = value["value"].astype(float)
spark.createDataFrame(value).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.model_backtest_value")
spark.sql(f"COMMENT ON TABLE {ML}.model_backtest_value IS 'Out-of-time backtest: PlayerPulse vs. status-quo win-back (payers quiet 3+ days) at equal weekly capacity; assumptions in playerpulse_game.gold_liveops_assumptions'")
weekly = pd.concat([sq.assign(policy="status_quo"), pp.assign(policy="playerpulse"), pp_noai.assign(policy="playerpulse_no_genai")])
spark.createDataFrame(weekly).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.model_backtest_weekly")
print(value.to_string(index=False))
with mlflow.start_run(run_id=oot_run_id):
    mlflow.log_table(value, "backtest_value.json")

# COMMAND ----------

# MAGIC %md ### Refit on all labeled snapshots, register in Unity Catalog, score the active player base

# COMMAND ----------

MODEL_NAME = f"{ML}.player_churn_risk"
with mlflow.start_run(run_name="hgb_final_all_labeled"):
    final = HistGradientBoostingClassifier(**PARAMS).fit(lab[FEATURES], lab.lapsed_14d)
    mlflow.log_params({**PARAMS, "trained_through_as_of": str(lab.as_of_date.max().date())})
    mlflow.log_metrics({"oot_test_auc": metrics["test_auc"], "oot_test_pr_auc": metrics["test_pr_auc"]})
    sig = infer_signature(lab[FEATURES].head(50), final.predict_proba(lab[FEATURES].head(50))[:, 1])
    info = mlflow.sklearn.log_model(final, artifact_path="model", signature=sig, input_example=lab[FEATURES].head(5),
                                    registered_model_name=MODEL_NAME)
from mlflow import MlflowClient
client = MlflowClient()
ver = info.registered_model_version
client.set_registered_model_alias(MODEL_NAME, "champion", ver)
client.update_registered_model(MODEL_NAME, description="P(no play in next 14 days) for players active in the last 7 days (HistGradientBoosting). Features: engagement, economy friction, crashes, spend, GenAI ticket signals.")
print(f"registered {MODEL_NAME} version {ver} -> @champion")

# COMMAND ----------

champion = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")
cur = pdf[pdf.labeled == False].copy()
cur["churn_prob_14d"] = champion.predict_proba(cur[FEATURES])[:, 1]
DRIVER_LABELS = {
    "trend_7d_vs_28d": "Play frequency dropping", "days_since_last_play": "Hasn't logged in recently",
    "minutes_7d": "Short sessions this week", "win_rate_7d": "Losing streak", "energy_walls_7d": "Hitting energy walls",
    "crashes_7d": "Crashing on device", "is_low_tier_device": "Low-tier device", "in_guild": "Not in a guild",
    "ai_churn_intent_28d": "Said they may quit (ticket)", "ai_payment_issue_28d": "Unresolved payment issue (ticket)",
    "ai_toxicity_28d": "Reported harassment (ticket)", "ai_energy_complaint_28d": "Complained about energy (ticket)",
    "days_since_purchase": "Stopped spending", "tenure_days": "New player", "latency_28d": "High latency",
}
medians = lab[FEATURES].median()
deltas = {}
for f in DRIVER_LABELS:
    X = cur[FEATURES].copy(); X[f] = medians[f]
    deltas[f] = cur.churn_prob_14d.values - champion.predict_proba(X)[:, 1]
Dl = pd.DataFrame(deltas, index=cur.index)
def top_drivers(i):
    s = Dl.loc[i].sort_values(ascending=False)
    return " ; ".join([DRIVER_LABELS[f] for f, v in s.items() if v > 0.01][:3])
cur["top_drivers"] = [top_drivers(i) for i in cur.index]
cur["value_at_risk_usd"] = (cur.churn_prob_14d * cur.spend_90d).round(2)
cur["model_version"] = str(ver)
cols = ["as_of_date", "player_id", "churn_prob_14d", "value_at_risk_usd", "top_drivers", "model_version"] + FEATURES
spark.createDataFrame(cur[cols]).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{ML}.player_churn_scores")
spark.sql(f"COMMENT ON TABLE {ML}.player_churn_scores IS 'Current 14-day lapse probability for players active in the last 7 days, from {MODEL_NAME}@champion, with reason codes'")
print(f"scored {len(cur):,} active players | expected lapsers next 14d = {cur.churn_prob_14d.sum():.0f} | revenue at risk = ${cur.value_at_risk_usd.sum():,.0f}")
print(cur.nlargest(12, "value_at_risk_usd")[["player_id", "churn_prob_14d", "spend_90d", "value_at_risk_usd", "top_drivers"]].to_string(index=False))

# COMMAND ----------

imp = pd.DataFrame({"feature": list(DRIVER_LABELS), "mean_abs_risk_delta": [np.abs(Dl[f]).mean() for f in DRIVER_LABELS]}).sort_values("mean_abs_risk_delta", ascending=False)
print(imp.to_string(index=False))
