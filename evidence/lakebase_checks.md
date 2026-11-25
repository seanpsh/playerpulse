# Lakebase checks (real Postgres output via the playerpulse-lakebase-admin job, run 133204637048798)

```text
-- SELECT rolname FROM pg_roles WHERE rolname = '8ab0e2ad-8163-4a96-8e93-cec03a3904b9'
rolname
8ab0e2ad-8163-4a96-8e93-cec03a3904b9
-- GRANT USAGE ON SCHEMA playerpulse_serving TO "8ab0e2ad-8163-4a96-8e93-cec03a3904b9"
GRANT
-- GRANT SELECT ON ALL TABLES IN SCHEMA playerpulse_serving TO "8ab0e2ad-8163-4a96-8e93-cec03a3904b9"
GRANT
-- ALTER DEFAULT PRIVILEGES IN SCHEMA playerpulse_serving GRANT SELECT ON TABLES TO "8ab0e2ad-8163-4a96-8e93-cec03a3904b9"
ALTER DEFAULT PRIVILEGES
-- SELECT count(*) AS rows_in_lakebase FROM playerpulse_serving.player_retention_queue_synced
rows_in_lakebase
43874
```
