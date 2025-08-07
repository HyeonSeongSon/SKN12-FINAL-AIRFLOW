#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIRA 고시 데이터 크롤링 Airflow DAG
매일 13:00에 HIRA 고시 데이터 수집
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
    'owner': 'hira-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 6, 13, 0, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'catchup': False
}

# DAG 정의
dag = DAG(
    'hira_crawler_daily',
    default_args=default_args,
    description='매일 13시에 HIRA 고시 데이터를 크롤링하는 DAG',
    schedule='0 13 * * *',
    max_active_runs=1,
    tags=['hira', 'crawler', 'daily']
)

def run_hira_crawler():
    """HIRA 크롤러 실행 함수"""
    try:
        # 크롤러 스크립트 경로
        crawler_script = '/opt/airflow/func/hira_crawler.py'
        
        logging.info(f"🏥 HIRA 크롤러 시작: {crawler_script}")
        
        # Python 스크립트 실행 - 실시간 출력
        env = os.environ.copy()
        process = subprocess.Popen(
            [sys.executable, '-u', crawler_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd='/opt/airflow/func',
            env=env,
            bufsize=1
        )
        
        # 실시간으로 stdout 출력
        output_lines = []
        error_lines = []
        
        # 타임아웃 설정
        import time
        start_time = time.time()
        timeout = 1800  # 30분
        
        while True:
            # 타임아웃 체크
            if time.time() - start_time > timeout:
                process.terminate()
                logging.error(f"❌ 타임아웃: {timeout}초 초과")
                raise subprocess.TimeoutExpired(cmd=[sys.executable, crawler_script], timeout=timeout)
            
            # stdout 읽기
            line = process.stdout.readline()
            if line:
                line = line.rstrip()
                output_lines.append(line)
                logging.info(f"[HIRA 크롤러] {line}")
            
            # 프로세스 종료 확인
            if process.poll() is not None:
                # 남은 출력 읽기
                for line in process.stdout:
                    line = line.rstrip()
                    output_lines.append(line)
                    logging.info(f"[HIRA 크롤러] {line}")
                
                # stderr 읽기
                for line in process.stderr:
                    line = line.rstrip()
                    error_lines.append(line)
                    logging.error(f"[HIRA 크롤러 에러] {line}")
                break
            
            # CPU 사용률을 낮추기 위한 짧은 대기
            time.sleep(0.01)
        
        return_code = process.returncode
        full_output = '\n'.join(output_lines)
        full_error = '\n'.join(error_lines)
        
        # 실행 결과 처리
        if return_code == 0:
            logging.info("✅ HIRA 크롤링 프로세스 완료")
            
            # 생성된 파일 확인
            import glob
            func_dir = '/opt/airflow/func'
            json_files = glob.glob(os.path.join(func_dir, 'hira_data_*.json'))
            if json_files:
                latest_file = max(json_files, key=os.path.getctime)
                logging.info(f"생성된 파일: {latest_file}")
                return {'status': 'success', 'file': latest_file, 'output': full_output}
            else:
                logging.warning("JSON 파일이 생성되지 않았습니다.")
                return {'status': 'warning', 'message': 'JSON 파일 없음', 'output': full_output}
        else:
            logging.error(f"❌ HIRA 크롤링 실패 (exit code: {return_code})")
            if full_error:
                logging.error(f"에러 출력:\n{full_error}")
            raise RuntimeError(f"크롤러 실행 실패: {full_error or '알 수 없는 오류'}")
            
    except subprocess.TimeoutExpired:
        logging.error("❌ HIRA 크롤러 타임아웃 (30분)")
        raise RuntimeError("크롤러 실행 타임아웃")
    except Exception as e:
        logging.error(f"❌ HIRA 크롤러 실행 중 오류: {e}")
        raise

def check_and_notify(**context):
    """크롤링 결과 확인"""
    try:
        # 이전 태스크 결과 가져오기
        task_result = context['task_instance'].xcom_pull(task_ids='run_crawler')
        
        if task_result and task_result.get('status') == 'success':
            logging.info("✅ HIRA 크롤링 성공")
            
            # 결과 파일 정보
            result_file = task_result.get('file', 'Unknown')
            file_name = os.path.basename(result_file) if result_file != 'Unknown' else 'Unknown'
            
            logging.info(f"📊 실행 정보:")
            logging.info(f"- 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"- 생성 파일: {file_name}")
            logging.info(f"- 대상: HIRA 고시 데이터 (어제~오늘)")
            logging.info(f"- 파일 위치: {result_file}")
            logging.info("✅ HIRA 고시 데이터 크롤링이 완료되었습니다.")
            
            return {'status': 'success', 'file': result_file}
        else:
            logging.warning("⚠️ HIRA 크롤링 부분 성공 또는 실패")
            logging.warning(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.warning(f"상태: {task_result.get('status', 'Unknown') if task_result else 'Failed'}")
            logging.warning(f"메시지: {task_result.get('message', 'No message') if task_result else 'Task failed'}")
            
            return {'status': 'warning', 'message': task_result.get('message', 'No message') if task_result else 'Task failed'}
            
    except Exception as e:
        logging.error(f"❌ 결과 확인 중 오류: {e}")
        logging.error(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return {'status': 'error', 'message': str(e)}

# Task 정의
crawler_task = PythonOperator(
    task_id='run_crawler',
    python_callable=run_hira_crawler,
    dag=dag,
    execution_timeout=timedelta(minutes=30)
)

check_task = PythonOperator(
    task_id='check_result',
    python_callable=check_and_notify,
    dag=dag,
)

# Task 의존성 설정
crawler_task >> check_task