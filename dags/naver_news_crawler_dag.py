#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 뉴스스탠드 크롤링 Airflow DAG
매일 09:00, 13:00에 KBS/MBC/SBS 뉴스 수집 및 AI 요약 생성
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
    'owner': 'news-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 5, 12, 0, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'catchup': False  # 과거 실행 건너뛰기
}

# DAG 정의
dag = DAG(
    'naver_news_crawler_v3',
    default_args=default_args,
    description='네이버 뉴스스탠드 KBS/MBC/SBS 크롤링 및 AI 요약',
    schedule='10 9,13 * * *',
    max_active_runs=1,
    tags=['news', 'crawler', 'ai-summary']
)

def run_news_crawler():
    """뉴스 크롤러 실행 함수"""
    try:
        # Docker 환경에서는 환경변수가 이미 설정되어 있으므로 로컬에서만 로드
        if not os.getenv('AIRFLOW__CORE__EXECUTOR'):
            load_env_variables()
        
        # 크롤러 스크립트 경로 (Docker 환경에서의 경로)
        if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
            crawler_script = '/opt/airflow/func/newsstand_crawler.py'
        else:  # 로컬 환경
            crawler_script = os.path.join(os.path.dirname(current_dir), 'func', 'newsstand_crawler.py')
        
        # 환경변수 설정 확인
        openai_key = os.getenv('OPENAI_API_KEY')
        logging.info(f"태스크 실행 시 OPENAI_API_KEY 확인: {openai_key[:10] if openai_key else 'NOT_SET'}...")
        
        if not openai_key:
            # .env 파일에서 직접 읽어서 설정 시도
            env_path = os.path.join(os.path.dirname(current_dir), '.env')
            logging.info(f".env 파일 경로 확인: {env_path}")
            logging.info(f".env 파일 존재 여부: {os.path.exists(env_path)}")
            
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    content = f.read()
                    logging.info(f".env 파일 내용 확인: {content[:100]}...")
                    for line in content.split('\n'):
                        if line.startswith('OPENAI_API_KEY='):
                            key_value = line.split('=', 1)[1]
                            os.environ['OPENAI_API_KEY'] = key_value
                            openai_key = key_value
                            logging.info("✅ .env에서 OPENAI_API_KEY 직접 로드 성공")
                            break
            
            if not openai_key:
                raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
        logging.info(f"OPENAI_API_KEY 확인됨: {openai_key[:10]}...")
        
        logging.info(f"뉴스 크롤러 시작: {crawler_script}")
        
        # Python 스크립트 실행 (환경변수 전달) - 실시간 출력
        env = os.environ.copy()
        process = subprocess.Popen(
            [sys.executable, '-u', crawler_script],  # -u 옵션으로 unbuffered 출력
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd='/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func'),
            env=env,
            bufsize=1  # 라인 버퍼링
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
                logging.info(f"[크롤러] {line}")
            
            # 프로세스 종료 확인
            if process.poll() is not None:
                # 남은 출력 읽기
                for line in process.stdout:
                    line = line.rstrip()
                    output_lines.append(line)
                    logging.info(f"[크롤러] {line}")
                
                # stderr 읽기
                for line in process.stderr:
                    line = line.rstrip()
                    error_lines.append(line)
                    logging.error(f"[크롤러 에러] {line}")
                break
            
            # CPU 사용률을 낮추기 위한 짧은 대기
            time.sleep(0.01)
        
        return_code = process.returncode
        full_output = '\n'.join(output_lines)
        full_error = '\n'.join(error_lines)
        
        # 실행 결과 처리
        if return_code == 0:
            logging.info("✅ 뉴스 크롤링 프로세스 완료")
            
            # 생성된 파일 확인
            import glob
            # 크롤러가 실제로 저장하는 경로와 일치시킴
            result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
            json_files = glob.glob(os.path.join(result_dir, 'newsstand_*.json'))
            if json_files:
                latest_file = max(json_files, key=os.path.getctime)
                logging.info(f"생성된 파일: {latest_file}")
                return {'status': 'success', 'file': latest_file, 'output': full_output}
            else:
                logging.warning("JSON 파일이 생성되지 않았습니다.")
                return {'status': 'warning', 'message': 'JSON 파일 없음', 'output': full_output}
        else:
            logging.error(f"❌ 뉴스 크롤링 실패 (exit code: {return_code})")
            if full_error:
                logging.error(f"에러 출력:\n{full_error}")
            raise RuntimeError(f"크롤러 실행 실패: {full_error or '알 수 없는 오류'}")
            
    except subprocess.TimeoutExpired:
        logging.error("❌ 뉴스 크롤러 타임아웃 (30분)")
        raise RuntimeError("크롤러 실행 타임아웃")
    except Exception as e:
        logging.error(f"❌ 뉴스 크롤러 실행 중 오류: {e}")
        raise

