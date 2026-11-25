# Unity Catalog model registry (real API output)

```json
{
  "full_name": "aws_demo_catalog.playerpulse_ml.player_churn_risk",
  "comment": "P(no play in next 14 days) for players active in the last 7 days (HistGradientBoosting). Features: engagement, economy friction, crashes, spend, GenAI ticket signals.",
  "aliases": [
    {
      "alias_name": "champion",
      "id": "45968b7e-a30a-4ca6-97ad-49665394794d",
      "version_num": 2
    }
  ],
  "owner": "shuheng.pi@databricks.com",
  "created_at": 1795617754151,
  "updated_at": 1795618485944
}
```

## Model versions
```json
[
  {
    "version": 2,
    "status": "READY",
    "run_id": "bb24fd56729742a8b02599e3333c3a68",
    "source": "models:/m-61ce7f5c88504da2ad08e1db5ec39181",
    "created_at": 1795618483745
  },
  {
    "version": 1,
    "status": "READY",
    "run_id": "2468889831cd45a881b8792b532b1be5",
    "source": "models:/m-45a5ec2dbbad45eaa19bea4ccddf7e04",
    "created_at": 1795617754545
  }
]
```
