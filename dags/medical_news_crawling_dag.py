#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
의료뉴스 크롤링 DAG
- recent_news: 최근(오늘/어제) 뉴스 크롤링
- trending_news: 당일 트렌딩 뉴스 크롤링
매일 09시와 13시에 두 크롤러를 순차적으로 실행
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
    'owner': 'medical-news-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 8, 10, 9, 0, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'catchup': False  # 과거 실행 건너뛰기
}

# DAG 정의
dag = DAG(
    'medical_news_crawling_v1',
    default_args=default_args,
    description='의료뉴스 크롤링 - 최근뉴스 & 트렌딩뉴스',
    schedule='0 9,13 * * 1-5',
    max_active_runs=1,
    tags=['medical', 'news', 'crawling', 'sequential']
)

def run_recent_news_crawler():
    """최근 뉴스 크롤러 실행 함수"""
    try:
        # Docker 환경에서는 환경변수가 이미 설정되어 있으므로 로컬에서만 로드
        if not os.getenv('AIRFLOW__CORE__EXECUTOR'):
            load_env_variables()
        
        # 크롤러 스크립트 경로
        if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
            crawler_script = '/opt/airflow/func/medical_recent_news_crawler.py'
        else:  # 로컬 환경
            crawler_script = os.path.join(os.path.dirname(current_dir), 'func', 'medical_recent_news_crawler.py')
        
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
        
        logging.info(f"최근 뉴스 크롤러 시작: {crawler_script}")
        
        # Python 스크립트 실행
        env = os.environ.copy()
        # Airflow 사용자의 Python 환경 사용
        env['PATH'] = '/home/airflow/.local/bin:' + env.get('PATH', '')
        process = subprocess.Popen(
            ['/home/airflow/.local/bin/python3', '-u', crawler_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # stderr을 stdout과 합침
            text=True,
            cwd='/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func'),
            env=env,
            bufsize=1,
            universal_newlines=True
        )
        
        # 실시간 로그 출력
        logging.info("📺 실시간 크롤링 로그 시작...")
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
                    logging.info(f"📰 {line}")
            
            # 프로세스 완료 대기
            process.wait()
            stdout = '\n'.join(output_lines)
            
            if process.returncode == 0:
                logging.info("✅ 최근 뉴스 크롤링 완료")
                logging.info("📊 최종 출력 요약 완료")
                
                # 생성된 파일 확인
                import glob
                # 크롤러가 실제로 저장하는 경로와 일치시킴
                result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
                json_files = glob.glob(os.path.join(result_dir, 'medical_recent_news_*.json'))
                
                if json_files:
                    latest_file = max(json_files, key=os.path.getctime)
                    logging.info(f"생성된 파일: {latest_file}")
                    return {'status': 'success', 'file': latest_file, 'output': stdout}
                else:
                    logging.warning("JSON 파일이 생성되지 않았습니다.")
                    return {'status': 'warning', 'message': 'JSON 파일 없음', 'output': stdout}
            else:
                error_output = '\n'.join(output_lines[-10:])  # 마지막 10줄만 에러로 표시
                logging.error(f"❌ 최근 뉴스 크롤링 실패 (리턴코드: {process.returncode})")
                logging.error(f"마지막 출력: {error_output}")
                raise RuntimeError(f"크롤러 실행 실패 (리턴코드: {process.returncode})")
                
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
            
            logging.error(f"❌ 최근 뉴스 크롤러 실행 중 오류: {proc_e}")
            raise RuntimeError(f"크롤러 실행 실패: {proc_e}")
            
    except Exception as e:
        logging.error(f"❌ 최근 뉴스 크롤러 실행 중 오류: {e}")
        raise