def create_excel_report(**context):
    """JSON 데이터를 Excel로 변환"""
    try:
        # 이전 태스크 결과 가져오기
        task_result = context['task_instance'].xcom_pull(task_ids='run_crawler')
        
        if task_result and task_result.get('status') == 'success':
            logging.info("📊 Excel 파일 생성 시작")
            
            # newsstand_iframe_preprocessing.py 임포트
            if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
                preprocessing_script = '/opt/airflow/func/newsstand_iframe_preprocessing.py'
            else:  # 로컬 환경
                preprocessing_script = os.path.join(os.path.dirname(current_dir), 'func', 'newsstand_iframe_preprocessing.py')
            
            # sys.path에 func 디렉토리 추가
            func_dir = '/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func')
            if func_dir not in sys.path:
                sys.path.append(func_dir)
            
            # 모듈 임포트 및 실행
            try:
                import newsstand_iframe_preprocessing
                
                # 모듈 리로드 (최신 코드 반영)
                import importlib
                importlib.reload(newsstand_iframe_preprocessing)
                
                # Excel 파일 생성 함수 실행
                result_df = newsstand_iframe_preprocessing.preprocess_newsstand_iframe()
                
                if result_df is not None and len(result_df) > 0:
                    logging.info(f"✅ Excel 파일 생성 완료: {len(result_df)}개 기사 처리")
                    return {'status': 'success', 'processed_count': len(result_df)}
                else:
                    logging.warning("⚠️ Excel 파일 생성됨, 하지만 데이터가 없음")
                    return {'status': 'warning', 'message': '처리할 데이터 없음'}
                    
            except ImportError as e:
                logging.error(f"❌ 모듈 임포트 실패: {e}")
                return {'status': 'error', 'message': f'모듈 임포트 실패: {e}'}
            except Exception as e:
                logging.error(f"❌ Excel 파일 생성 실패: {e}")
                return {'status': 'error', 'message': f'Excel 생성 실패: {e}'}
                
        else:
            logging.warning("⚠️ 크롤링이 성공하지 않아 Excel 생성을 건너뜁니다.")
            return {'status': 'skipped', 'message': '크롤링 실패로 건너뜀'}
            
    except Exception as e:
        logging.error(f"❌ Excel 생성 태스크 실행 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}


def upload_excel_to_db(**context):
    """생성된 Excel 파일을 데이터베이스에 업로드"""
    try:
        # 이전 태스크 결과 가져오기
        excel_result = context['task_instance'].xcom_pull(task_ids='prepro_and_create_excel')
        
        if excel_result and excel_result.get('status') == 'success':
            logging.info("📤 Excel 파일 업로드 시작")
            
            # newsstand_iframe_uploader.py 모듈 임포트
            func_dir = '/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func')
            if func_dir not in sys.path:
                sys.path.append(func_dir)
            
            try:
                import newsstand_iframe_uploader
                
                # 모듈 리로드 (최신 코드 반영)
                import importlib
                importlib.reload(newsstand_iframe_uploader)
                
                # newsstand 타입으로 업로드
                upload_success = newsstand_iframe_uploader.upload_latest_file(file_type='newsstand')
                
                if upload_success:
                    logging.info("✅ Excel 파일 업로드 성공")
                    return {'status': 'success', 'message': '업로드 완료'}
                else:
                    logging.error("❌ Excel 파일 업로드 실패")
                    return {'status': 'error', 'message': '업로드 실패'}
                    
            except ImportError as e:
                logging.error(f"❌ 업로더 모듈 임포트 실패: {e}")
                return {'status': 'error', 'message': f'모듈 임포트 실패: {e}'}
            except Exception as e:
                logging.error(f"❌ Excel 파일 업로드 실패: {e}")
                return {'status': 'error', 'message': f'업로드 실패: {e}'}
                
        else:
            logging.warning("⚠️ Excel 생성이 성공하지 않아 업로드를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Excel 생성 실패로 건너뜀'}
            
    except Exception as e:
        logging.error(f"❌ Excel 업로드 태스크 실행 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def cleanup_newsstand_json_files(**context):
    """업로드 성공한 newsstand JSON 파일 정리 (최신 4개만 유지)"""
    try:
        # 이전 태스크 결과 가져오기
        upload_result = context['task_instance'].xcom_pull(task_ids='upload_excel')
        
        # 업로드가 성공한 경우에만 파일 정리
        if upload_result and upload_result.get('status') == 'success':
            logging.info("🗑️ Newsstand JSON 파일 정리 시작...")
            
            # clear_files 모듈 import
            sys.path.append('/opt/airflow/func')
            from clear_files import clear_json_files
            
            # newsstand JSON 파일 정리 실행 (최신 4개만 유지)
            clear_json_files(file_type='newsstand')
            
            logging.info("✅ Newsstand JSON 파일 정리 완료")
            return {'status': 'success', 'message': 'Newsstand JSON files cleaned up successfully'}
        else:
            logging.warning("⚠️ 업로드가 성공하지 않아 파일 정리를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Upload was not successful'}
            
    except Exception as e:
        logging.error(f"❌ Newsstand JSON 파일 정리 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}


def check_and_notify(**context):
    """크롤링 결과 확인"""
    try:
        # 이전 태스크 결과 가져오기
        crawler_result = context['task_instance'].xcom_pull(task_ids='run_crawler')
        excel_result = context['task_instance'].xcom_pull(task_ids='prepro_and_create_excel')
        upload_result = context['task_instance'].xcom_pull(task_ids='upload_excel')
        
        if crawler_result and crawler_result.get('status') == 'success':
            logging.info("✅ 크롤링 성공")
            
            # 결과 파일 정보
            result_file = crawler_result.get('file', 'Unknown')
            file_name = os.path.basename(result_file) if result_file != 'Unknown' else 'Unknown'
            
            # Excel 생성 결과
            excel_status = excel_result.get('status', 'unknown') if excel_result else 'unknown'
            excel_count = excel_result.get('processed_count', 0) if excel_result else 0
            
            # 업로드 결과
            upload_status = upload_result.get('status', 'unknown') if upload_result else 'unknown'
            upload_message = upload_result.get('message', '') if upload_result else ''
            
            logging.info(f"📊 실행 정보:")
            logging.info(f"- 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"- 생성 파일: {file_name}")
            logging.info(f"- 대상 언론사: KBS, MBC, SBS")
            logging.info(f"- 파일 위치: {result_file}")
            logging.info(f"- Excel 생성: {excel_status} ({excel_count}개 기사 처리)")
            logging.info(f"- DB 업로드: {upload_status} ({upload_message})")
            logging.info("✅ 모든 뉴스에 대한 AI 요약이 생성되었습니다.")
            
            return {'status': 'success', 'file': result_file, 'excel_status': excel_status, 'excel_count': excel_count, 'upload_status': upload_status}
        else:
            logging.warning("⚠️ 크롤링 부분 성공 또는 실패")
            logging.warning(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.warning(f"상태: {crawler_result.get('status', 'Unknown') if crawler_result else 'Failed'}")
            logging.warning(f"메시지: {crawler_result.get('message', 'No message') if crawler_result else 'Task failed'}")
            
            return {'status': 'warning', 'message': crawler_result.get('message', 'No message') if crawler_result else 'Task failed'}
            
    except Exception as e:
        logging.error(f"❌ 결과 확인 중 오류: {e}")
        logging.error(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return {'status': 'error', 'message': str(e)}


# Task 정의
crawler_task = PythonOperator(
    task_id='run_crawler',
    python_callable=run_news_crawler,
    dag=dag,
    execution_timeout=timedelta(minutes=30)
)

prepro_and_create_excel_task = PythonOperator(
    task_id='prepro_and_create_excel',
    python_callable=create_excel_report,
    dag=dag,
    execution_timeout=timedelta(minutes=10)
)

upload_excel_task = PythonOperator(
    task_id='upload_excel',
    python_callable=upload_excel_to_db,
    dag=dag,
    execution_timeout=timedelta(minutes=5)
)

cleanup_json_task = PythonOperator(
    task_id='cleanup_newsstand_json',
    python_callable=cleanup_newsstand_json_files,
    dag=dag,
)

check_task = PythonOperator(
    task_id='check_result',
    python_callable=check_and_notify,
    dag=dag,
)

# Task 의존성 설정
crawler_task >> prepro_and_create_excel_task >> upload_excel_task >> cleanup_json_task >> check_task

# DAG 문서화
dag.doc_md = """
# 네이버 뉴스스탠드 크롤링 DAG

## 개요
이 DAG는 네이버 뉴스스탠드에서 KBS, MBC, SBS 뉴스를 수집하고 AI 요약을 생성합니다.

## 실행 일정
- **매일 09:00, 13:00** (Asia/Seoul 기준)
- 한 번에 하나의 DAG 인스턴스만 실행

## 주요 기능
1. **뉴스 수집**: iframe 기반으로 KBS/MBC/SBS 뉴스 크롤링
2. **AI 요약**: OpenAI GPT를 사용한 뉴스 요약 생성
3. **Excel 변환**: JSON 데이터를 Excel 형태로 변환 및 전처리
4. **결과 저장**: JSON 및 Excel 형태로 파일 저장

## 환경 설정
- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- Chrome/ChromeDriver 설치 필요
- `openpyxl` 패키지 필요 (Excel 생성용)

## 산출물
- `newsstand_YYYYMMDD_HHMMSS.json`: 크롤링 결과 파일 (JSON 형식)
- `newsstand_iframe_processed_YYYYMMDD_HHMMSS.xlsx`: 전처리된 Excel 파일

## Task 순서
1. `run_crawler`: 뉴스 크롤링 및 AI 요약 생성
2. `prepro_and_create_excel`: JSON 데이터를 Excel로 변환
3. `upload_excel`: Excel 파일을 데이터베이스에 업로드
4. `check_result`: 전체 결과 확인 및 로깅
"""