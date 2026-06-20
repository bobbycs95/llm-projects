"""
Airflow DAG: Daily LLM Stats ingestion at 01:00 WIB (18:00 UTC)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "admin",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="llm_stats_daily_ingestion",
    default_args=default_args,
    description="Daily ETL from LLM Stats API to Postgres (01:00 WIB / 18:00 UTC)",
    schedule_interval="0 18 * * *",
    start_date=datetime(2026, 6, 20),
    catchup=False,
    tags=["llm-stats", "etl"],
) as dag:

    run_etl = BashOperator(
        task_id="run_etl",
        bash_command="python /opt/airflow/scripts/etl.py",
    )