def run_trending_news_crawler():
    """트렌딩 뉴스 크롤러 실행 함수"""
    try:
        # Docker 환경에서는 환경변수가 이미 설정되어 있으므로 로컬에서만 로드
        if not os.getenv('AIRFLOW__CORE__EXECUTOR'):
            load_env_variables()
        
        # 크롤러 스크립트 경로
        if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
            crawler_script = '/opt/airflow/func/medical_top_trending_news_today_crawler.py'
        else:  # 로컬 환경
            crawler_script = os.path.join(os.path.dirname(current_dir), 'func', 'medical_top_trending_news_today_crawler.py')
        
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
        
        logging.info(f"트렌딩 뉴스 크롤러 시작: {crawler_script}")
        
        # Python 스크립트 실행
        env = os.environ.copy()
        # Airflow 사용자의 Python 환경 사용
        env['PATH'] = '/home/airflow/.local/bin:' + env.get('PATH', '')
        process = subprocess.Popen(
            ['/home/airflow/.local/bin/python3', '-u', crawler_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # stderr을 stdout과 합침
            text=True,
            cwd='/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func'),
            env=env,
            bufsize=1,
            universal_newlines=True
        )
        
        # 실시간 로그 출력
        logging.info("📺 실시간 크롤링 로그 시작...")
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
                    logging.info(f"📈 {line}")
            
            # 프로세스 완료 대기
            process.wait()
            stdout = '\n'.join(output_lines)
            
            if process.returncode == 0:
                logging.info("✅ 트렌딩 뉴스 크롤링 완료")
                logging.info("📊 최종 출력 요약 완료")
                
                # 생성된 파일 확인
                import glob
                # 크롤러가 실제로 저장하는 경로와 일치시킴
                result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
                json_files = glob.glob(os.path.join(result_dir, 'medical_top_trending_news_*.json'))
                
                if json_files:
                    latest_file = max(json_files, key=os.path.getctime)
                    logging.info(f"생성된 파일: {latest_file}")
                    return {'status': 'success', 'file': latest_file, 'output': stdout}
                else:
                    logging.warning("JSON 파일이 생성되지 않았습니다.")
                    return {'status': 'warning', 'message': 'JSON 파일 없음', 'output': stdout}
            else:
                error_output = '\n'.join(output_lines[-10:])  # 마지막 10줄만 에러로 표시
                logging.error(f"❌ 트렌딩 뉴스 크롤링 실패 (리턴코드: {process.returncode})")
                logging.error(f"마지막 출력: {error_output}")
                raise RuntimeError(f"크롤러 실행 실패 (리턴코드: {process.returncode})")
                
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
            
            logging.error(f"❌ 트렌딩 뉴스 크롤러 실행 중 오류: {proc_e}")
            raise RuntimeError(f"크롤러 실행 실패: {proc_e}")
            
    except Exception as e:
        logging.error(f"❌ 트렌딩 뉴스 크롤러 실행 중 오류: {e}")
        raise

def cleanup_chrome_processes():
    """Chrome 프로세스 정리"""
    try:
        logging.info("🧹 Chrome 프로세스 정리 중...")
        
        # Chrome 관련 프로세스 종료
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=10)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=10)
        
        logging.info("✅ Chrome 프로세스 정리 완료")
        return {'status': 'success', 'message': 'Chrome processes cleaned up'}
        
    except Exception as e:
        logging.warning(f"⚠️ Chrome 프로세스 정리 중 오류 (무시 가능): {str(e)}")
        return {'status': 'warning', 'message': str(e)}

