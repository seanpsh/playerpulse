# Databricks App deployment check (real API output)

App URL (workspace SSO required): https://playerpulse-7474659338788077.aws.databricksapps.com

```json
{
  "name": "playerpulse",
  "description": "PlayerPulse - LiveOps retention console (Emberforge, synthetic data)",
  "url": "https://playerpulse-7474659338788077.aws.databricksapps.com",
  "app_status": {
    "message": "App has status: App is running",
    "state": "RUNNING"
  },
  "compute_status": {
    "message": "App compute is running.",
    "state": "ACTIVE"
  },
  "service_principal_client_id": "8ab0e2ad-8163-4a96-8e93-cec03a3904b9",
  "resources": [
    {
      "database": {
        "database_name": "playerpulse",
        "instance_name": "playerpulse-lakebase",
        "permission": "CAN_CONNECT_AND_CREATE"
      },
      "name": "lakebase"
    },
    {
      "name": "sql-warehouse",
      "sql_warehouse": {
        "id": "4b55146770394f51",
        "permission": "CAN_USE"
      }
    },
    {
      "genie_space": {
        "name": "PlayerPulse",
        "permission": "CAN_RUN",
        "space_id": "01f1e8deefe41e469de20a4ea139c622"
      },
      "name": "genie-space"
    }
  ],
  "active_deployment": {
    "create_time": "2026-11-25T14:48:45Z",
    "creator": "shuheng.pi@databricks.com",
    "deployment_artifacts": {
      "source_code_path": "/Workspace/Users/8ab0e2ad-8163-4a96-8e93-cec03a3904b9/src/01f1e8df50d51ee68140c9684f02c9f2"
    },
    "deployment_id": "01f1e8df50d51ee68140c9684f02c9f2",
    "mode": "SNAPSHOT",
    "scan_omitted_count_is_lower_bound": false,
    "scan_omitted_findings_count": 0,
    "scan_status": "APP_DEPLOYMENT_SCAN_STATUS_UNSPECIFIED",
    "source_code_path": "/Workspace/Users/shuheng.pi@databricks.com/.bundle/playerpulse/dev/files/app",
    "status": {
      "message": "App started successfully",
      "state": "SUCCEEDED"
    },
    "update_time": "2026-11-25T14:48:58Z"
  }
}
```
