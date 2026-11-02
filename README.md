# rds-observability-pipeline

A scheduled Lambda that watches a list of RDS/Aurora PostgreSQL instances
and sends an SNS alert when something is off: an instance not available,
CPU over threshold, or connection count over threshold.

Portfolio implementation of patterns I use as an AWS DBA / data engineer.
It watches databases; it does not claim to have run anywhere specific.

## Run

1. Set the Lambda environment variables from config.json: instance IDs,
   SNS topic ARN, and thresholds.
2. Package handler.py with boto3 and deploy it as a Lambda.
3. Trigger it on a schedule with EventBridge. Every 5 minutes is a
   reasonable start.