def add_delay_between_crawlers():
    """크롤러 간 대기 시간 추가"""
    import time
    try:
        delay_seconds = 30  # 30초 대기
        logging.info(f"⏰ 크롤러 간 {delay_seconds}초 대기 중...")
        time.sleep(delay_seconds)
        logging.info("✅ 대기 완료, 다음 크롤러 준비됨")
        return {'status': 'success', 'delay_seconds': delay_seconds}
    except Exception as e:
        logging.error(f"❌ 대기 중 오류: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def create_medical_excel_report(**context):
    """의료뉴스 JSON 데이터를 Excel로 변환"""
    try:
        # 이전 태스크 결과 가져오기
        recent_result = context['task_instance'].xcom_pull(task_ids='crawl_recent_news')
        trending_result = context['task_instance'].xcom_pull(task_ids='crawl_trending_news')
        
        # 최소 하나의 크롤링이 성공했는지 확인
        success_count = 0
        if recent_result and recent_result.get('status') == 'success':
            success_count += 1
        if trending_result and trending_result.get('status') == 'success':
            success_count += 1
            
        if success_count > 0:
            logging.info(f"📊 Excel 파일 생성 시작 (성공한 크롤링: {success_count}/2개)")
            
            # medical_news_preprocessing.py 임포트
            import sys
            if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
                func_dir = '/opt/airflow/func'
            else:  # 로컬 환경
                func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            
            if func_dir not in sys.path:
                sys.path.append(func_dir)
            
            # 모듈 임포트 및 실행
            try:
                import medical_news_preprocessing
                
                # 모듈 리로드 (최신 코드 반영)
                import importlib
                importlib.reload(medical_news_preprocessing)
                
                # Excel 파일 생성 함수 실행
                result_df = medical_news_preprocessing.preprocess_medical_news()
                
                if result_df is not None and len(result_df) > 0:
                    logging.info(f"✅ Excel 파일 생성 완료: {len(result_df)}개 고유 기사 처리")
                    return {'status': 'success', 'processed_count': len(result_df)}
                else:
                    logging.warning("⚠️ Excel 파일 생성됨, 하지만 고유한 새 데이터가 없음")
                    return {'status': 'warning', 'message': '새로운 고유 데이터 없음'}
                    
            except ImportError as e:
                logging.error(f"❌ 모듈 임포트 실패: {e}")
                return {'status': 'error', 'message': f'모듈 임포트 실패: {e}'}
            except Exception as e:
                logging.error(f"❌ Excel 파일 생성 실패: {e}")
                return {'status': 'error', 'message': f'Excel 생성 실패: {e}'}
                
        else:
            logging.warning("⚠️ 모든 크롤링이 실패하여 Excel 생성을 건너뜁니다.")
            return {'status': 'skipped', 'message': '크롤링 실패로 건너뜀'}
            
    except Exception as e:
        logging.error(f"❌ Excel 생성 태스크 실행 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}


def aggregate_results(**context):
    """크롤링 결과 집계"""
    try:
        logging.info("📊 크롤링 결과 집계 중...")
        
        # XCom에서 결과 가져오기
        recent_result = context['task_instance'].xcom_pull(task_ids='crawl_recent_news')
        trending_result = context['task_instance'].xcom_pull(task_ids='crawl_trending_news')
        excel_result = context['task_instance'].xcom_pull(task_ids='create_medical_excel')
        
        total_files = 0
        recent_file = None
        trending_file = None
        
        if recent_result and recent_result.get('status') == 'success':
            total_files += 1
            recent_file = recent_result.get('file', 'Unknown')
            logging.info(f"📰 최근 뉴스 크롤링 성공: {recent_file}")
        else:
            logging.warning(f"📰 최근 뉴스 크롤링 실패: {recent_result}")
        
        if trending_result and trending_result.get('status') == 'success':
            total_files += 1
            trending_file = trending_result.get('file', 'Unknown')
            logging.info(f"📈 트렌딩 뉴스 크롤링 성공: {trending_file}")
        else:
            logging.warning(f"📈 트렌딩 뉴스 크롤링 실패: {trending_result}")
        
        # Excel 생성 결과
        excel_status = excel_result.get('status', 'unknown') if excel_result else 'unknown'
        excel_count = excel_result.get('processed_count', 0) if excel_result else 0
        
        logging.info(f"🎯 성공한 크롤링: {total_files}/2개")
        logging.info(f"📊 Excel 생성: {excel_status} ({excel_count}개 고유 기사 처리)")
        logging.info(f"📊 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if total_files > 0:
            logging.info("✅ 의료뉴스 크롤링 완료!")
        else:
            logging.warning("⚠️ 모든 크롤링이 실패했습니다!")
        
        return {
            'total_successful': total_files,
            'recent_news_file': recent_file,
            'trending_news_file': trending_file,
            'excel_status': excel_status,
            'excel_count': excel_count,
            'timestamp': datetime.now().isoformat(),
            'status': 'completed' if total_files > 0 else 'failed'
        }
        
    except Exception as e:
        logging.error(f"❌ 결과 집계 중 오류: {str(e)}")
        raise

# Task 정의

# Chrome 프로세스 정리 (시작 전)
cleanup_start = PythonOperator(
    task_id='cleanup_chrome_start',
    python_callable=cleanup_chrome_processes,
    dag=dag,
    execution_timeout=timedelta(minutes=5)
)

# 최근 뉴스 크롤링
crawl_recent_news = PythonOperator(
    task_id='crawl_recent_news',
    python_callable=run_recent_news_crawler,
    dag=dag,
    execution_timeout=timedelta(minutes=30)
)

# 크롤러 간 대기
delay_task = PythonOperator(
    task_id='delay_between_crawlers',
    python_callable=add_delay_between_crawlers,
    dag=dag,
    execution_timeout=timedelta(minutes=2)
)

# 트렌딩 뉴스 크롤링
crawl_trending_news = PythonOperator(
    task_id='crawl_trending_news',
    python_callable=run_trending_news_crawler,
    dag=dag,
    execution_timeout=timedelta(minutes=30)
)

# Excel 파일 생성
create_excel_task = PythonOperator(
    task_id='create_medical_excel',
    python_callable=create_medical_excel_report,
    dag=dag,
    execution_timeout=timedelta(minutes=10)
)

# 결과 집계
aggregate_task = PythonOperator(
    task_id='aggregate_results',
    python_callable=aggregate_results,
    dag=dag,
    execution_timeout=timedelta(minutes=5)
)

# Chrome 프로세스 정리 (완료 후)
cleanup_end = PythonOperator(
    task_id='cleanup_chrome_end',
    python_callable=cleanup_chrome_processes,
    dag=dag,
    execution_timeout=timedelta(minutes=5)
)

# Task 의존성 설정 - 순차적 실행 (Excel 생성 추가)
cleanup_start >> crawl_recent_news >> delay_task >> crawl_trending_news >> create_excel_task >> aggregate_task >> cleanup_end

# DAG 문서화
dag.doc_md = """
# 의료뉴스 크롤링 DAG

## 개요
이 DAG는 약업닷컴에서 의료뉴스를 수집하고 AI 요약을 생성합니다.

## 실행 일정
- **월요일~금요일 09:00, 13:00** (Asia/Seoul 기준)
- 주말 제외 평일만 실행
- 한 번에 하나의 DAG 인스턴스만 실행

## 주요 기능
1. **최근 뉴스 수집**: 오늘/어제 뉴스 크롤링 (날짜 기반 필터링)
2. **트렌딩 뉴스 수집**: 당일 트렌딩 뉴스 크롤링 (최근 뉴스 완료 후 실행)
3. **AI 요약**: OpenAI GPT-4o를 사용한 뉴스 요약 생성
4. **Excel 변환**: JSON 데이터를 Excel로 변환하며 중복 제거 및 고유 기사만 추출
5. **결과 저장**: JSON 및 Excel 형태로 파일 저장
6. **실시간 로깅**: 크롤링 진행상황을 실시간으로 Airflow 로그에 출력
7. **순차 실행**: 리소스 경합을 방지하기 위해 크롤러들을 순차적으로 실행

## 환경 설정
- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- Chrome/ChromeDriver 설치 필요
- `openpyxl` 패키지 필요 (Excel 생성용)

## 산출물
- `medical_recent_news_YYYYMMDD_HHMMSS.json`: 최근 뉴스 크롤링 결과
- `medical_top_trending_news_YYYYMMDD_HHMMSS.json`: 트렌딩 뉴스 크롤링 결과
- `medical_news_unique_YYYYMMDD_HHMMSS.xlsx`: 고유한 새 기사만 포함한 Excel 파일

## Task 순서
1. `cleanup_chrome_start`: Chrome 프로세스 정리
2. `crawl_recent_news`: 최근 뉴스 크롤링
3. `delay_between_crawlers`: 크롤러 간 대기 (30초)
4. `crawl_trending_news`: 트렌딩 뉴스 크롤링
5. `create_medical_excel`: Excel 파일 생성 (중복 제거)
6. `aggregate_results`: 전체 결과 집계
7. `cleanup_chrome_end`: Chrome 프로세스 정리

## 실시간 로깅
각 크롤러의 진행상황을 실시간으로 확인할 수 있습니다:
- 🏁 크롤링 시작 알림
- 📰 최근 뉴스: 개별 뉴스 수집 진행상황 
- 📈 트렌딩 뉴스: 개별 뉴스 수집 진행상황
- ✅ 성공/❌ 실패 상태 실시간 업데이트
- 🔄 재시도 메커니즘 진행상황
"""