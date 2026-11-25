# Genie space conversations (real API output)

Space id: `01f1e8deefe41e469de20a4ea139c622` · captured 2026-11-25 14:59 UTC

## Q: How did the 14-day lapse rate of whales change from Season 6 to Season 7?

_status: COMPLETED_

**Genie:** You want to see the 14-day lapse rate for each payer tier broken down by season, showing the total number of active player weeks and the overall lapse rate for each combination.

```sql
WITH `season_rates` AS (
  SELECT
    CASE
      WHEN `week_start` < DATE'2026-06-02' THEN 'Season 6'
      WHEN `week_start` < DATE'2026-09-01' THEN 'Season 7'
    END AS `season`,
    SUM(`lapsed_14d`) AS `lapsed_14d`,
    SUM(`active_players`) AS `active_players`,
    try_divide(100 * SUM(`lapsed_14d`),SUM(`active_players`)) AS `lapse_rate_14d_pct`
  FROM `aws_demo_catalog`.`playerpulse_game`.`gold_weekly_churn`
  WHERE `payer_tier` IS NOT NULL
    AND `payer_tier` ILIKE '%whale%'
    AND `week_start` IS NOT NULL
    AND `week_start` >= DATE'2026-03-01'
    AND `week_start` < DATE'2026-09-01'
  GROUP BY
    CASE
      WHEN `week_start` < DATE'2026-06-02' THEN 'Season 6'
      WHEN `week_start` < DATE'2026-09-01' THEN 'Season 7'
    END
)
SELECT
  MAX(CASE WHEN `season` = 'Season 6' THEN `lapse_rate_14d_pct` END) AS `season_6_lapse_rate_14d_pct`,
  MAX(CASE WHEN `season` = 'Season 7' THEN `lapse_rate_14d_pct` END) AS `season_7_lapse_rate_14d_pct`,
  MAX(CASE WHEN `season` = 'Season 7' THEN `lapse_rate_14d_pct` END) - MAX(CASE WHEN `season` = 'Season 6' THEN `lapse_rate_14d_pct` END) AS `change_pct_points`
FROM `season_rates`
```

| season_6_lapse_rate_14d_pct | season_7_lapse_rate_14d_pct | change_pct_points |
|---|---|---|
| 0.8051082731815657 | 1.3351564385104158 | 0.53004816532885 |

**Genie:** Whale 14-day lapse rate increased from **0.805%** in **Season 6** to **1.335%** in **Season 7**, a rise of **0.530 percentage points**. Based on the season-level totals in the result, whales were more likely to lapse in **Season 7** than in **Season 6**.

## Q: What was the crash rate by device tier before and after client v7.2?

_status: COMPLETED_

**Genie:** You want to see the crash rate percentage by device tier before and after the release of client version 7.2 on August 12, 2026.

```sql
SELECT CASE WHEN `kpi_date` < DATE'2026-08-12' THEN 'before_v7.2' ELSE 'after_v7.2' END AS `period`, `device_tier`, SUM(`crashes`) AS `crashes`, SUM(`sessions`) AS `sessions`, ROUND(try_divide(100 * SUM(`crashes`),SUM(`sessions`)), 3) AS `crash_rate_pct` FROM `aws_demo_catalog`.`playerpulse_game`.`gold_daily_kpis` WHERE `device_tier` IS NOT NULL AND `kpi_date` IS NOT NULL AND `sessions` IS NOT NULL AND `crashes` IS NOT NULL GROUP BY CASE WHEN `kpi_date` < DATE'2026-08-12' THEN 'before_v7.2' ELSE 'after_v7.2' END, `device_tier` ORDER BY `period`, `device_tier`
```

| period | device_tier | crashes | sessions | crash_rate_pct |
|---|---|---|---|---|
| after_v7.2 | high | 34525 | 2304010 | 1.498 |
| after_v7.2 | low | 137754 | 951432 | 14.479 |
| after_v7.2 | mid | 34570 | 2316121 | 1.493 |
| before_v7.2 | high | 62486 | 4172316 | 1.498 |
| before_v7.2 | low | 97459 | 2166945 | 4.498 |
| before_v7.2 | mid | 62961 | 4191801 | 1.502 |

**Genie:** Crash rates were **stable** for **high** and **mid** device tiers before vs. after v7.2, but **low-tier devices worsened sharply** after the release.

- **High tier:** **1.498%** before v7.2 and **1.498%** after v7.2
- **Mid tier:** **1.502%** before v7.2 and **1.493%** after v7.2
- **Low tier:** **4.498%** before v7.2 and **14.479%** after v7.2

