#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 뉴스스탠드 크롤링 Airflow DAG
매일 09:00, 13:00에 KBS/MBC/SBS 뉴스 수집 및 AI 요약 생성
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from datetime import datetime, timedelta
import os
import sys
import subprocess
import logging

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 기본 DAG 설정
default_args = {
    'owner': 'news-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 31),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'catchup': True,
    'email': ['inexorable17@gmail.com']  # 실제 이메일 주소로 변경
}

# DAG 정의
dag = DAG(
    'naver_news_crawler',
    default_args=default_args,
    description='네이버 뉴스스탠드 KBS/MBC/SBS 크롤링 및 AI 요약',
    schedule='0 9,13 * * *',  # 매일 09:00, 13:00 (UTC 기준)
    max_active_runs=1,
    tags=['news', 'crawler', 'ai-summary']
)

def run_news_crawler():
    """뉴스 크롤러 실행 함수"""
    try:
        # 크롤러 스크립트 경로
        crawler_script = os.path.join(os.path.dirname(current_dir), 'func', 'newsstand_crawler.py')
        
        # 환경변수 설정 확인
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
        logging.info(f"뉴스 크롤러 시작: {crawler_script}")
        
        # Python 스크립트 실행
        result = subprocess.run(
            [sys.executable, crawler_script],
            capture_output=True,
            text=True,
            timeout=1800,  # 30분 타임아웃
            cwd=os.path.join(os.path.dirname(current_dir), 'func')
        )
        
        # 실행 결과 로깅
        if result.returncode == 0:
            logging.info("✅ 뉴스 크롤링 성공")
            logging.info(f"출력:\n{result.stdout}")
            
            # 생성된 파일 확인
            import glob
            func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            json_files = glob.glob(os.path.join(func_dir, 'newsstand_*.json'))
            if json_files:
                latest_file = max(json_files, key=os.path.getctime)
                logging.info(f"생성된 파일: {latest_file}")
                return {'status': 'success', 'file': latest_file, 'output': result.stdout}
            else:
                logging.warning("JSON 파일이 생성되지 않았습니다.")
                return {'status': 'warning', 'message': 'JSON 파일 없음', 'output': result.stdout}
        else:
            logging.error(f"❌ 뉴스 크롤링 실패 (exit code: {result.returncode})")
            logging.error(f"에러:\n{result.stderr}")
            raise RuntimeError(f"크롤러 실행 실패: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logging.error("❌ 뉴스 크롤러 타임아웃 (30분)")
        raise RuntimeError("크롤러 실행 타임아웃")
    except Exception as e:
        logging.error(f"❌ 뉴스 크롤러 실행 중 오류: {e}")
        raise

def check_and_notify(**context):
    """크롤링 결과 확인 및 알림"""
    try:
        # 이전 태스크 결과 가져오기
        task_result = context['task_instance'].xcom_pull(task_ids='run_crawler')
        
        if task_result and task_result.get('status') == 'success':
            logging.info("✅ 크롤링 성공 - 알림 전송")
            
            # 결과 파일 정보
            result_file = task_result.get('file', 'Unknown')
            file_name = os.path.basename(result_file) if result_file != 'Unknown' else 'Unknown'
            
            # 성공 메시지 반환 (EmailOperator에서 사용)
            return {
                'subject': f'[SUCCESS] 네이버 뉴스 크롤링 완료 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'content': f'''
🎉 네이버 뉴스스탠드 크롤링이 성공적으로 완료되었습니다.

📊 실행 정보:
- 실행 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 생성 파일: {file_name}
- 대상 언론사: KBS, MBC, SBS

📁 파일 위치: {result_file}

✅ 모든 뉴스에 대한 AI 요약이 생성되었습니다.
                '''
            }
        else:
            logging.warning("⚠️ 크롤링 부분 성공 또는 실패")
            return {
                'subject': f'[WARNING] 네이버 뉴스 크롤링 이슈 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'content': f'''
⚠️ 네이버 뉴스스탠드 크롤링에서 문제가 발생했습니다.

📊 실행 정보:
- 실행 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 상태: {task_result.get('status', 'Unknown') if task_result else 'Failed'}
- 메시지: {task_result.get('message', 'No message') if task_result else 'Task failed'}

🔍 로그를 확인하여 문제를 진단해주세요.
                '''
            }
            
    except Exception as e:
        logging.error(f"❌ 알림 준비 중 오류: {e}")
        return {
            'subject': f'[ERROR] 네이버 뉴스 크롤링 오류 - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'content': f'''
❌ 네이버 뉴스스탠드 크롤링 중 오류가 발생했습니다.

📊 오류 정보:
- 실행 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 오류: {str(e)}

🔍 Airflow 로그를 확인하여 문제를 진단해주세요.
            '''
        }

def send_notification_email(**context):
    """이메일 알림 전송"""
    try:
        # 이전 태스크에서 준비된 알림 내용 가져오기
        notification_data = context['task_instance'].xcom_pull(task_ids='check_result')
        
        if notification_data:
            # EmailOperator 동적 생성 및 실행
            email_task = EmailOperator(
                task_id='send_email_dynamic',
                to=['inexorable17@gmail.com'],
                subject=notification_data['subject'],
                html_content=notification_data['content'].replace('\n', '<br>'),
                dag=dag
            )
            
            # 이메일 전송 실행
            email_task.execute(context)
            logging.info("✅ 알림 이메일 전송 완료")
        else:
            logging.warning("⚠️ 알림 데이터가 없어 이메일을 전송하지 않습니다.")
            
    except Exception as e:
        logging.error(f"❌ 이메일 전송 실패: {e}")
        # 이메일 전송 실패는 전체 DAG 실패로 이어지지 않도록 함
        pass

# Task 정의
crawler_task = PythonOperator(
    task_id='run_crawler',
    python_callable=run_news_crawler,
    dag=dag,
    pool='crawler_pool',  # 리소스 풀 사용 (선택사항)
    execution_timeout=timedelta(minutes=30)
)

check_task = PythonOperator(
    task_id='check_result',
    python_callable=check_and_notify,
    dag=dag,
)

email_task = PythonOperator(
    task_id='send_notification',
    python_callable=send_notification_email,
    dag=dag,
    trigger_rule='all_done'  # 이전 태스크가 성공/실패 관계없이 실행
)

# Task 의존성 설정
crawler_task >> check_task >> email_task

# DAG 문서화
dag.doc_md = """
# 네이버 뉴스스탠드 크롤링 DAG

## 개요
이 DAG는 네이버 뉴스스탠드에서 KBS, MBC, SBS 뉴스를 수집하고 AI 요약을 생성합니다.

## 실행 일정
- **매일 09:00, 13:00** (UTC 기준)
- 한 번에 하나의 DAG 인스턴스만 실행

## 주요 기능
1. **뉴스 수집**: iframe 기반으로 KBS/MBC/SBS 뉴스 크롤링
2. **AI 요약**: OpenAI GPT를 사용한 뉴스 요약 생성
3. **결과 저장**: JSON 형태로 파일 저장
4. **알림**: 실행 결과를 이메일로 통지

## 환경 설정
- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- Chrome/ChromeDriver 설치 필요
- 이메일 SMTP 설정 필요

## 산출물
- `newsstand_YYYYMMDD_HHMMSS.json`: 크롤링 결과 파일
"""