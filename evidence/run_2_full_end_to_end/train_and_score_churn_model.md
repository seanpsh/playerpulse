# train_and_score_churn_model — executed notebook output

- Notebook: `/Workspace/Users/shuheng.pi@databricks.com/.bundle/playerpulse/dev/files/src/notebooks/03_train_and_score_churn_model`
- Job run: 931556335206949 · task run: 619361212557610 · result: **SUCCESS**
- Started 2026-11-25 14:52:16 UTC, duration 166s

# 03 · ML: 14-day lapse (churn) model for active players
* **Point-in-time weekly snapshots** (Sundays): only data on/before each `as_of_date` is used. Population = players
  active in the prior 7 days.
* **Features**: engagement level & trend, win/loss, energy walls (Season 7 economy), crashes, latency, guild,
  spend recency/monetary, tenure, device, and **GenAI ticket signals** (root cause, churn intent, severity).
* **Label**: no play in the next 14 days.
* **Out-of-time validation**: train on snapshots to 19-Jul-2026, test on 9-Aug → 11-Oct-2026 (3-week gap, no label overlap).
* **Business backtest** vs. the studio's current win-back rule ("payers quiet for 3+ days, highest spend first")
  at the same weekly LiveOps capacity.
* Registered in **Unity Catalog** as `<catalog>.playerpulse_ml.player_churn_risk@champion`; scores the active base with reason codes.

```python
%pip install --quiet "mlflow>=2.20" "scikit-learn>=1.4,<1.7"
%restart_python
```
**Output:**

```text
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
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
```
**Output:**

```text
data as of: 2026-10-31 | weekly capacity: 500 | assumptions: {'save_rate_proactive': 0.25, 'save_rate_reactive': 0.1, 'offer_cost_usd': 0.25, 'forward_revenue_multiplier': 2.0, 'weekly_intervention_capacity': 500.0}
```

### Point-in-time feature snapshots

```python
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
```
**Output:**

| labeled | count(1) | avg(lapsed_14d) |
|---|---|---|
| True | 1084147 | 0.01762030425763296 |
| False | 43874 | None |

```python
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
```
**Output:**

```text
train rows 599,947 (lapse rate 1.546%) | test rows 404,132 (lapse rate 1.945%)
```

### Train (out-of-time), evaluate, ablate GenAI features, backtest vs. status-quo win-back

```python
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
```
**Output:**

```text
If you are using MLflow Tracing, you can migrate your traces to Unity Catalog for unlimited storage, fine-grained access controls, and queryability from notebooks, SQL, and dashboards. Learn more: https://docs.databricks.com/aws/en/mlflow3/genai/tracing/migrate-traces-to-uc
```

```text
{
  "test_auc": 0.8864,
  "test_pr_auc": 0.3044,
  "test_brier": 0.0158,
  "test_auc_without_genai_features": 0.8866,
  "test_auc_ticket_filers": 0.9026,
  "test_auc_ticket_filers_without_genai": 0.9009,
  "test_auc_days_since_last_play_only": 0.8348,
  "test_base_lapse_rate": 0.0195,
  "lapse_rate_ai_churn_intent": 0.0382,
  "lapse_rate_ai_payment_issue": 0.0527,
  "bt_status_quo_lapsers_reached": 577.0,
  "bt_status_quo_revenue_at_risk_reached": 50619.14,
  "bt_status_quo_expected_revenue_saved": 10123.828,
  "bt_playerpulse_lapsers_reached": 415.0,
  "bt_playerpulse_revenue_at_risk_reached": 64634.79,
  "bt_playerpulse_expected_revenue_saved": 17588.553,
  "bt_playerpulse_no_genai_lapsers_reached": 398.0,
  "bt_playerpulse_no_genai_revenue_at_risk_reached": 64511.32,
  "bt_playerpulse_no_genai_expected_revenue_saved": 17594.177
}
as_of_date  total_payer_lapsers  total_revenue_at_risk  status_quo_reached_$  playerpulse_reached_$  status_quo_saved_$  playerpulse_saved_$
2026-08-09                  154               10192.72                6245.0                 8398.0              1249.0               2432.0
2026-08-16                  153                6736.03                5480.0                 5721.0              1096.0               1254.0
2026-08-23                  179                9849.20                5207.0                 8155.0              1041.0               2585.0
2026-08-30                  194                9204.86                7226.0                 7505.0              1445.0               1677.0
2026-09-06                  129                7432.16                4007.0                 6336.0               801.0               2000.0
2026-09-13                   79                5510.23                3685.0                 5103.0               737.0               1478.0
2026-09-20                   76                6388.60                3410.0                 5913.0               682.0               1972.0
2026-09-27                   58                4966.72                4238.0                 4337.0               848.0                916.0
2026-10-04                   51                5675.61                3171.0                 5030.0               634.0               1576.0
2026-10-11                   40                8389.81                7950.0                 8136.0              1590.0               1697.0
```

