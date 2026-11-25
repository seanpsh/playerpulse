# SQL verification queries (real results from the Databricks SQL warehouse)

Captured 2026-11-25 14:59 UTC · warehouse `4b55146770394f51` · catalog `aws_demo_catalog`

## Lakeflow: row counts per layer (dedup + expectations drop bad rows)

```sql
SELECT 'bronze_telemetry_daily' tbl, count(*) n FROM aws_demo_catalog.playerpulse_game.bronze_telemetry_daily UNION ALL
SELECT 'silver_player_daily', count(*) FROM aws_demo_catalog.playerpulse_game.silver_player_daily UNION ALL
SELECT 'silver_players', count(*) FROM aws_demo_catalog.playerpulse_game.silver_players UNION ALL
SELECT 'silver_purchases', count(*) FROM aws_demo_catalog.playerpulse_game.silver_purchases UNION ALL
SELECT 'silver_support_tickets', count(*) FROM aws_demo_catalog.playerpulse_game.silver_support_tickets UNION ALL
SELECT 'gold_player_360_current', count(*) FROM aws_demo_catalog.playerpulse_game.gold_player_360_current UNION ALL
SELECT 'ml.ticket_insights', count(*) FROM aws_demo_catalog.playerpulse_ml.ticket_insights UNION ALL
SELECT 'ml.player_features_pit', count(*) FROM aws_demo_catalog.playerpulse_ml.player_features_pit UNION ALL
SELECT 'serving.player_retention_queue', count(*) FROM aws_demo_catalog.playerpulse_serving.player_retention_queue
```

| tbl | n |
|---|---|
| silver_player_daily | 6165398 |
| silver_players | 64642 |
| silver_purchases | 92136 |
| silver_support_tickets | 27395 |
| bronze_telemetry_daily | 6175202 |
| gold_player_360_current | 64241 |
| ml.ticket_insights | 27395 |
| ml.player_features_pit | 1128021 |
| serving.player_retention_queue | 43874 |

## Lakeflow: data-quality expectation results (pipeline event log)

```sql
WITH ev AS (SELECT explode(from_json(details:flow_progress:data_quality:expectations,
  'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) e
  FROM event_log(TABLE(aws_demo_catalog.playerpulse_game.silver_player_daily)) WHERE event_type='flow_progress' AND details:flow_progress:data_quality IS NOT NULL)
SELECT e.dataset, e.name AS expectation, sum(e.passed_records) passed, sum(e.failed_records) failed FROM ev GROUP BY ALL ORDER BY 1, 2
```

| dataset | expectation | passed | failed |
|---|---|---|---|
| aws_demo_catalog.playerpulse_game.silver_player_daily | consistent_matches | 12336114 | 0 |
| aws_demo_catalog.playerpulse_game.silver_player_daily | non_negative_play | 12331286 | 4828 |
| aws_demo_catalog.playerpulse_game.silver_player_daily | plausible_latency | 12336114 | 0 |
| aws_demo_catalog.playerpulse_game.silver_player_daily | valid_player | 12335624 | 490 |
| aws_demo_catalog.playerpulse_game.silver_players | valid_age | 129284 | 0 |
| aws_demo_catalog.playerpulse_game.silver_players | valid_player | 129284 | 0 |
| aws_demo_catalog.playerpulse_game.silver_purchases | refund_sign | 184272 | 0 |
| aws_demo_catalog.playerpulse_game.silver_purchases | valid_status | 184272 | 0 |
| aws_demo_catalog.playerpulse_game.silver_purchases | valid_txn | 184272 | 0 |
| aws_demo_catalog.playerpulse_game.silver_support_tickets | valid_ticket | 54790 | 0 |

## Business problem: 14-day lapse rate by season and payer tier

```sql
SELECT CASE WHEN week_start < DATE'2026-06-02' THEN 'S6 Ashen Crown' WHEN week_start < DATE'2026-09-01' THEN 'S7 Rift Energy' ELSE 'S8 Ember Tide' END season,
  payer_tier, sum(active_players) player_weeks, sum(lapsed_14d) lapsed, round(sum(lapsed_14d) / sum(active_players), 4) lapse_rate_14d,
  round(sum(lapsed_spend_90d_usd), 0) lapsed_spend_90d_usd
FROM aws_demo_catalog.playerpulse_game.gold_weekly_churn GROUP BY ALL ORDER BY payer_tier, season
```

