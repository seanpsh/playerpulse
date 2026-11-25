-- =====================================================================================
-- PlayerPulse · Lakeflow Declarative Pipeline · GOLD
-- Business-level tables for ML features, the Genie space and the LiveOps app.
-- =====================================================================================

CREATE OR REFRESH MATERIALIZED VIEW gold_liveops_assumptions
COMMENT 'Value assumptions used by the backtest and app (Emberforge LiveOps / finance, 2026). Save rates reflect that win-back works far better before a player has gone quiet.'
AS SELECT * FROM VALUES
  ('save_rate_proactive',        0.25, 'Share of at-risk players retained when contacted while still active (<3 days since last play)'),
  ('save_rate_reactive',         0.10, 'Share retained when contacted after 3+ days of inactivity (status-quo win-back)'),
  ('offer_cost_usd',             0.25, 'Avg cost per intervention (mix of near-free fixes/gifts and discount offers that cannibalise some organic spend)'),
  ('forward_revenue_multiplier', 2.00, 'Value of retaining a payer = 2 x trailing 90-day net spend (~6 months of remaining payer lifetime)'),
  ('weekly_intervention_capacity', 500, 'Personalised interventions LiveOps + CRM can run per week')
AS t(assumption, value, description);

CREATE OR REFRESH MATERIALIZED VIEW gold_daily_kpis
COMMENT 'Daily title KPIs by platform, device tier and region: DAU, installs, engagement, crash rate, net revenue, payers, ARPDAU, ARPPU.'
AS WITH act AS (
  SELECT d.activity_date AS kpi_date, p.platform, p.device_tier, p.region,
    count(*) AS dau, sum(d.sessions) AS sessions, round(sum(d.minutes_played), 0) AS minutes_played,
    sum(d.matches) AS matches, sum(d.crashes) AS crashes, sum(d.energy_walls) AS energy_walls
  FROM silver_player_daily d JOIN silver_players p USING (player_id) GROUP BY ALL
), rev AS (
  SELECT s.purchase_date AS kpi_date, p.platform, p.device_tier, p.region,
    round(sum(s.amount_usd), 2) AS net_revenue_usd, count(DISTINCT s.player_id) AS payers
  FROM silver_purchases s JOIN silver_players p USING (player_id) GROUP BY ALL
), inst AS (
  SELECT install_date AS kpi_date, platform, device_tier, region, count(*) AS installs FROM silver_players GROUP BY ALL
)
SELECT a.kpi_date, a.platform, a.device_tier, a.region, a.dau, coalesce(i.installs, 0) AS installs,
  a.sessions, a.minutes_played, a.matches, a.crashes, round(a.crashes / a.sessions, 4) AS crash_rate_per_session,
  a.energy_walls, coalesce(r.net_revenue_usd, 0) AS net_revenue_usd, coalesce(r.payers, 0) AS payers,
  round(coalesce(r.net_revenue_usd, 0) / a.dau, 4) AS arpdau_usd,
  round(coalesce(r.net_revenue_usd, 0) / nullif(r.payers, 0), 2) AS arppu_usd
FROM act a
LEFT JOIN rev r USING (kpi_date, platform, device_tier, region)
LEFT JOIN inst i USING (kpi_date, platform, device_tier, region);

CREATE OR REFRESH MATERIALIZED VIEW gold_retention_cohorts
COMMENT 'Install-week cohort retention: share of installs active on day 1, 7 and 30 after install (classic Dn retention).'
AS WITH c AS (
  SELECT p.player_id, p.install_date, CAST(date_trunc('week', p.install_date) AS DATE) AS cohort_week, p.platform, p.acquisition_channel
  FROM silver_players p WHERE p.install_date >= DATE'2026-03-01'
), a AS (
  SELECT c.player_id,
    max(CASE WHEN datediff(d.activity_date, c.install_date) = 1 THEN 1 ELSE 0 END) AS d1,
    max(CASE WHEN datediff(d.activity_date, c.install_date) = 7 THEN 1 ELSE 0 END) AS d7,
    max(CASE WHEN datediff(d.activity_date, c.install_date) = 30 THEN 1 ELSE 0 END) AS d30
  FROM c JOIN silver_player_daily d ON d.player_id = c.player_id GROUP BY c.player_id
), mx AS (SELECT max(activity_date) AS d FROM silver_player_daily)
SELECT c.cohort_week, c.platform, c.acquisition_channel, count(*) AS installs,
  round(avg(coalesce(a.d1, 0)), 4) AS d1_retention,
  CASE WHEN max(c.install_date) <= date_sub(max(mx.d), 7) THEN round(avg(coalesce(a.d7, 0)), 4) END AS d7_retention,
  CASE WHEN max(c.install_date) <= date_sub(max(mx.d), 30) THEN round(avg(coalesce(a.d30, 0)), 4) END AS d30_retention
