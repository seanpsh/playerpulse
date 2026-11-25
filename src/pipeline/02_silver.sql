-- =====================================================================================
-- PlayerPulse · Lakeflow Declarative Pipeline · SILVER
-- Typed, de-duplicated, quality-checked entities. Expectations drop bad records; pass/fail
-- counts land in the pipeline event log (data-quality evidence).
-- =====================================================================================

-- PII never lands unmasked: the account-service extract is read straight into a masked table.
-- Mask policy functions are created in notebook 00 (schema playerpulse_governance).
CREATE OR REFRESH MATERIALIZED VIEW silver_players (
  player_id STRING COMMENT 'Game account id',
  email STRING MASK ${catalog}.playerpulse_governance.mask_pii COMMENT 'PII - masked',
  device_id STRING MASK ${catalog}.playerpulse_governance.mask_pii COMMENT 'PII (device advertising id) - masked',
  birth_year INT MASK ${catalog}.playerpulse_governance.mask_int COMMENT 'PII - masked; use age_band / is_minor',
  age_band STRING COMMENT '13-17, 18-24, 25-34, 35-44, 45+',
  is_minor BOOLEAN COMMENT 'Under 18. Responsible-monetization policy: never targeted with paid offers.',
  platform STRING, device_tier STRING COMMENT 'low / mid / high GPU tier', region STRING, country_code STRING,
  acquisition_channel STRING, install_date DATE,
  marketing_opt_in BOOLEAN COMMENT 'Consent to marketing messages (offers require opt-in)',
  CONSTRAINT valid_player EXPECT (player_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_age EXPECT (birth_year BETWEEN 1940 AND 2013) ON VIOLATION DROP ROW
)
COMMENT 'One row per player account (deduplicated). Contains PII protected by Unity Catalog column masks.'
TBLPROPERTIES ('quality' = 'silver', 'contains_pii' = 'true')
AS SELECT player_id, email, device_id, birth_year,
  CASE WHEN 2026 - birth_year < 18 THEN '13-17' WHEN 2026 - birth_year < 25 THEN '18-24'
       WHEN 2026 - birth_year < 35 THEN '25-34' WHEN 2026 - birth_year < 45 THEN '35-44' ELSE '45+' END AS age_band,
  (2026 - birth_year) < 18 AS is_minor,
  platform, device_tier, region, country_code, acquisition_channel, install_date, marketing_opt_in
FROM (
  SELECT player_id, email, device_id, CAST(birth_year AS INT) AS birth_year, platform, device_tier, region, country_code,
         acquisition_channel, CAST(install_date AS DATE) AS install_date, CAST(marketing_opt_in AS BOOLEAN) AS marketing_opt_in,
         row_number() OVER (PARTITION BY player_id ORDER BY install_date) AS rn
  FROM read_files('/Volumes/${catalog}/playerpulse_raw/landing/player_accounts/', format => 'csv', header => true)
) WHERE rn = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_player_daily (
  CONSTRAINT valid_player EXPECT (player_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT non_negative_play EXPECT (minutes_played >= 0 AND sessions >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT consistent_matches EXPECT (wins + losses = matches) ON VIOLATION DROP ROW,
  CONSTRAINT plausible_latency EXPECT (avg_latency_ms BETWEEN 5 AND 2000)
)
COMMENT 'Daily per-player activity (deduplicated). Grain: player_id x activity_date. A row exists only on days the player played.'
TBLPROPERTIES ('quality' = 'silver')
AS SELECT player_id, activity_date, sessions, minutes_played, matches, wins, losses, energy_walls, crashes,
  avg_latency_ms, max_level, guild_id, guild_id > 0 AS in_guild, client_version
FROM (
  SELECT *, row_number() OVER (PARTITION BY player_id, activity_date ORDER BY _ingested_at DESC) AS rn
  FROM bronze_telemetry_daily
) WHERE rn = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_purchases (
  CONSTRAINT valid_txn EXPECT (transaction_id IS NOT NULL AND player_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_status EXPECT (status IN ('COMPLETED', 'REFUNDED')) ON VIOLATION DROP ROW,
  CONSTRAINT refund_sign EXPECT ((status = 'REFUNDED') = (amount_usd < 0))
)
COMMENT 'Store purchases (deduplicated). Refunds are negative amounts. net revenue = sum(amount_usd).'
TBLPROPERTIES ('quality' = 'silver')
AS SELECT DISTINCT transaction_id, player_id, purchase_ts, CAST(purchase_ts AS DATE) AS purchase_date,
  store, sku, amount_usd, currency, status
FROM bronze_store_receipts;

CREATE OR REFRESH MATERIALIZED VIEW silver_support_tickets (
  CONSTRAINT valid_ticket EXPECT (ticket_id IS NOT NULL AND message IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Helpdesk tickets and in-game feedback (free text). GenAI (ai_query) classifies them in playerpulse_ml.ticket_insights.'
TBLPROPERTIES ('quality' = 'silver')
AS SELECT DISTINCT ticket_id, player_id, created_ts, CAST(created_ts AS DATE) AS created_date, channel, trim(message) AS message
FROM bronze_support_tickets;

CREATE OR REFRESH MATERIALIZED VIEW silver_liveops_calendar
COMMENT 'LiveOps calendar: seasons, events, client releases (with known issues). Use to explain KPI movements.'
TBLPROPERTIES ('quality' = 'silver')
AS SELECT DISTINCT entry_type, name, start_date, end_date, description FROM bronze_liveops_calendar;