| season | payer_tier | player_weeks | lapsed | lapse_rate_14d | lapsed_spend_90d_usd |
|---|---|---|---|---|---|
| S6 Ashen Crown | dolphin | 13506 | 76 | 0.0056 | 3720.0 |
| S7 Rift Energy | dolphin | 24787 | 435 | 0.0175 | 21197.0 |
| S8 Ember Tide | dolphin | 10993 | 100 | 0.0091 | 4687.0 |
| S6 Ashen Crown | minnow | 44829 | 290 | 0.0065 | 1866.0 |
| S7 Rift Energy | minnow | 70196 | 1313 | 0.0187 | 8368.0 |
| S8 Ember Tide | minnow | 32827 | 294 | 0.009 | 1983.0 |
| S6 Ashen Crown | non_payer | 383126 | 4101 | 0.0107 | -21.0 |
| S7 Rift Energy | non_payer | 409746 | 10772 | 0.0263 | -172.0 |
| S8 Ember Tide | non_payer | 194837 | 2797 | 0.0144 | -16.0 |
| S6 Ashen Crown | whale | 7204 | 58 | 0.0081 | 29848.0 |
| S7 Rift Energy | whale | 12433 | 166 | 0.0134 | 83789.0 |
| S8 Ember Tide | whale | 5985 | 60 | 0.01 | 32435.0 |

## Title KPIs by month (DAU, net revenue, ARPDAU, crash rate)

```sql
SELECT date_format(kpi_date, 'yyyy-MM') month, round(sum(dau) / count(DISTINCT kpi_date)) avg_dau, round(sum(net_revenue_usd)) net_revenue_usd,
  round(sum(net_revenue_usd) / sum(dau), 3) arpdau_usd, round(sum(crashes) / sum(sessions), 4) crash_rate
FROM aws_demo_catalog.playerpulse_game.gold_daily_kpis GROUP BY 1 ORDER BY 1
```

| month | avg_dau | net_revenue_usd | arpdau_usd | crash_rate |
|---|---|---|---|---|
| 2026-03 | 21697.0 | 181384.0 | 0.27 | 0.0213 |
| 2026-04 | 24925.0 | 204562.0 | 0.274 | 0.0212 |
| 2026-05 | 26307.0 | 181086.0 | 0.222 | 0.0211 |
| 2026-06 | 24715.0 | 231597.0 | 0.312 | 0.0213 |
| 2026-07 | 24652.0 | 258421.0 | 0.338 | 0.021 |
| 2026-08 | 22708.0 | 203220.0 | 0.289 | 0.046 |
| 2026-09 | 26689.0 | 306560.0 | 0.383 | 0.0452 |
| 2026-10 | 29652.0 | 234831.0 | 0.255 | 0.0203 |

## Root cause: crash rate by device tier around client v7.2 (Aug 12) and hotfix v7.3 (Sep 24)

```sql
SELECT p.device_tier, CASE WHEN d.activity_date < DATE'2026-08-12' THEN '1 before v7.2' WHEN d.activity_date < DATE'2026-09-24' THEN '2 v7.2' ELSE '3 after v7.3' END period,
  round(sum(d.crashes) / sum(d.sessions), 4) crash_rate_per_session
FROM aws_demo_catalog.playerpulse_game.silver_player_daily d JOIN aws_demo_catalog.playerpulse_game.silver_players p USING (player_id) WHERE d.activity_date >= DATE'2026-07-01' GROUP BY ALL ORDER BY 1, 2
```

| device_tier | period | crash_rate_per_session |
|---|---|---|
| high | 1 before v7.2 | 0.0149 |
| high | 2 v7.2 | 0.015 |
| high | 3 after v7.3 | 0.015 |
| low | 1 before v7.2 | 0.0446 |
| low | 2 v7.2 | 0.2652 |
| low | 3 after v7.3 | 0.0455 |
| mid | 1 before v7.2 | 0.0149 |
| mid | 2 v7.2 | 0.0149 |
| mid | 3 after v7.3 | 0.015 |