FROM c LEFT JOIN a USING (player_id) CROSS JOIN mx
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_weekly_churn
COMMENT 'Weekly 14-day lapse rate of the active base by payer tier. active = played in the 7 days before week_start; lapsed = no play in the 14 days after. Only complete windows.'
AS WITH weeks AS (
  SELECT explode(sequence(DATE'2026-03-08', date_sub((SELECT max(activity_date) FROM silver_player_daily), 14), INTERVAL 7 DAY)) AS week_start
), spend AS (
  SELECT w.week_start, s.player_id, sum(s.amount_usd) AS spend_90d
  FROM weeks w JOIN silver_purchases s ON s.purchase_date <= w.week_start AND s.purchase_date > date_sub(w.week_start, 90)
  GROUP BY ALL
), base AS (
  SELECT DISTINCT w.week_start, d.player_id
  FROM weeks w JOIN silver_player_daily d ON d.activity_date <= w.week_start AND d.activity_date > date_sub(w.week_start, 7)
), fut AS (
  SELECT DISTINCT w.week_start, d.player_id
  FROM weeks w JOIN silver_player_daily d ON d.activity_date > w.week_start AND d.activity_date <= date_add(w.week_start, 14)
)
SELECT b.week_start,
  CASE WHEN coalesce(s.spend_90d, 0) <= 0 THEN 'non_payer' WHEN s.spend_90d < 20 THEN 'minnow'
       WHEN s.spend_90d < 100 THEN 'dolphin' ELSE 'whale' END AS payer_tier,
  count(*) AS active_players,
  sum(CASE WHEN f.player_id IS NULL THEN 1 ELSE 0 END) AS lapsed_14d,
  round(avg(CASE WHEN f.player_id IS NULL THEN 1.0 ELSE 0.0 END), 4) AS lapse_rate_14d,
  round(sum(CASE WHEN f.player_id IS NULL THEN coalesce(s.spend_90d, 0) ELSE 0 END), 2) AS lapsed_spend_90d_usd
FROM base b
LEFT JOIN fut f USING (week_start, player_id)
LEFT JOIN spend s USING (week_start, player_id)
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_player_360_current
COMMENT 'Current snapshot per player (no PII): lifecycle stage, recent engagement, spend, tickets, guild, device. Grain: player_id. lifecycle: new (<7d), active, quiet_3d (3-13 days inactive, the status-quo win-back list), lapsed (14d+).'
AS WITH asof AS (SELECT max(activity_date) AS d FROM silver_player_daily),
act AS (
  SELECT d.player_id, max(d.activity_date) AS last_active_date,
    sum(CASE WHEN d.activity_date > date_sub(asof.d, 7) THEN 1 ELSE 0 END) AS active_days_7d,
    sum(CASE WHEN d.activity_date > date_sub(asof.d, 28) THEN 1 ELSE 0 END) AS active_days_28d,
    round(sum(CASE WHEN d.activity_date > date_sub(asof.d, 7) THEN d.minutes_played ELSE 0 END), 0) AS minutes_7d,
    sum(CASE WHEN d.activity_date > date_sub(asof.d, 7) THEN d.crashes ELSE 0 END) AS crashes_7d,
    sum(CASE WHEN d.activity_date > date_sub(asof.d, 7) THEN d.energy_walls ELSE 0 END) AS energy_walls_7d,
    max_by(d.in_guild, d.activity_date) AS in_guild, max(d.max_level) AS level, max_by(d.client_version, d.activity_date) AS client_version
  FROM silver_player_daily d CROSS JOIN asof GROUP BY d.player_id
),
pay AS (
  SELECT s.player_id, round(sum(s.amount_usd), 2) AS lifetime_spend_usd,
    round(sum(CASE WHEN s.purchase_date > date_sub(asof.d, 90) THEN s.amount_usd ELSE 0 END), 2) AS spend_90d_usd,
    max(s.purchase_date) AS last_purchase_date
  FROM silver_purchases s CROSS JOIN asof GROUP BY s.player_id
),
tk AS (
  SELECT t.player_id, count(*) AS tickets_28d FROM silver_support_tickets t CROSS JOIN asof
  WHERE t.created_date > date_sub(asof.d, 28) GROUP BY t.player_id
)
SELECT p.player_id, p.platform, p.device_tier, p.region, p.country_code, p.age_band, p.is_minor, p.marketing_opt_in,
  p.acquisition_channel, p.install_date, datediff(asof.d, p.install_date) AS tenure_days,
  a.last_active_date, datediff(asof.d, a.last_active_date) AS days_since_last_play,
  CASE WHEN datediff(asof.d, p.install_date) < 7 THEN 'new'
       WHEN datediff(asof.d, a.last_active_date) < 3 THEN 'active'
       WHEN datediff(asof.d, a.last_active_date) < 14 THEN 'quiet_3d'
       ELSE 'lapsed' END AS lifecycle_stage,
  a.active_days_7d, a.active_days_28d, a.minutes_7d, a.crashes_7d, a.energy_walls_7d, a.in_guild, a.level, a.client_version,
  coalesce(y.lifetime_spend_usd, 0) AS lifetime_spend_usd, coalesce(y.spend_90d_usd, 0) AS spend_90d_usd, y.last_purchase_date,
  CASE WHEN coalesce(y.spend_90d_usd, 0) <= 0 THEN 'non_payer' WHEN y.spend_90d_usd < 20 THEN 'minnow'
       WHEN y.spend_90d_usd < 100 THEN 'dolphin' ELSE 'whale' END AS payer_tier,
  coalesce(k.tickets_28d, 0) AS tickets_28d,
  asof.d AS as_of_date
FROM silver_players p
CROSS JOIN asof
JOIN act a USING (player_id)
LEFT JOIN pay y USING (player_id)
LEFT JOIN tk k USING (player_id);
