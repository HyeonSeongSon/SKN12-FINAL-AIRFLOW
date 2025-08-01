from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, chain
import datetime
import pendulum

with DAG(
    dag_id="dag_operator",
    schedule="0 0 1 * *",
    start_date=pendulum.datetime(2025, 8, 1, tz="Aisa/Seoul"),
    catchup=False,
    tags=["Naver_News_Crowring", "Preprocessing", "Insert_DB"],
) as dag:
    pass