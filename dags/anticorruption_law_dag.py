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

def check_for_changes():
    """법률 정보 변경사항 확인"""
    try:
        # func 디렉토리 경로 설정
        func_dir = os.path.join(os.path.dirname(current_dir), 'func')
        sys.path.append(func_dir)
        
        # anticorruption_law_logic 모듈 임포트
        from anticorruption_law_logic import check_law_info_changes
        
        logging.info("법률 정보 변경사항 확인 시작")
        
        # 변경사항 확인
        has_changes = check_law_info_changes()
        
        logging.info(f"변경사항 확인 결과: {'변경 있음' if has_changes else '변경 없음'}")
        
        return has_changes
        
    except Exception as e:
        logging.error(f"변경사항 확인 중 오류: {str(e)}")
        raise

def delete_old_files_conditional(**context):
    """변경사항이 있을 때만 오래된 파일 삭제"""
    try:
        # 이전 태스크 결과 확인
        has_changes = context['task_instance'].xcom_pull(task_ids='check_changes')
        
        if has_changes:
            logging.info("변경사항이 있어 오래된 파일을 삭제합니다.")
            
            # func 디렉토리 경로 설정
            func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            sys.path.append(func_dir)
            
            from anticorruption_law_logic import delete_old_files
            
            # 오래된 파일 삭제
            result = delete_old_files()
            
            logging.info(f"파일 삭제 결과: {result['message']}")
            
            return True  # Excel 생성을 위해 True 반환
        else:
            logging.info("변경사항이 없어 파일 삭제를 건너뜁니다.")
            return False  # Excel 생성 건너뛰기
            
    except Exception as e:
        logging.error(f"파일 삭제 중 오류: {str(e)}")
        raise

def create_excel_file(**context):
    """Excel 파일 생성"""
    try:
        # 이전 태스크 결과 확인
        should_create_excel = context['task_instance'].xcom_pull(task_ids='delete_old_files')
        
        if should_create_excel:
            logging.info("Excel 파일 생성을 시작합니다.")
            
            # func 디렉토리 경로 설정
            func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            preprocessing_path = os.path.join(func_dir, 'anticorruption_law_preprocessing.py')
            
            # Python 스크립트 실행
            result = subprocess.run(
                ['python3', preprocessing_path],
                cwd=func_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            if result.returncode == 0:
                logging.info(f"Excel 파일 생성 성공:\n{result.stdout}")
            else:
                logging.error(f"Excel 파일 생성 실패:\n{result.stderr}")
                raise Exception(f"Excel 파일 생성 실패: {result.stderr}")
            
            return "Excel 파일 생성 완료"
        else:
            logging.info("변경사항이 없어 Excel 파일 생성을 건너뜁니다.")
            return "Excel 파일 생성 건너뜀"
            
    except subprocess.TimeoutExpired:
        logging.error("Excel 파일 생성 타임아웃 (5분)")
        raise Exception("Excel 파일 생성 타임아웃")
    except Exception as e:
        logging.error(f"Excel 파일 생성 중 오류: {str(e)}")
        raise

def upload_anticorruption_data(**context):
    """청탁금지법 처리된 데이터 업로드"""
    try:
        # 이전 태스크 결과 확인
        should_upload = context['task_instance'].xcom_pull(task_ids='delete_old_files')
        
        if should_upload:
            logging.info("📤 청탁금지법 데이터 업로드 시작...")
            
            # func 디렉토리 경로 설정
            func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            sys.path.append(func_dir)
            
            from anticorruption_law_uploader import upload_latest_anticorruption_file
            
            # 파일 업로드
            result = upload_latest_anticorruption_file()
            
            if result:
                logging.info("✅ 청탁금지법 데이터 업로드 성공!")
                return {'status': 'success', 'message': 'Upload completed successfully'}
            else:
                logging.error("❌ 청탁금지법 데이터 업로드 실패")
                return {'status': 'failed', 'message': 'Upload failed'}
        else:
            logging.info("변경사항이 없어 업로드를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'No changes detected, upload skipped'}
            
    except Exception as e:
        logging.error(f"청탁금지법 데이터 업로드 중 오류: {str(e)}")
        raise

def clear_anticorruption_excel_files(**context):
    """청탁금지법 Excel 파일 정리"""
    try:
        # 이전 태스크 결과 확인
        upload_result = context['task_instance'].xcom_pull(task_ids='upload_anticorruption_data')
        
        # 업로드가 성공한 경우에만 Excel 파일 삭제
        if upload_result and upload_result.get('status') == 'success':
            logging.info("🗑️ 업로드 성공 후 청탁금지법 Excel 파일 정리 시작...")
            
            # func 디렉토리 경로 설정
            func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            sys.path.append(func_dir)
            
            from clear_files import clear_excel_files
            
            # law 타입 Excel 파일 삭제
            clear_excel_files('law')
            
            logging.info("✅ 청탁금지법 Excel 파일 정리 완료!")
            return {'status': 'success', 'message': 'Excel files cleared successfully'}
        else:
            logging.info("⚠️ 업로드가 성공하지 않아 Excel 파일 정리를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Upload was not successful, file cleanup skipped'}
            
    except Exception as e:
        logging.error(f"❌ Excel 파일 정리 중 오류: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def process_law_files():
    """법률 파일 처리 (변경사항 확인 및 파일 정리) - 기존 호환성 유지"""
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
    schedule='20 13 * * *',  # 매일 13:00 (한국시간)
    max_active_runs=1,
    tags=['law', 'anticorruption', 'crawler']
)

# 태스크 1: 청탁금지법 크롤링
crawl_task = PythonOperator(
    task_id='crawl_anticorruption_law',
    python_callable=run_anticorruption_crawler,
    dag=dag
)

# 태스크 2: 변경사항 확인
check_changes_task = PythonOperator(
    task_id='check_changes',
    python_callable=check_for_changes,
    dag=dag
)

# 태스크 3: 조건부 파일 삭제
delete_files_task = PythonOperator(
    task_id='delete_old_files',
    python_callable=delete_old_files_conditional,
    dag=dag
)

# 태스크 4: 조건부 Excel 파일 생성
excel_task = PythonOperator(
    task_id='create_excel',
    python_callable=create_excel_file,
    dag=dag
)

# 태스크 5: 청탁금지법 데이터 업로드
upload_task = PythonOperator(
    task_id='upload_anticorruption_data',
    python_callable=upload_anticorruption_data,
    dag=dag
)

# 태스크 6: 청탁금지법 Excel 파일 정리
clear_excel_task = PythonOperator(
    task_id='clear_excel_files',
    python_callable=clear_anticorruption_excel_files,
    dag=dag
)

# 태스크 7: 기존 법률 파일 처리 (호환성 유지)
process_task = PythonOperator(
    task_id='process_law_files',
    python_callable=process_law_files,
    dag=dag
)

# 태스크 의존성 설정
crawl_task >> check_changes_task >> delete_files_task >> excel_task >> upload_task >> clear_excel_task >> process_task