## Retention cohorts (D1/D7/D30) by install month

```sql
SELECT date_format(cohort_week, 'yyyy-MM') install_month, sum(installs) installs, round(sum(d1_retention * installs) / sum(installs), 3) d1,
  round(sum(d7_retention * installs) / sum(installs), 3) d7, round(sum(d30_retention * installs) / sum(installs), 3) d30
FROM aws_demo_catalog.playerpulse_game.gold_retention_cohorts GROUP BY 1 ORDER BY 1
```

| install_month | installs | d1 | d7 | d30 |
|---|---|---|---|---|
| 2026-02 | 133 | 0.722 | 0.609 | 0.571 |
| 2026-03 | 4823 | 0.704 | 0.626 | 0.622 |
| 2026-04 | 3814 | 0.733 | 0.651 | 0.601 |
| 2026-05 | 3992 | 0.723 | 0.625 | 0.518 |
| 2026-06 | 5052 | 0.704 | 0.553 | 0.499 |
| 2026-07 | 3936 | 0.709 | 0.571 | 0.45 |
| 2026-08 | 5140 | 0.683 | 0.541 | 0.534 |
| 2026-09 | 3883 | 0.726 | 0.649 | 0.447 |
| 2026-10 | 3869 | 0.681 | 0.318 |  |

## GenAI: ticket classification summary

```sql
SELECT category, count(*) tickets, round(avg(sentiment), 2) avg_sentiment, sum(CAST(churn_intent AS INT)) churn_intent,
  sum(CASE WHEN extraction_error IS NOT NULL THEN 1 ELSE 0 END) errors
FROM aws_demo_catalog.playerpulse_ml.ticket_insights GROUP BY 1 ORDER BY 2 DESC
```

| category | tickets | avg_sentiment | churn_intent | errors |
|---|---|---|---|---|
| CRASH_BUG | 8918 | -1.36 | 589 | 0 |
| ENERGY_ECONOMY | 5374 | -1.51 | 520 | 0 |
| ACCOUNT_HELP | 3321 | -0.03 | 100 | 0 |
| OTHER | 3197 | -0.45 | 89 | 0 |
| POSITIVE_FEEDBACK | 3094 | 1.96 | 75 | 0 |
| PAYMENT_ENTITLEMENT | 1628 | -1.59 | 666 | 0 |
| MATCHMAKING_DIFFICULTY | 1052 | -1.1 | 58 | 0 |
| TOXICITY | 811 | -1.56 | 366 | 0 |

## GenAI: sample classifications (slang, negation, multi-issue)

```sql
SELECT message, category, sentiment, churn_intent, severity, summary FROM aws_demo_catalog.playerpulse_ml.ticket_insights
WHERE message RLIKE '(?i)not quitting|charged twice|cash grab|7.2|guild is leaving' ORDER BY ticket_id LIMIT 12
```