Across all 6 results, the clear outlier is **low-tier devices**, where crash rate increased by **9.981 percentage points** after v7.2.

## Q: What are high-risk payers complaining about, by ticket category?

_status: COMPLETED_

**Genie:** You want to see what high-risk paying players are complaining about, broken down by ticket category.

```sql
SELECT t.category, COUNT(*) AS ticket_count, COUNT(DISTINCT t.player_id) AS players, ROUND(AVG(CAST(t.sentiment AS DOUBLE)), 3) AS avg_sentiment, ROUND(AVG(CAST(t.severity AS DOUBLE)), 3) AS avg_severity, SUM(CASE WHEN t.churn_intent THEN 1 ELSE 0 END) AS churn_intent_tickets, SUM(CASE WHEN t.spend_stop_intent THEN 1 ELSE 0 END) AS spend_stop_intent_tickets FROM aws_demo_catalog.playerpulse_serving.player_retention_queue AS q INNER JOIN aws_demo_catalog.playerpulse_ml.ticket_insights AS t ON q.player_id = t.player_id WHERE q.risk_tier IS NOT NULL AND q.risk_tier ILIKE '%high%' AND q.payer_tier IS NOT NULL AND q.payer_tier <> 'non_payer' AND t.category IS NOT NULL AND t.category <> 'POSITIVE_FEEDBACK' GROUP BY t.category ORDER BY ticket_count DESC, t.category
```

| category | ticket_count | players | avg_sentiment | avg_severity | churn_intent_tickets | spend_stop_intent_tickets |
|---|---|---|---|---|---|---|
| PAYMENT_ENTITLEMENT | 19 | 10 | -1.632 | 3.0 | 5 | 3 |
| CRASH_BUG | 8 | 8 | -1.625 | 2.625 | 0 | 0 |
| ACCOUNT_HELP | 2 | 2 | 0.0 | 1.0 | 0 | 0 |
| ENERGY_ECONOMY | 1 | 1 | -1.0 | 1.0 | 0 | 0 |
| MATCHMAKING_DIFFICULTY | 1 | 1 | -1.0 | 1.0 | 0 | 0 |
| OTHER | 1 | 1 | 0.0 | 1.0 | 0 | 0 |
| TOXICITY | 1 | 1 | -1.0 | 2.0 | 1 | 0 |

**Genie:** Among high-risk payers, complaints are led by **PAYMENT_ENTITLEMENT** with **19 tickets** from **10 players**, followed by **CRASH_BUG** with **8 tickets** from **8 players**; payment/entitlement issues also show the most risk signals, including **5** churn-intent tickets and **3** spend-stop-intent tickets. Examples include:
- **PAYMENT_ENTITLEMENT** — **19 tickets**, **10 players**, avg sentiment **-1.632**, avg severity **3.000**
- **CRASH_BUG** — **8 tickets**, **8 players**, avg sentiment **-1.625**, avg severity **2.625**
- **ACCOUNT_HELP** — **2 tickets**, **2 players**, avg sentiment **0.000**, avg severity **1.000**
- **ENERGY_ECONOMY** — **1 ticket**, **1 player**, avg sentiment **-1.000**, avg severity **1.000**
- **MATCHMAKING_DIFFICULTY** — **1 ticket**, **1 player**, avg sentiment **-1.000**, avg severity **1.000**
Across all **7 categories**, complaints are concentrated in payment/entitlement and crash issues, and payment/entitlement stands out as both the largest and most severe category.

## Q: How many players in the retention queue are blocked from paid offers, and why?

_status: COMPLETED_

**Genie:** You want to see how many players in the retention queue are blocked from receiving paid offers, categorized by the reason for the block.

```sql
WITH blocked AS (
  SELECT
    CASE
      WHEN `is_minor` = true AND `marketing_opt_in` = false THEN 'minor_and_no_marketing_consent'
      WHEN `is_minor` = true THEN 'minor'
      WHEN `marketing_opt_in` = false THEN 'no_marketing_consent'
      ELSE 'other'
    END AS `block_reason`
  FROM `aws_demo_catalog`.`playerpulse_serving`.`player_retention_queue`
  WHERE `paid_offer_eligible` = false
)
SELECT
  `block_reason`,
  COUNT(*) AS `blocked_players`,
  SUM(COUNT(*)) OVER () AS `total_blocked_players`
FROM blocked
GROUP BY `block_reason`
ORDER BY `blocked_players` DESC, `block_reason`
```

| block_reason | blocked_players | total_blocked_players |
|---|---|---|
| no_marketing_consent | 14874 | 19986 |
| minor | 3151 | 19986 |
| minor_and_no_marketing_consent | 1961 | 19986 |

