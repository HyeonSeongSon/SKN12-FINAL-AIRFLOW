#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
청탁금지법 데이터 크롤링 Airflow DAG
매일 14:00에 청탁금지법 데이터 수집 및 처리
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import sys
import subprocess
import logging
import pendulum

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 한국 시간대 설정
local_tz = pendulum.timezone('Asia/Seoul')

# 기본 DAG 설정
default_args = {
    'owner': 'anticorruption-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 7, 14, 0, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'catchup': False
}

def run_anticorruption_crawler():
    """청탁금지법 크롤러 실행"""
    try:
        # func 디렉토리 경로 설정
        func_dir = os.path.join(os.path.dirname(current_dir), 'func')
        crawler_path = os.path.join(func_dir, 'anticorruption_law_crawler.py')
        
        logging.info(f"청탁금지법 크롤러 시작: {crawler_path}")
        
        # Python 스크립트 실행
        result = subprocess.run(
            ['python3', crawler_path],
            cwd=func_dir,
            capture_output=True,
            text=True,
            timeout=600  # 10분 타임아웃
        )
        
        if result.returncode == 0:
            logging.info(f"청탁금지법 크롤링 성공:\n{result.stdout}")
        else:
            logging.error(f"청탁금지법 크롤링 실패:\n{result.stderr}")
            raise Exception(f"크롤링 실패: {result.stderr}")
        
        return "청탁금지법 크롤링 완료"
        
    except subprocess.TimeoutExpired:
        logging.error("청탁금지법 크롤링 타임아웃 (10분)")
        raise Exception("크롤링 타임아웃")
    except Exception as e:
        logging.error(f"청탁금지법 크롤링 중 오류: {str(e)}")
        raise

def process_law_files():
    """법률 파일 처리 (변경사항 확인 및 파일 정리)"""
    try:
        # func 디렉토리 경로 설정
        func_dir = os.path.join(os.path.dirname(current_dir), 'func')
        logic_path = os.path.join(func_dir, 'anticorruption_law_logic.py')
        
        logging.info(f"법률 파일 처리 시작: {logic_path}")
        
        # Python 스크립트 실행
        result = subprocess.run(
            ['python3', logic_path],
            cwd=func_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )
        
        if result.returncode == 0:
            logging.info(f"법률 파일 처리 성공:\n{result.stdout}")
        else:
            logging.error(f"법률 파일 처리 실패:\n{result.stderr}")
            raise Exception(f"파일 처리 실패: {result.stderr}")
        
        return "법률 파일 처리 완료"
        
    except subprocess.TimeoutExpired:
        logging.error("법률 파일 처리 타임아웃 (5분)")
        raise Exception("파일 처리 타임아웃")
    except Exception as e:
        logging.error(f"법률 파일 처리 중 오류: {str(e)}")
        raise

# DAG 정의
dag = DAG(
    'anticorruption_law_crawler',
    default_args=default_args,
    description='청탁금지법 데이터 크롤링 및 처리',
    schedule='0 13 * * *',  # 매일 13:00 (한국시간)
    max_active_runs=1,
    tags=['law', 'anticorruption', 'crawler']
)

# 태스크 1: 청탁금지법 크롤링
crawl_task = PythonOperator(
    task_id='crawl_anticorruption_law',
    python_callable=run_anticorruption_crawler,
    dag=dag
)

# 태스크 2: 법률 파일 처리
process_task = PythonOperator(
    task_id='process_law_files',
    python_callable=process_law_files,
    dag=dag
)

# 태스크 의존성 설정: 크롤링 → 파일 처리
crawl_task >> process_task