| message | category | sentiment | churn_intent | severity | summary |
|---|---|---|---|---|---|
| Charged twice for gem pack, want refund not spending another cent. | PAYMENT_ENTITLEMENT | -2 | false | 3 | Player reports being charged twice for a gem pack, requests refund, and will stop spending. |
| not quitting lol just wondering when next season starts | OTHER | 0 | false | 1 | Player asks when the next season starts; explicitly not quitting. |
| APP CLOSES MID MATCH SINCE 7.2, LOST 3 RANKED GAMES IN A ROW | CRASH_BUG | -2 | false | 3 | App crashes mid-match since client 7.2; player lost three ranked games consecutively. |
| Not quitting lol just wondering when next season starts | OTHER | 0 | false | 1 | Player asks when the next season starts and says they are not quitting. |
| Charged twice for gem pack, want refund probably moving to another game. | PAYMENT_ENTITLEMENT | -2 | true | 3 | Player reports being charged twice for a gem pack and requests a refund. |
| Not quitting lol just wondering when next season starts | OTHER | 0 | false | 1 | Player asks when the next season starts; explicitly not quitting. |
| App closes mid match since 7.2, lost 3 ranked games in a row | CRASH_BUG | -1 | false | 3 | App crashes mid-match since client version 7.2, causing consecutive ranked losses. |
| charged twice for gem pack, want refund | PAYMENT_ENTITLEMENT | -1 | false | 3 | Player reports double charge for gem pack and requests a refund. |
| app closes mid match since 7.2, lost 3 ranked games in a row | CRASH_BUG | -1 | false | 2 | App closes mid-match since client version 7.2; player lost three ranked games. |
| Not quitting lol just wondering when next season starts | OTHER | 0 | false | 1 | Player asks when the next season starts and says they are not quitting. |
| NOT QUITTING LOL JUST WONDERING WHEN NEXT SEASON STARTS | OTHER | 0 | false | 0 | Player asks when the next season starts and says they are not quitting. |
| not quitting lol just wondering when next season starts | OTHER | 0 | false | 1 | Player asks when the next season starts and states they are not quitting. |

## GenAI signal value: lapse rate when a ticket shows churn intent / payment issue (features table)

```sql
SELECT 'all active player-weeks' segment, count(*) n, round(avg(lapsed_14d), 4) lapse_rate FROM aws_demo_catalog.playerpulse_ml.player_features_pit WHERE labeled UNION ALL
SELECT 'ai_churn_intent_28d = 1', count(*), round(avg(lapsed_14d), 4) FROM aws_demo_catalog.playerpulse_ml.player_features_pit WHERE labeled AND ai_churn_intent_28d = 1 UNION ALL
SELECT 'ai_payment_issue_28d = 1', count(*), round(avg(lapsed_14d), 4) FROM aws_demo_catalog.playerpulse_ml.player_features_pit WHERE labeled AND ai_payment_issue_28d = 1 UNION ALL
SELECT 'ai_toxicity_28d = 1', count(*), round(avg(lapsed_14d), 4) FROM aws_demo_catalog.playerpulse_ml.player_features_pit WHERE labeled AND ai_toxicity_28d = 1
```

| segment | n | lapse_rate |
|---|---|---|
| all active player-weeks | 1084147 | 0.0176 |
| ai_churn_intent_28d = 1 | 7996 | 0.0401 |
| ai_payment_issue_28d = 1 | 4544 | 0.048 |
| ai_toxicity_28d = 1 | 2425 | 0.0478 |

## ML: backtest value vs. status-quo win-back (equal weekly capacity)

```sql
SELECT metric, value FROM aws_demo_catalog.playerpulse_ml.model_backtest_value
```

| metric | value |
|---|---|
| Backtest weeks (out-of-time, Aug-Oct 2026) | 10.0 |
| Weekly intervention capacity | 500.0 |
| Avg DAU in backtest window | 26633.0 |
| Net revenue in backtest window ($) | 636541.0 |
| Payer lapsers (all weeks) | 1113.0 |
| Revenue at risk from lapsers, 90d spend ($) | 74346.0 |
| Status quo: lapsers reached | 577.0 |
| PlayerPulse: lapsers reached | 415.0 |
| Status quo: revenue at risk reached ($) | 50619.0 |
| PlayerPulse: revenue at risk reached ($) | 64635.0 |
| PlayerPulse w/o GenAI features: revenue at risk reached ($) | 64511.0 |
| Status quo: expected revenue saved, net of offer cost ($) | 9162.0 |
| PlayerPulse: expected revenue saved, net of offer cost ($) | 16339.0 |
| Incremental net revenue vs status quo, annualised ($) | 37316.0 |
| Incremental net revenue per 1M DAU, annualised ($) | 1401130.0 |
| Players retained per year (PlayerPulse) | 256.0 |
| Players retained per year (status quo) | 300.0 |

## ML: weekly backtest detail