### Business value of the backtest (same weekly capacity, better targeting, earlier contact)

```python
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
```
**Output:**

```text
                                                     metric     value
                 Backtest weeks (out-of-time, Aug-Oct 2026)      10.0
                               Weekly intervention capacity     500.0
                                 Avg DAU in backtest window   26633.0
                         Net revenue in backtest window ($)  636541.0
                                  Payer lapsers (all weeks)    1113.0
                Revenue at risk from lapsers, 90d spend ($)   74346.0
                                Status quo: lapsers reached     577.0
                               PlayerPulse: lapsers reached     415.0
                    Status quo: revenue at risk reached ($)   50619.0
                   PlayerPulse: revenue at risk reached ($)   64635.0
PlayerPulse w/o GenAI features: revenue at risk reached ($)   64511.0
  Status quo: expected revenue saved, net of offer cost ($)    9162.0
 PlayerPulse: expected revenue saved, net of offer cost ($)   16339.0
      Incremental net revenue vs status quo, annualised ($)   37316.0
         Incremental net revenue per 1M DAU, annualised ($) 1401130.0
                    Players retained per year (PlayerPulse)     256.0
                     Players retained per year (status quo)     300.0
```

### Refit on all labeled snapshots, register in Unity Catalog, score the active player base

```python
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
```
**Output:**

```text
2026/11/25 14:54:34 WARNING mlflow.models.model: `artifact_path` is deprecated. Please use `name` instead.
🔗 View Logged Model at: https://fevm-aws-demo.cloud.databricks.com/ml/experiments/2691521608615268/models/m-61ce7f5c88504da2ad08e1db5ec39181?o=7474659338788077
Registered model 'aws_demo_catalog.playerpulse_ml.player_churn_risk' already exists. Creating a new version of this model...
```

```text
🔗 Created version '2' of model 'aws_demo_catalog.playerpulse_ml.player_churn_risk': https://fevm-aws-demo.cloud.databricks.com/explore/data/models/aws_demo_catalog/playerpulse_ml/player_churn_risk/version/2?o=7474659338788077
```

```text
registered aws_demo_catalog.playerpulse_ml.player_churn_risk version 2 -> @champion
```

```python
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
```
**Output:**

```text
scored 43,874 active players | expected lapsers next 14d = 498 | revenue at risk = $9,109
player_id  churn_prob_14d  spend_90d  value_at_risk_usd                                                                                 top_drivers
 P0046644        0.724307    1978.32            1432.91                        Hasn't logged in recently ; Not in a guild ; Play frequency dropping
 P0007755        0.444928    2323.39            1033.74          Hasn't logged in recently ; Unresolved payment issue (ticket) ; Crashing on device
 P0031051        0.738857    1373.48            1014.81                               Hasn't logged in recently ; Unresolved payment issue (ticket)
 P0029369        0.906790     984.62             892.84              Hasn't logged in recently ; Unresolved payment issue (ticket) ; Not in a guild
 P0039162        0.823434     480.83             395.93     Hasn't logged in recently ; Unresolved payment issue (ticket) ; Play frequency dropping
 P0049967        0.506103     416.81             210.95                                                  Hasn't logged in recently ; Not in a guild
 P0037483        0.457363     386.85             176.93              Hasn't logged in recently ; Unresolved payment issue (ticket) ; Not in a guild
 P0024131        0.225635     661.71             149.30                                                  Hasn't logged in recently ; Not in a guild
 P0011897        0.182699     755.82             138.09              Hasn't logged in recently ; Unresolved payment issue (ticket) ; Not in a guild
 P0025493        0.079422    1633.60             129.74                               Hasn't logged in recently ; Unresolved payment issue (ticket)
 P0058930        0.212840     571.78             121.70              Unresolved payment issue (ticket) ; Hasn't logged in recently ; Not in a guild
 P0040720        0.199974     559.86             111.96 Hasn't logged in recently ; Unresolved payment issue (ticket) ; Said they may quit (ticket)
```

```python
imp = pd.DataFrame({"feature": list(DRIVER_LABELS), "mean_abs_risk_delta": [np.abs(Dl[f]).mean() for f in DRIVER_LABELS]}).sort_values("mean_abs_risk_delta", ascending=False)
print(imp.to_string(index=False))
```
**Output:**

```text
                feature  mean_abs_risk_delta
   days_since_last_play             0.007861
               in_guild             0.003003
            tenure_days             0.001465
             minutes_7d             0.000569
    days_since_purchase             0.000540
            win_rate_7d             0.000475
        trend_7d_vs_28d             0.000284
             crashes_7d             0.000219
   ai_payment_issue_28d             0.000078
            latency_28d             0.000067
        ai_toxicity_28d             0.000038
    ai_churn_intent_28d             0.000012
     is_low_tier_device             0.000008
        energy_walls_7d             0.000000
ai_energy_complaint_28d             0.000000
```
