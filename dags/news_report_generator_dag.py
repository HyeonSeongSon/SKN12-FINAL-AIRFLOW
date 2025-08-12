#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
제약영업회사 전략 보고서 생성 DAG
매일 13시 30분에 크롤링된 뉴스 데이터를 기반으로 전략 보고서 생성
"""

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import subprocess
import logging
import pendulum

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))

# .env 파일에서 환경변수 로드
def load_env_variables():
    """프로젝트 루트의 .env 파일에서 환경변수 로드"""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(current_dir), '.env')
        load_dotenv(env_path)
        logging.info(f"환경변수 로드 완료: {env_path}")
    except ImportError:
        logging.warning("python-dotenv 패키지가 없습니다. 환경변수를 직접 설정합니다.")
        # .env 파일 직접 읽기
        env_path = os.path.join(os.path.dirname(current_dir), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            logging.info(f"환경변수 직접 로드 완료: {env_path}")
    except Exception as e:
        logging.error(f"환경변수 로드 실패: {e}")

# Docker 환경에서는 환경변수가 이미 설정되어 있으므로 로컬에서만 로드
if not os.getenv('AIRFLOW__CORE__EXECUTOR'):
    load_env_variables()

# 한국 시간대 설정
local_tz = pendulum.timezone('Asia/Seoul')

# 기본 DAG 설정
default_args = {
    'owner': 'report-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 12, 13, 30, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'catchup': False  # 과거 실행 건너뛰기
}

# DAG 정의
dag = DAG(
    'news_report_generator_v1',
    default_args=default_args,
    description='제약영업회사 전략 보고서 생성',
    schedule='30 13 * * 1-5',  # 평일 13:30
    max_active_runs=1,
    tags=['report', 'strategy', 'pharmaceutical', 'ai']
)

def run_report_generator():
    """뉴스 보고서 생성기 실행 함수"""
    try:
        # Docker 환경에서는 환경변수가 이미 설정되어 있으므로 로컬에서만 로드
        if not os.getenv('AIRFLOW__CORE__EXECUTOR'):
            load_env_variables()
        
        # 보고서 생성기 스크립트 경로
        if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
            script_path = '/opt/airflow/func/news_report_generator.py'
        else:  # 로컬 환경
            script_path = os.path.join(os.path.dirname(current_dir), 'func', 'news_report_generator.py')
        
        # 환경변수 설정 확인
        openai_key = os.getenv('OPENAI_API_KEY')
        logging.info(f"태스크 실행 시 OPENAI_API_KEY 확인: {openai_key[:10] if openai_key else 'NOT_SET'}...")
        
        if not openai_key:
            # .env 파일에서 직접 읽어서 설정 시도
            env_path = os.path.join(os.path.dirname(current_dir), '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY='):
                            key_value = line.split('=', 1)[1].strip()
                            os.environ['OPENAI_API_KEY'] = key_value
                            openai_key = key_value
                            logging.info("✅ .env에서 OPENAI_API_KEY 직접 로드 성공")
                            break
            
            if not openai_key:
                raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
        logging.info(f"📊 보고서 생성기 시작: {script_path}")
        
        # Python 스크립트 실행
        env = os.environ.copy()
        # Airflow 사용자의 Python 환경 사용
        env['PATH'] = '/home/airflow/.local/bin:' + env.get('PATH', '')
        process = subprocess.Popen(
            ['/home/airflow/.local/bin/python3', '-u', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # stderr을 stdout과 합침
            text=True,
            cwd='/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func'),
            env=env,
            bufsize=1,
            universal_newlines=True
        )
        
        # 실시간 로그 출력
        logging.info("📊 실시간 보고서 생성 로그 시작...")
        output_lines = []
        
        try:
            # 실시간으로 출력 읽기
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    output_lines.append(line)
                    # Airflow 로그에 실시간 출력
                    logging.info(f"📋 {line}")
            
            # 프로세스 완료 대기
            process.wait()
            stdout = '\n'.join(output_lines)
            
            if process.returncode == 0:
                logging.info("✅ 전략 보고서 생성 완료")
                
                # 생성된 파일 확인
                import glob
                result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
                report_files = glob.glob(os.path.join(result_dir, 'pharmaceutical_strategy_report_*.md'))
                
                if report_files:
                    latest_file = max(report_files, key=os.path.getctime)
                    logging.info(f"생성된 보고서: {latest_file}")
                    return {'status': 'success', 'file': latest_file, 'output': stdout}
                else:
                    logging.warning("보고서 파일이 생성되지 않았습니다.")
                    return {'status': 'warning', 'message': '보고서 파일 없음', 'output': stdout}
            else:
                error_output = '\n'.join(output_lines[-10:])  # 마지막 10줄만 에러로 표시
                logging.error(f"❌ 보고서 생성 실패 (리턴코드: {process.returncode})")
                logging.error(f"마지막 출력: {error_output}")
                raise RuntimeError(f"보고서 생성기 실행 실패 (리턴코드: {process.returncode})")
                
        except Exception as proc_e:
            # 프로세스가 여전히 실행 중이면 종료
            if process.poll() is None:
                logging.warning("⏰ 프로세스 강제 종료 중...")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    logging.error("💀 프로세스 강제 종료")
            
            logging.error(f"❌ 보고서 생성기 실행 중 오류: {proc_e}")
            raise RuntimeError(f"보고서 생성기 실행 실패: {proc_e}")
            
    except Exception as e:
        logging.error(f"❌ 보고서 생성기 실행 중 오류: {e}")
        raise

def check_and_notify(**context):
    """보고서 생성 결과 확인"""
    try:
        # 이전 태스크 결과 가져오기
        task_result = context['task_instance'].xcom_pull(task_ids='generate_report')
        
        if task_result and task_result.get('status') == 'success':
            logging.info("✅ 보고서 생성 성공")
            
            # 결과 파일 정보
            result_file = task_result.get('file', 'Unknown')
            file_name = os.path.basename(result_file) if result_file != 'Unknown' else 'Unknown'
            
            logging.info(f"📊 실행 정보:")
            logging.info(f"- 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"- 생성 파일: {file_name}")
            logging.info(f"- 파일 위치: {result_file}")
            logging.info("✅ 제약영업회사 전략 보고서가 생성되었습니다.")
            
            return {'status': 'success', 'file': result_file}
        else:
            logging.warning("⚠️ 보고서 생성 부분 성공 또는 실패")
            logging.warning(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.warning(f"상태: {task_result.get('status', 'Unknown') if task_result else 'Failed'}")
            logging.warning(f"메시지: {task_result.get('message', 'No message') if task_result else 'Task failed'}")
            
            return {'status': 'warning', 'message': task_result.get('message', 'No message') if task_result else 'Task failed'}
            
    except Exception as e:
        logging.error(f"❌ 결과 확인 중 오류: {e}")
        logging.error(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return {'status': 'error', 'message': str(e)}

# Task 정의
generate_report_task = PythonOperator(
    task_id='generate_report',
    python_callable=run_report_generator,
    dag=dag,
    execution_timeout=timedelta(minutes=20)
)

check_task = PythonOperator(
    task_id='check_result',
    python_callable=check_and_notify,
    dag=dag,
)

# Task 의존성 설정
generate_report_task >> check_task

# DAG 문서화
dag.doc_md = """
# 제약영업회사 전략 보고서 생성 DAG