```sql
SELECT policy, date_format(as_of_date, 'yyyy-MM-dd') week, contacted, lapsers_reached, round(revenue_at_risk_reached) rev_at_risk_reached,
  round(expected_revenue_saved) expected_saved, round(offer_cost) offer_cost, round(total_revenue_at_risk) total_rev_at_risk
FROM aws_demo_catalog.playerpulse_ml.model_backtest_weekly ORDER BY week, policy
```

| policy | week | contacted | lapsers_reached | rev_at_risk_reached | expected_saved | offer_cost | total_rev_at_risk |
|---|---|---|---|---|---|---|---|
| playerpulse | 2026-08-09 | 500 | 58 | 8398.0 | 2432.0 | 125.0 | 10193.0 |
| playerpulse_no_genai | 2026-08-09 | 500 | 56 | 8342.0 | 2407.0 | 125.0 | 10193.0 |
| status_quo | 2026-08-09 | 500 | 78 | 6245.0 | 1249.0 | 125.0 | 10193.0 |
| playerpulse | 2026-08-16 | 500 | 51 | 5721.0 | 1254.0 | 125.0 | 6736.0 |
| playerpulse_no_genai | 2026-08-16 | 500 | 51 | 5720.0 | 1254.0 | 125.0 | 6736.0 |
| status_quo | 2026-08-16 | 500 | 77 | 5480.0 | 1096.0 | 125.0 | 6736.0 |
| playerpulse | 2026-08-23 | 500 | 60 | 8155.0 | 2585.0 | 125.0 | 9849.0 |
| playerpulse_no_genai | 2026-08-23 | 500 | 59 | 8241.0 | 2637.0 | 125.0 | 9849.0 |
| status_quo | 2026-08-23 | 500 | 84 | 5207.0 | 1041.0 | 125.0 | 9849.0 |
| playerpulse | 2026-08-30 | 500 | 65 | 7505.0 | 1677.0 | 125.0 | 9205.0 |
| playerpulse_no_genai | 2026-08-30 | 500 | 63 | 7499.0 | 1685.0 | 125.0 | 9205.0 |
| status_quo | 2026-08-30 | 500 | 90 | 7226.0 | 1445.0 | 125.0 | 9205.0 |
| playerpulse | 2026-09-06 | 500 | 49 | 6336.0 | 2000.0 | 125.0 | 7432.0 |
| playerpulse_no_genai | 2026-09-06 | 500 | 50 | 6634.0 | 2148.0 | 125.0 | 7432.0 |
| status_quo | 2026-09-06 | 485 | 69 | 4007.0 | 801.0 | 121.0 | 7432.0 |
| playerpulse | 2026-09-13 | 500 | 42 | 5103.0 | 1478.0 | 125.0 | 5510.0 |
| playerpulse_no_genai | 2026-09-13 | 500 | 35 | 4898.0 | 1402.0 | 125.0 | 5510.0 |
| status_quo | 2026-09-13 | 420 | 58 | 3685.0 | 737.0 | 105.0 | 5510.0 |
| playerpulse | 2026-09-20 | 500 | 28 | 5913.0 | 1972.0 | 125.0 | 6389.0 |
| playerpulse_no_genai | 2026-09-20 | 500 | 23 | 5768.0 | 1907.0 | 125.0 | 6389.0 |
| status_quo | 2026-09-20 | 242 | 42 | 3410.0 | 682.0 | 61.0 | 6389.0 |
| playerpulse | 2026-09-27 | 500 | 21 | 4337.0 | 916.0 | 125.0 | 4967.0 |
| playerpulse_no_genai | 2026-09-27 | 500 | 20 | 4276.0 | 904.0 | 125.0 | 4967.0 |
| status_quo | 2026-09-27 | 180 | 27 | 4238.0 | 848.0 | 45.0 | 4967.0 |
| playerpulse | 2026-10-04 | 500 | 22 | 5030.0 | 1576.0 | 125.0 | 5676.0 |
| playerpulse_no_genai | 2026-10-04 | 500 | 21 | 4975.0 | 1549.0 | 125.0 | 5676.0 |
| status_quo | 2026-10-04 | 272 | 29 | 3171.0 | 634.0 | 68.0 | 5676.0 |
| playerpulse | 2026-10-11 | 500 | 19 | 8136.0 | 1697.0 | 125.0 | 8390.0 |
| playerpulse_no_genai | 2026-10-11 | 500 | 20 | 8156.0 | 1701.0 | 125.0 | 8390.0 |
| status_quo | 2026-10-11 | 247 | 23 | 7950.0 | 1590.0 | 62.0 | 8390.0 |

