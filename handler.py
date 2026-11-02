"""Lambda: check RDS instances and alert on problems.

Runs on a schedule. It reads the instance list and thresholds from
environment variables, pulls a few CloudWatch metrics per instance, and
publishes one SNS message per problem found. No message means nothing
breached, which is the normal case.
"""

import os
from datetime import datetime, timedelta, timezone

import boto3

rds = boto3.client("rds")
cloudwatch = boto3.client("cloudwatch")
sns = boto3.client("sns")

INSTANCE_IDS = [
    i.strip()
    for i in os.environ.get("DB_INSTANCE_IDS", "").split(",")
    if i.strip()
]
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
CPU_THRESHOLD = float(os.environ.get("CPU_THRESHOLD", "80"))
CONNECTION_THRESHOLD = int(os.environ.get("CONNECTION_THRESHOLD", "800"))
PERIOD_HOURS = int(os.environ.get("METRIC_PERIOD_HOURS", "1"))


def instance_status(instance_id):
    resp = rds.describe_db_instances(DBInstanceIdentifier=instance_id)
    return resp["DBInstances"][0]["DBInstanceStatus"]


def metric_average(instance_id, metric):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=PERIOD_HOURS)
    resp = cloudwatch.get_metric_statistics(
        Namespace="AWS/RDS",
        MetricName=metric,
        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    points = resp.get("Datapoints", [])
    if not points:
        return None
    return sum(p["Average"] for p in points) / len(points)


def check_instance(instance_id):
    problems = []
    status = instance_status(instance_id)
    if status != "available":
        problems.append(f"{instance_id} status is {status}")
    cpu = metric_average(instance_id, "CPUUtilization")
    if cpu is not None and cpu > CPU_THRESHOLD:
        problems.append(
            f"{instance_id} CPU avg {cpu:.1f}% over {PERIOD_HOURS}h "
            f"(threshold {CPU_THRESHOLD}%)"
        )
    conns = metric_average(instance_id, "DatabaseConnections")
    if conns is not None and conns > CONNECTION_THRESHOLD:
        problems.append(
            f"{instance_id} connections avg {conns:.0f} "
            f"(threshold {CONNECTION_THRESHOLD})"
        )
    return problems


def handler(event, context):
    all_problems = []
    for instance_id in INSTANCE_IDS:
        all_problems.extend(check_instance(instance_id))
    if all_problems and SNS_TOPIC_ARN:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="RDS alert",
            Message="\n".join(all_problems),
        )
    return {"checked": len(INSTANCE_IDS), "problems": len(all_problems)}