## 개요
이 DAG는 크롤링된 뉴스 데이터를 바탕으로 제약영업회사를 위한 전략 보고서를 자동 생성합니다.

## 실행 일정
- **월요일~금요일 13:30** (Asia/Seoul 기준)
- 주말 제외 평일만 실행
- 한 번에 하나의 DAG 인스턴스만 실행
- 뉴스 크롤링 완료 후 실행되도록 스케줄 조정

## 주요 기능
1. **뉴스 데이터 분석**: 크롤링된 뉴스 요약들을 통합 분석
2. **전략 보고서 생성**: OpenAI GPT-4o를 사용한 제약영업 전략 보고서 작성
3. **마크다운 저장**: 생성된 보고서를 .md 파일로 저장
4. **실시간 로깅**: 보고서 생성 진행상황을 실시간으로 Airflow 로그에 출력

## 입력 데이터
- `newsstand_iframe_*.json`: KBS/MBC/SBS 뉴스 요약
- `medical_top_trending_news_*.json`: 의료업계 트렌딩 뉴스
- `medical_recent_news_*.json`: 최신 의료 뉴스

## 환경 설정
- `OPENAI_API_KEY`: OpenAI API 키 (필수)

## 산출물
- `pharmaceutical_strategy_report_YYYYMMDD_HHMMSS.md`: 전략 보고서 파일

## 보고서 구조
1. Executive Summary
2. 제약영업 영향 분석  
3. 주요 뉴스 동향 클러스터 & 우선순위
4. 리스크 & 트리거 보드
5. 전략적 대응 및 실행계획
6. 대응 시나리오
7. 최종 의사결정 권고안
8. 출처 매핑 & 신뢰도

## 특징
- PEST 분석 및 5 Forces 기반 전략 분석
- 정량화된 영향도 평가 (±% 수치)
- 실행 가능한 액션 플랜 제시
- 규제/정책 변화에 따른 처방행태 및 매출 영향 분석
"""