## Serving: retention queue by next-best-action

```sql
SELECT next_best_action, count(*) players, sum(CASE WHEN risk_tier='HIGH' THEN 1 ELSE 0 END) high_risk, round(sum(value_at_risk_usd), 2) revenue_at_risk_usd,
  sum(CASE WHEN paid_offer_eligible THEN 1 ELSE 0 END) offer_eligible
FROM aws_demo_catalog.playerpulse_serving.player_retention_queue GROUP BY 1 ORDER BY 4 DESC
```

| next_best_action | players | high_risk | revenue_at_risk_usd | offer_eligible |
|---|---|---|---|---|
| SUPPORT_ESCALATION | 160 | 6 | 4603.41 | 99 |
| PERSONALISED_OFFER | 4336 | 11 | 2923.65 | 4336 |
| EVENT_REENGAGEMENT_PUSH | 32606 | 103 | 1322.92 | 15726 |
| GUILD_MATCH_INVITE | 4194 | 64 | 170.76 | 2320 |
| TECH_FIX_AND_APOLOGY_GIFT | 2476 | 4 | 80.1 | 1350 |
| SAFETY_REVIEW | 102 | 5 | 8.34 | 57 |

## Serving: top 10 of the queue with reason codes and AI message

```sql
SELECT priority_rank, player_id, payer_tier, round(churn_prob_14d, 3) p14, round(value_at_risk_usd, 2) value_at_risk, next_best_action,
  top_drivers, last_ticket_summary, ai_message FROM aws_demo_catalog.playerpulse_serving.player_retention_queue ORDER BY priority_rank LIMIT 10
```

| priority_rank | player_id | payer_tier | p14 | value_at_risk | next_best_action | top_drivers | last_ticket_summary | ai_message |
|---|---|---|---|---|---|---|---|---|
| 1 | P0046644 | whale | 0.724 | 1432.91 | PERSONALISED_OFFER | Hasn't logged in recently ; Not in a guild ; Play frequency dropping |  | Commander, the Rift stirs at Level 87, and your banner is always welcome here. We've prepared a personalised offer in the Shop, picked for your journey. Take it or leave it, no rush. Guilds across Emberline are also recruiting if you'd like allies at your side. |
| 2 | P0007755 | whale | 0.445 | 1033.74 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) ; Crashing on device | Player reports a failed purchase where payment was still charged to their card. | Hail, Rift Warden. We're sorry your purchase failed after payment went through. Our support team is prioritizing your case to restore your items. We're also sorry about the crashes; we're working on stability fixes for your device. Your guild and the Rift await your return. |
| 3 | P0031051 | whale | 0.739 | 1014.81 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) | Purchase failed but payment was charged to card; player will stop spending. | Greetings, Rift Commander! Our Support team has escalated your recent purchase issue. We're fixing it and will restore your missing items. Thank you for your patience. We'll send word here the moment it's done. Your guildmates and the Rift will be waiting whenever you're ready. |
| 4 | P0029369 | whale | 0.907 | 892.84 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) ; Not in a guild | Purchase failed but payment was charged to the player's card. | Hail, Rift Commander. We're sorry your recent purchase didn't arrive as it should. Our support team has escalated your case and is working to fix it and restore your items. Once it's resolved, they'll arrive right here in your mailbox. Thank you for your patience and your long service in the Rift. |
| 5 | P0039162 | whale | 0.823 | 395.93 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) ; Play frequency dropping | Player bought the season pass but did not receive its rewards. | Hail, Rift Commander. We're sorry your Season Pass rewards never arrived. Our team is working on your ticket to restore everything you're owed, and we'll update you here as soon as it's done. Your guildmates and the Rift await whenever you're ready. Thank you for your patience. |
| 6 | P0049967 | whale | 0.506 | 210.95 | EVENT_REENGAGEMENT_PUSH | Hasn't logged in recently ; Not in a guild |  | Hail, Rift Warden! The embers still burn for you. A fresh rift event has opened, with new foes and rewards waiting for a level 48 tactician. Gather allies, or find a guild to fight beside, and return when the call suits you. Your realm awaits. |
| 7 | P0037483 | whale | 0.457 | 176.93 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) ; Not in a guild | Player purchased the season pass but did not receive its rewards. | Hail, Rift Walker. We're sorry your Season Pass rewards never arrived. Our team is looking into your ticket as a priority and will restore everything owed to you. Once it's settled, you'll get a confirmation here. Thank you for your patience. Your place in Emberline awaits. |
| 8 | P0024131 | whale | 0.226 | 149.3 | PERSONALISED_OFFER | Hasn't logged in recently ; Not in a guild |  | Welcome back, Rift Walker! The Rift has stirred while you were away. Guild halls are open if you'd like allies at your side, and a personalised offer is waiting in the shop whenever you're ready. No rush. Your legend, your pace. |
| 9 | P0011897 | whale | 0.183 | 138.09 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) ; Not in a guild | Player bought the season pass but did not receive its rewards. | Greetings, Rift Walker. We're sorry your Season Pass rewards never reached you. Our support team is escalating your ticket to restore every missing reward to your account. We'll send word here once the restoration is complete. Thank you for your patience, and the Rift will be ready when you return. |
| 10 | P0025493 | whale | 0.079 | 129.74 | SUPPORT_ESCALATION | Hasn't logged in recently ; Unresolved payment issue (ticket) | Player purchased season pass but did not receive the rewards. | Greetings, Rift Commander! We're sorry your Season Pass rewards never reached your vault. Our support guild has escalated your ticket and is working to restore every reward. We'll send word here as soon as they arrive. Thank you for your patience, and your place in the Rift awaits. |

