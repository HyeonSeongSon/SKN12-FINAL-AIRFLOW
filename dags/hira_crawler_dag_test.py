#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIRA 고시 데이터 크롤링 테스트 DAG
test_crawling 함수를 사용하여 2025-01-01 ~ 2025-08-01 범위로 테스트
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
    'owner': 'hira-test-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 6, 13, 0, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'catchup': False
}

# DAG 정의
dag = DAG(
    'hira_crawler_test',
    default_args=default_args,
    description='HIRA 크롤러 test_crawling 함수를 사용한 테스트 DAG (2025-01-01 ~ 2025-08-01)',
    schedule=None,  # 수동 실행만
    max_active_runs=1,
    tags=['hira', 'crawler', 'test']
)

def run_hira_test_crawler():
    """HIRA 테스트 크롤러 실행 함수"""
    try:
        # test_crawling 함수를 호출하는 Python 스크립트 생성
        test_script_content = '''#!/usr/bin/env python3
import sys
import os
sys.path.append('/opt/airflow/func')

try:
    from hira_crawler import test_crawling
    print("✅ hira_crawler 모듈 import 성공")
except ImportError as e:
    print(f"❌ hira_crawler 모듈 import 실패: {e}")
    # 대안으로 test_crawling_with_retry 함수 시도
    try:
        from hira_crawler import test_crawling_with_retry
        print("✅ test_crawling_with_retry 함수 import 성공")
        def test_crawling():
            return test_crawling_with_retry()
    except ImportError as e2:
        print(f"❌ test_crawling_with_retry 함수도 import 실패: {e2}")
        sys.exit(1)

if __name__ == "__main__":
    print("🏥 HIRA 테스트 크롤링 시작...")
    try:
        result = test_crawling()
        print("✅ HIRA 테스트 크롤링 완료")
        if result:
            print(f"결과: {result}")
    except Exception as e:
        print(f"❌ HIRA 테스트 크롤링 중 오류: {e}")
        sys.exit(1)
'''
        
        # 임시 스크립트 파일 생성
        test_script_path = '/opt/airflow/func/hira_test_runner.py'
        with open(test_script_path, 'w', encoding='utf-8') as f:
            f.write(test_script_content)
        
        logging.info(f"🏥 HIRA 테스트 크롤러 시작 (2025-01-01 ~ 2025-08-01)")
        
        # Python 스크립트 실행 - 실시간 출력
        env = os.environ.copy()
        process = subprocess.Popen(
            [sys.executable, '-u', test_script_path],
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
        
        # 타임아웃 설정 (테스트이므로 더 긴 시간)
        import time
        start_time = time.time()
        timeout = 3600  # 60분
        
        while True:
            # 타임아웃 체크
            if time.time() - start_time > timeout:
                process.terminate()
                logging.error(f"❌ 타임아웃: {timeout}초 초과")
                raise subprocess.TimeoutExpired(cmd=[sys.executable, test_script_path], timeout=timeout)
            
            # stdout 읽기
            line = process.stdout.readline()
            if line:
                line = line.rstrip()
                output_lines.append(line)
                logging.info(f"[HIRA 테스트] {line}")
            
            # 프로세스 종료 확인
            if process.poll() is not None:
                # 남은 출력 읽기
                for line in process.stdout:
                    line = line.rstrip()
                    output_lines.append(line)
                    logging.info(f"[HIRA 테스트] {line}")
                
                # stderr 읽기
                for line in process.stderr:
                    line = line.rstrip()
                    error_lines.append(line)
                    logging.error(f"[HIRA 테스트 에러] {line}")
                break
            
            # CPU 사용률을 낮추기 위한 짧은 대기
            time.sleep(0.01)
        
        return_code = process.returncode
        full_output = '\n'.join(output_lines)
        full_error = '\n'.join(error_lines)
        
        # 실행 결과 처리
        if return_code == 0:
            logging.info("✅ HIRA 테스트 크롤링 프로세스 완료")
            
            # 생성된 테스트 파일 확인
            import glob
            # 크롤러가 실제로 저장하는 경로와 일치시킴
            result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
            test_files = glob.glob(os.path.join(result_dir, 'hira_data_test_range.xlsx'))
            if test_files:
                latest_file = test_files[0]
                logging.info(f"생성된 테스트 파일: {latest_file}")
                return {'status': 'success', 'file': latest_file, 'output': full_output}
            else:
                logging.warning("테스트 Excel 파일이 생성되지 않았습니다.")
                return {'status': 'warning', 'message': '테스트 Excel 파일 없음', 'output': full_output}
        else:
            logging.error(f"❌ HIRA 테스트 크롤링 실패 (exit code: {return_code})")
            if full_error:
                logging.error(f"에러 출력:\n{full_error}")
            raise RuntimeError(f"테스트 크롤러 실행 실패: {full_error or '알 수 없는 오류'}")
            
    except subprocess.TimeoutExpired:
        logging.error("❌ HIRA 테스트 크롤러 타임아웃 (60분)")
        raise RuntimeError("테스트 크롤러 실행 타임아웃")
    except Exception as e:
        logging.error(f"❌ HIRA 테스트 크롤러 실행 중 오류: {e}")
        raise
    finally:
        # 임시 스크립트 파일 삭제
        if os.path.exists('/opt/airflow/func/hira_test_runner.py'):
            os.remove('/opt/airflow/func/hira_test_runner.py')

def upload_hira_test_data(**context):
    """테스트 HIRA 데이터 업로드"""
    try:
        # 이전 태스크 결과 가져오기
        task_result = context['task_instance'].xcom_pull(task_ids='check_test_result')
        
        # 크롤링이 성공한 경우에만 업로드 시도
        if task_result and task_result.get('status') == 'success':
            logging.info("📤 테스트 HIRA 데이터 업로드 시작...")
            
            # hira_data_uploader 모듈 import
            sys.path.append('/opt/airflow/func')
            from hira_data_uploader import upload_latest_hira_file
            
            # 업로드 실행
            upload_success = upload_latest_hira_file()
            
            if upload_success:
                logging.info("✅ 테스트 HIRA 데이터 업로드 성공")
                return {'status': 'success', 'message': 'Test upload completed successfully'}
            else:
                logging.error("❌ 테스트 HIRA 데이터 업로드 실패")
                return {'status': 'failed', 'message': 'Test upload failed'}
        else:
            logging.warning("⚠️ 테스트 크롤링이 성공하지 않아 업로드를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Test crawling was not successful'}
            
    except Exception as e:
        logging.error(f"❌ 테스트 업로드 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def cleanup_hira_test_files(**context):
    """업로드 성공한 테스트 HIRA Excel 파일 삭제"""
    try:
        # 이전 태스크 결과 가져오기
        upload_result = context['task_instance'].xcom_pull(task_ids='upload_test_hira_data')
        
        # 업로드가 성공한 경우에만 파일 삭제
        if upload_result and upload_result.get('status') == 'success':
            logging.info("🗑️ 테스트 HIRA Excel 파일 삭제 시작...")
            
            # clear_files 모듈 import
            sys.path.append('/opt/airflow/func')
            from clear_files import clear_excel_files
            
            # HIRA Excel 파일 삭제 실행
            clear_excel_files(file_type='hira')
            
            logging.info("✅ 테스트 HIRA Excel 파일 삭제 완료")
            return {'status': 'success', 'message': 'Test HIRA files cleaned up successfully'}
        else:
            logging.warning("⚠️ 업로드가 성공하지 않아 파일 삭제를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Upload was not successful'}
            
    except Exception as e:
        logging.error(f"❌ 테스트 파일 삭제 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def check_test_result(**context):
    """테스트 크롤링 결과 확인"""
    try:
        # 이전 태스크 결과 가져오기
        task_result = context['task_instance'].xcom_pull(task_ids='run_test_crawler')
        
        if task_result and task_result.get('status') == 'success':
            logging.info("✅ HIRA 테스트 크롤링 성공")
            
            # 결과 파일 정보
            result_file = task_result.get('file', 'Unknown')
            file_name = os.path.basename(result_file) if result_file != 'Unknown' else 'Unknown'
            
            logging.info(f"📊 테스트 실행 정보:")
            logging.info(f"- 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"- 생성 파일: {file_name}")
            logging.info(f"- 테스트 범위: 2025-01-01 ~ 2025-08-01")
            logging.info(f"- 파일 위치: {result_file}")
            logging.info("✅ HIRA 고시 데이터 테스트 크롤링이 완료되었습니다.")
            
            return {'status': 'success', 'file': result_file}
        else:
            logging.warning("⚠️ HIRA 테스트 크롤링 부분 성공 또는 실패")
            logging.warning(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.warning(f"상태: {task_result.get('status', 'Unknown') if task_result else 'Failed'}")
            logging.warning(f"메시지: {task_result.get('message', 'No message') if task_result else 'Task failed'}")
            
            return {'status': 'warning', 'message': task_result.get('message', 'No message') if task_result else 'Task failed'}
            
    except Exception as e:
        logging.error(f"❌ 테스트 결과 확인 중 오류: {e}")
        logging.error(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return {'status': 'error', 'message': str(e)}

# Task 정의
test_crawler_task = PythonOperator(
    task_id='run_test_crawler',
    python_callable=run_hira_test_crawler,
    dag=dag,
    execution_timeout=timedelta(minutes=60)  # 테스트이므로 60분
)

check_test_task = PythonOperator(
    task_id='check_test_result',
    python_callable=check_test_result,
    dag=dag,
)

upload_test_task = PythonOperator(
    task_id='upload_test_hira_data',
    python_callable=upload_hira_test_data,
    dag=dag,
)

cleanup_test_files_task = PythonOperator(
    task_id='cleanup_test_hira_files',
    python_callable=cleanup_hira_test_files,
    dag=dag,
)

# Task 의존성 설정
test_crawler_task >> check_test_task >> upload_test_task >> cleanup_test_files_task