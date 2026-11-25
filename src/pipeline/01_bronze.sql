-- =====================================================================================
-- PlayerPulse · Lakeflow Declarative Pipeline · BRONZE
-- Incremental ingestion (Auto Loader via STREAM read_files) of raw exports that Emberforge's
-- systems drop into the Unity Catalog volume /Volumes/<catalog>/playerpulse_raw/landing/
-- Every row keeps file-level lineage (_source_file, _ingested_at).
-- Player accounts (PII) are NOT landed in bronze: they are read straight into a masked silver table.
-- =====================================================================================

CREATE OR REFRESH STREAMING TABLE bronze_telemetry_daily
COMMENT 'Game-server daily per-player telemetry aggregates (raw, append-only). Source: telemetry_daily/*.csv.gz'
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'game servers')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/playerpulse_raw/landing/telemetry_daily/',
  format => 'csv', header => true,
  schemaHints => 'player_id STRING, activity_date DATE, sessions INT, minutes_played DOUBLE, matches INT, wins INT, losses INT, energy_walls INT, crashes INT, avg_latency_ms DOUBLE, max_level INT, guild_id INT, client_version STRING'
);

CREATE OR REFRESH STREAMING TABLE bronze_store_receipts
COMMENT 'App Store / Google Play purchase receipts (raw JSON lines). Source: store_transactions/*.json'
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'store receipts')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/playerpulse_raw/landing/store_transactions/',
  format => 'json',
  schemaHints => 'transaction_id STRING, player_id STRING, purchase_ts TIMESTAMP, store STRING, sku STRING, amount_usd DOUBLE, currency STRING, status STRING'
);

CREATE OR REFRESH STREAMING TABLE bronze_support_tickets
COMMENT 'Helpdesk tickets and in-game feedback, free text (raw JSON lines). Source: support_tickets/*.json'
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'helpdesk + in-game feedback')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/playerpulse_raw/landing/support_tickets/',
  format => 'json',
  schemaHints => 'ticket_id STRING, player_id STRING, created_ts TIMESTAMP, channel STRING, message STRING'
);

CREATE OR REFRESH STREAMING TABLE bronze_liveops_calendar
COMMENT 'LiveOps calendar: seasons, events and client releases (raw). Source: liveops_calendar/*.csv'
TBLPROPERTIES ('quality' = 'bronze', 'source_system' = 'LiveOps planning')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/playerpulse_raw/landing/liveops_calendar/',
  format => 'csv', header => true,
  schemaHints => 'entry_type STRING, name STRING, start_date DATE, end_date DATE, description STRING'
);