## Governance: masked PII as seen by a non-privileged user

```sql
SELECT player_id, email, device_id, birth_year, age_band, is_minor FROM aws_demo_catalog.playerpulse_game.silver_players LIMIT 5
```

| player_id | email | device_id | birth_year | age_band | is_minor |
|---|---|---|---|---|---|
| P0000002 | pla****** | IOS****** |  | 25-34 | false |
| P0000005 | pla****** | AND****** |  | 35-44 | false |
| P0000006 | pla****** | AND****** |  | 18-24 | false |
| P0000007 | pla****** | AND****** |  | 25-34 | false |
| P0000009 | pla****** | IOS****** |  | 25-34 | false |

## Governance: responsible-monetization policy (no paid offers to minors / no consent)

```sql
SELECT is_minor, marketing_opt_in, paid_offer_eligible, count(*) players, sum(CASE WHEN next_best_action='PERSONALISED_OFFER' THEN 1 ELSE 0 END) personalised_offers
FROM aws_demo_catalog.playerpulse_serving.player_retention_queue GROUP BY ALL ORDER BY ALL
```

| is_minor | marketing_opt_in | paid_offer_eligible | players | personalised_offers |
|---|---|---|---|---|
| false | false | false | 14874 | 0 |
| false | true | true | 23888 | 4336 |
| true | false | false | 1961 | 0 |
| true | true | false | 3151 | 0 |

## Governance: column tags

```sql
SELECT schema_name, table_name, column_name, tag_name, tag_value FROM aws_demo_catalog.information_schema.column_tags WHERE schema_name LIKE 'playerpulse%' ORDER BY ALL
```

| schema_name | table_name | column_name | tag_name | tag_value |
|---|---|---|---|---|

## Governance: lineage captured by Unity Catalog

```sql
SELECT DISTINCT source_table_full_name, target_table_full_name FROM system.access.table_lineage
WHERE target_table_full_name LIKE 'aws_demo_catalog.playerpulse%' AND source_table_full_name IS NOT NULL AND event_date >= current_date() - INTERVAL 7 DAYS
ORDER BY 2, 1
```