**Genie:** **19,986 players** in the retention queue are blocked from paid offers. The reasons shown are **no marketing consent** with **14,874 players**, **minor** with **3,151 players**, and **minor and no marketing consent** with **1,961 players**. The biggest driver is **no marketing consent**, accounting for the clear majority of blocked players.

## Q: How much incremental revenue does PlayerPulse deliver versus the current win-back rule?

_status: COMPLETED_

**Genie:** You want to see the incremental revenue delivered by PlayerPulse compared to the current win-back rule, based on backtest metrics.

```sql
SELECT `metric`, ROUND(`value`, 2) AS `value`
FROM `aws_demo_catalog`.`playerpulse_ml`.`model_backtest_value`
WHERE `metric` IS NOT NULL
  AND `metric` ILIKE '%incremental%revenue%'
ORDER BY `metric`
```

| metric | value |
|---|---|
| Incremental net revenue per 1M DAU, annualised ($) | 1401130.0 |
| Incremental net revenue vs status quo, annualised ($) | 37316.0 |

**Genie:** PlayerPulse delivers **$37,316.00** in **annualized incremental net revenue** versus the current win-back rule. The results also show **$1,401,130.00** in **annualized incremental net revenue per 1M DAU**, indicating the uplift scales materially with audience size.

## Q: Show weekly ARPDAU since March

_status: COMPLETED_

**Genie:** You want to see the weekly ARPDAU (average revenue per daily active user) and average daily active users for each week starting from March 1, 2026.

```sql
SELECT CAST(date_trunc('WEEK', `kpi_date`) AS DATE) AS `week`, ROUND(try_divide(SUM(`net_revenue_usd`),SUM(`dau`)), 3) AS `arpdau_usd`, ROUND(try_divide(SUM(`dau`),7), 0) AS `avg_dau`
FROM `aws_demo_catalog`.`playerpulse_game`.`gold_daily_kpis`
WHERE `kpi_date` IS NOT NULL
  AND `kpi_date` >= DATE'2026-03-01'
GROUP BY CAST(date_trunc('WEEK', `kpi_date`) AS DATE)
ORDER BY `week`
```

| week | arpdau_usd | avg_dau |
|---|---|---|
| 2026-02-23 | 0.412 | 3061.0 |
| 2026-03-02 | 0.404 | 20881.0 |
| 2026-03-09 | 0.223 | 21398.0 |
| 2026-03-16 | 0.23 | 21952.0 |
| 2026-03-23 | 0.225 | 22421.0 |
| 2026-03-30 | 0.22 | 22911.0 |
| 2026-04-06 | 0.286 | 24216.0 |
| 2026-04-13 | 0.339 | 26498.0 |
| 2026-04-20 | 0.251 | 25290.0 |
| 2026-04-27 | 0.221 | 25514.0 |
| 2026-05-04 | 0.236 | 25764.0 |
| 2026-05-11 | 0.222 | 26101.0 |
| 2026-05-18 | 0.22 | 26529.0 |
| 2026-05-25 | 0.214 | 26876.0 |
| 2026-06-01 | 0.477 | 26712.0 |
| 2026-06-08 | 0.266 | 25198.0 |
| 2026-06-15 | 0.246 | 24161.0 |
| 2026-06-22 | 0.259 | 23415.0 |
| 2026-06-29 | 0.263 | 22985.0 |
| 2026-07-06 | 0.312 | 24018.0 |
| 2026-07-13 | 0.39 | 26250.0 |
| 2026-07-20 | 0.381 | 25927.0 |
| 2026-07-27 | 0.301 | 23531.0 |
| 2026-08-03 | 0.286 | 23056.0 |
| 2026-08-10 | 0.298 | 22914.0 |

**Genie:** Weekly ARPDAU since March ranges from **$0.214** to **$0.506** across the **36 weeks shown**, with the highest value in the week of **2026-08-31** and the lowest in the week of **2026-05-25**. Examples include:
- **2026-03-02:** **$0.404** ARPDAU, **20,881** average DAU
- **2026-06-01:** **$0.477** ARPDAU, **26,712** average DAU
- **2026-07-13:** **$0.390** ARPDAU, **26,250** average DAU
- **2026-08-31:** **$0.506** ARPDAU, **22,547** average DAU
- **2026-09-21:** **$0.396** ARPDAU, **29,862** average DAU
ARPDAU was generally lower through March to May, then showed stronger spikes in early June, late August, and late September while average DAU climbed to just under **29.9K** by October.