| source_table_full_name | target_table_full_name |
|---|---|
| aws_demo_catalog.playerpulse_game.silver_player_daily | aws_demo_catalog.playerpulse_game.gold_daily_kpis |
| aws_demo_catalog.playerpulse_game.silver_players | aws_demo_catalog.playerpulse_game.gold_daily_kpis |
| aws_demo_catalog.playerpulse_game.silver_purchases | aws_demo_catalog.playerpulse_game.gold_daily_kpis |
| aws_demo_catalog.playerpulse_game.silver_player_daily | aws_demo_catalog.playerpulse_game.gold_player_360_current |
| aws_demo_catalog.playerpulse_game.silver_players | aws_demo_catalog.playerpulse_game.gold_player_360_current |
| aws_demo_catalog.playerpulse_game.silver_purchases | aws_demo_catalog.playerpulse_game.gold_player_360_current |
| aws_demo_catalog.playerpulse_game.silver_support_tickets | aws_demo_catalog.playerpulse_game.gold_player_360_current |
| aws_demo_catalog.playerpulse_game.silver_player_daily | aws_demo_catalog.playerpulse_game.gold_retention_cohorts |
| aws_demo_catalog.playerpulse_game.silver_players | aws_demo_catalog.playerpulse_game.gold_retention_cohorts |
| aws_demo_catalog.playerpulse_game.silver_player_daily | aws_demo_catalog.playerpulse_game.gold_weekly_churn |
| aws_demo_catalog.playerpulse_game.silver_purchases | aws_demo_catalog.playerpulse_game.gold_weekly_churn |
| aws_demo_catalog.playerpulse_game.bronze_liveops_calendar | aws_demo_catalog.playerpulse_game.silver_liveops_calendar |
| aws_demo_catalog.playerpulse_game.bronze_telemetry_daily | aws_demo_catalog.playerpulse_game.silver_player_daily |
| aws_demo_catalog.playerpulse_game.bronze_store_receipts | aws_demo_catalog.playerpulse_game.silver_purchases |
| aws_demo_catalog.playerpulse_game.bronze_support_tickets | aws_demo_catalog.playerpulse_game.silver_support_tickets |
| aws_demo_catalog.playerpulse_serving.player_retention_queue_stage | aws_demo_catalog.playerpulse_ml.ai_winback_messages |
| aws_demo_catalog.playerpulse_game.silver_player_daily | aws_demo_catalog.playerpulse_ml.player_features_pit |
| aws_demo_catalog.playerpulse_game.silver_players | aws_demo_catalog.playerpulse_ml.player_features_pit |
| aws_demo_catalog.playerpulse_game.silver_purchases | aws_demo_catalog.playerpulse_ml.player_features_pit |
| aws_demo_catalog.playerpulse_ml.ticket_insights | aws_demo_catalog.playerpulse_ml.player_features_pit |
| aws_demo_catalog.playerpulse_game.silver_support_tickets | aws_demo_catalog.playerpulse_ml.ticket_insights |
| aws_demo_catalog.playerpulse_ml.ticket_insights | aws_demo_catalog.playerpulse_ml.ticket_insights |
| aws_demo_catalog.playerpulse_ml.ai_winback_messages | aws_demo_catalog.playerpulse_serving.player_retention_queue |
| aws_demo_catalog.playerpulse_serving.player_retention_queue_stage | aws_demo_catalog.playerpulse_serving.player_retention_queue |
| aws_demo_catalog.playerpulse_game.gold_player_360_current | aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |
| aws_demo_catalog.playerpulse_game.silver_players | aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |
| aws_demo_catalog.playerpulse_ml.player_churn_scores | aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |
| aws_demo_catalog.playerpulse_ml.ticket_insights | aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |
| aws_demo_catalog.playerpulse_serving.player_retention_queue_stage | aws_demo_catalog.playerpulse_serving.player_retention_queue_stage |
| aws_demo_catalog.playerpulse_serving.player_retention_queue | aws_demo_catalog.playerpulse_serving.player_retention_queue_synced |

