#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
의료뉴스 크롤링 테스트 DAG - 2025년 8월 13일 날짜 고정
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
    'start_date': datetime(2025, 8, 17, 9, 0, tzinfo=local_tz),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'catchup': False
}

# DAG 정의
dag = DAG(
    'medical_news_crawling_test_20250813',
    default_args=default_args,
    description='의료뉴스 크롤링 테스트 - 2025년 8월 13일 날짜 고정',
    schedule=None,  # 수동 실행
    max_active_runs=1,
    tags=['medical', 'news', 'test', '20250813']
)

def run_recent_news_crawler_test():
    """최근 뉴스 크롤러 실행 함수 - 2025년 8월 13일 테스트"""
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
        
        logging.info(f"최근 뉴스 크롤러 시작 (테스트 날짜: 2025-08-13): {crawler_script}")
        
        # Python 스크립트 실행 - 날짜를 환경변수로 전달
        env = os.environ.copy()
        env['TEST_DATE'] = '2025-08-13'  # 테스트 날짜 설정
        env['PATH'] = '/home/airflow/.local/bin:' + env.get('PATH', '')
        
        process = subprocess.Popen(
            ['/home/airflow/.local/bin/python3', '-u', crawler_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd='/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func'),
            env=env,
            bufsize=1,
            universal_newlines=True
        )
        
        # 실시간 로그 출력
        logging.info("📺 실시간 크롤링 로그 시작 (테스트 날짜: 2025-08-13)...")
        output_lines = []
        
        try:
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    output_lines.append(line)
                    logging.info(f"📰 {line}")
            
            process.wait()
            stdout = '\n'.join(output_lines)
            
            if process.returncode == 0:
                logging.info("✅ 최근 뉴스 크롤링 완료 (테스트)")
                
                # 생성된 파일 확인
                import glob
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
                error_output = '\n'.join(output_lines[-10:])
                logging.error(f"❌ 최근 뉴스 크롤링 실패 (리턴코드: {process.returncode})")
                logging.error(f"마지막 출력: {error_output}")
                raise RuntimeError(f"크롤러 실행 실패 (리턴코드: {process.returncode})")
                
        except Exception as proc_e:
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

def run_trending_news_crawler_test():
    """트렌딩 뉴스 크롤러 실행 함수 - 2025년 8월 13일 테스트"""
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
        
        logging.info(f"트렌딩 뉴스 크롤러 시작 (테스트 날짜: 2025-08-13): {crawler_script}")
        
        # Python 스크립트 실행 - 날짜를 환경변수로 전달
        env = os.environ.copy()
        env['TEST_DATE'] = '2025-08-13'  # 테스트 날짜 설정
        env['PATH'] = '/home/airflow/.local/bin:' + env.get('PATH', '')
        
        process = subprocess.Popen(
            ['/home/airflow/.local/bin/python3', '-u', crawler_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd='/opt/airflow/func' if os.getenv('AIRFLOW__CORE__EXECUTOR') else os.path.join(os.path.dirname(current_dir), 'func'),
            env=env,
            bufsize=1,
            universal_newlines=True
        )
        
        # 실시간 로그 출력
        logging.info("📺 실시간 크롤링 로그 시작 (테스트 날짜: 2025-08-13)...")
        output_lines = []
        
        try:
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    line = output.strip()
                    output_lines.append(line)
                    logging.info(f"📈 {line}")
            
            process.wait()
            stdout = '\n'.join(output_lines)
            
            if process.returncode == 0:
                logging.info("✅ 트렌딩 뉴스 크롤링 완료 (테스트)")
                
                # 생성된 파일 확인
                import glob
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
                error_output = '\n'.join(output_lines[-10:])
                logging.error(f"❌ 트렌딩 뉴스 크롤링 실패 (리턴코드: {process.returncode})")
                logging.error(f"마지막 출력: {error_output}")
                raise RuntimeError(f"크롤러 실행 실패 (리턴코드: {process.returncode})")
                
        except Exception as proc_e:
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
        delay_seconds = 30
        logging.info(f"⏰ 크롤러 간 {delay_seconds}초 대기 중...")
        time.sleep(delay_seconds)
        logging.info("✅ 대기 완료, 다음 크롤러 준비됨")
        return {'status': 'success', 'delay_seconds': delay_seconds}
    except Exception as e:
        logging.error(f"❌ 대기 중 오류: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def create_medical_excel_report_test(**context):
    """테스트 크롤링 결과로 Medical Excel 파일 생성"""
    try:
        logging.info("📊 Medical Excel 파일 생성 시작 (테스트)")
        
        # 이전 태스크 결과 가져오기
        recent_result = context['task_instance'].xcom_pull(task_ids='crawl_recent_news_test')
        trending_result = context['task_instance'].xcom_pull(task_ids='crawl_trending_news_test')
        
        # 최소 하나의 크롤링이 성공했는지 확인
        success_count = 0
        if recent_result and recent_result.get('status') == 'success':
            success_count += 1
        if trending_result and trending_result.get('status') == 'success':
            success_count += 1
            
        if success_count > 0:
            logging.info(f"📊 Excel 파일 생성 시작 (성공한 크롤링: {success_count}/2개, 테스트)")
            
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
                    logging.info(f"✅ Excel 파일 생성 완료 (테스트): {len(result_df)}개 고유 기사 처리")
                    return {'status': 'success', 'processed_count': len(result_df), 'test_date': '2025-08-13'}
                else:
                    logging.warning("⚠️ Excel 파일 생성됨, 하지만 고유한 새 데이터가 없음 (테스트)")
                    return {'status': 'warning', 'message': '새로운 고유 데이터 없음', 'test_date': '2025-08-13'}
                    
            except ImportError as e:
                logging.error(f"❌ 모듈 임포트 실패: {e}")
                return {'status': 'error', 'message': f'모듈 임포트 실패: {e}'}
            except Exception as e:
                logging.error(f"❌ Excel 생성 과정에서 오류: {e}")
                return {'status': 'error', 'message': f'Excel 생성 오류: {e}'}
        else:
            logging.warning("⚠️ 성공한 크롤링이 없어 Excel 파일을 생성하지 않습니다 (테스트)")
            return {'status': 'skipped', 'message': '크롤링 실패로 Excel 생성 생략', 'test_date': '2025-08-13'}
        
    except Exception as e:
        logging.error(f"❌ Excel 생성 태스크 실행 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def upload_medical_excel_to_db_test(**context):
    """생성된 Medical Excel 파일을 데이터베이스에 업로드 (테스트)"""
    try:
        # 이전 태스크 결과 가져오기
        excel_result = context['task_instance'].xcom_pull(task_ids='create_medical_excel_test')
        
        if excel_result and excel_result.get('status') == 'success':
            logging.info("📤 Medical Excel 파일 업로드 시작 (테스트)")
            
            # newsstand_iframe_uploader.py 모듈 임포트
            import sys
            if os.getenv('AIRFLOW__CORE__EXECUTOR'):  # Docker 환경
                func_dir = '/opt/airflow/func'
            else:  # 로컬 환경
                func_dir = os.path.join(os.path.dirname(current_dir), 'func')
            
            if func_dir not in sys.path:
                sys.path.append(func_dir)
            
            try:
                import newsstand_iframe_uploader
                
                # 모듈 리로드 (최신 코드 반영)
                import importlib
                importlib.reload(newsstand_iframe_uploader)
                
                # medical 타입으로 업로드
                upload_success = newsstand_iframe_uploader.upload_latest_file(file_type='medical')
                
                if upload_success:
                    logging.info("✅ Medical Excel 파일 업로드 성공 (테스트)")
                    return {'status': 'success', 'message': '업로드 완료', 'test_date': '2025-08-13'}
                else:
                    logging.error("❌ Medical Excel 파일 업로드 실패 (테스트)")
                    return {'status': 'error', 'message': '업로드 실패'}
                    
            except ImportError as ie:
                logging.error(f"❌ newsstand_iframe_uploader 모듈 임포트 실패: {ie}")
                return {'status': 'error', 'message': f'모듈 임포트 실패: {ie}'}
            except Exception as ue:
                logging.error(f"❌ 업로드 과정에서 오류: {ue}")
                return {'status': 'error', 'message': f'업로드 오류: {ue}'}
        else:
            logging.warning("⚠️ Excel 파일이 생성되지 않아 업로드를 건너뜁니다")
            return {'status': 'skipped', 'message': 'Excel 파일 없음'}
            
    except Exception as e:
        logging.error(f"❌ 업로드 태스크 실행 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def cleanup_medical_recent_json_files(**context):
    """업로드 성공한 medical_recent JSON 파일 정리 (최신 4개만 유지)"""
    try:
        # 이전 태스크 결과 가져오기
        upload_result = context['task_instance'].xcom_pull(task_ids='upload_medical_excel_test')
        
        # 업로드가 성공한 경우에만 파일 정리
        if upload_result and upload_result.get('status') == 'success':
            logging.info("🗑️ Medical Recent JSON 파일 정리 시작...")
            
            # clear_files 모듈 import
            import sys
            sys.path.append('/opt/airflow/func')
            from clear_files import clear_json_files
            
            # medical_recent JSON 파일 정리 실행 (최신 4개만 유지)
            clear_json_files(file_type='medical_recent')
            
            logging.info("✅ Medical Recent JSON 파일 정리 완료")
            return {'status': 'success', 'message': 'Medical Recent JSON files cleaned up successfully'}
        else:
            logging.warning("⚠️ 업로드가 성공하지 않아 파일 정리를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Upload was not successful'}
            
    except Exception as e:
        logging.error(f"❌ Medical Recent JSON 파일 정리 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def cleanup_medical_trending_json_files(**context):
    """업로드 성공한 medical_trending JSON 파일 정리 (최신 4개만 유지)"""
    try:
        # 이전 태스크 결과 가져오기 (recent 파일 정리가 성공했을 때만 실행)
        recent_cleanup_result = context['task_instance'].xcom_pull(task_ids='cleanup_medical_recent_json_test')
        
        # 이전 정리가 성공하거나 스킵된 경우 실행
        if recent_cleanup_result and recent_cleanup_result.get('status') in ['success', 'skipped']:
            logging.info("🗑️ Medical Trending JSON 파일 정리 시작...")
            
            # clear_files 모듈 import
            import sys
            sys.path.append('/opt/airflow/func')
            from clear_files import clear_json_files
            
            # medical_trending JSON 파일 정리 실행 (최신 4개만 유지)
            clear_json_files(file_type='medical_trending')
            
            logging.info("✅ Medical Trending JSON 파일 정리 완료")
            return {'status': 'success', 'message': 'Medical Trending JSON files cleaned up successfully'}
        else:
            logging.warning("⚠️ 이전 단계가 완료되지 않아 파일 정리를 건너뜁니다.")
            return {'status': 'skipped', 'message': 'Previous cleanup was not completed'}
            
    except Exception as e:
        logging.error(f"❌ Medical Trending JSON 파일 정리 중 오류: {e}")
        return {'status': 'error', 'message': str(e)}

def aggregate_test_results(**context):
    """테스트 크롤링 결과 집계"""
    try:
        logging.info("📊 테스트 크롤링 결과 집계 중...")
        
        # XCom에서 결과 가져오기
        recent_result = context['task_instance'].xcom_pull(task_ids='crawl_recent_news_test')
        trending_result = context['task_instance'].xcom_pull(task_ids='crawl_trending_news_test')
        excel_result = context['task_instance'].xcom_pull(task_ids='create_medical_excel_test')
        upload_result = context['task_instance'].xcom_pull(task_ids='upload_medical_excel_test')
        
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
        
        # 업로드 결과
        upload_status = upload_result.get('status', 'unknown') if upload_result else 'unknown'
        upload_message = upload_result.get('message', '') if upload_result else ''
        
        logging.info(f"🎯 성공한 크롤링: {total_files}/2개")
        logging.info(f"📊 Excel 생성 상태: {excel_status}")
        logging.info(f"📤 DB 업로드 상태: {upload_status}")
        if excel_count > 0:
            logging.info(f"📊 처리된 뉴스 수: {excel_count}개")
        if upload_message:
            logging.info(f"📤 업로드 메시지: {upload_message}")
        logging.info(f"📊 테스트 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"📅 테스트 대상 날짜: 2025-08-13")
        
        if total_files > 0:
            logging.info("✅ 의료뉴스 테스트 크롤링 완료!")
        else:
            logging.warning("⚠️ 모든 테스트 크롤링이 실패했습니다!")
        
        return {
            'total_successful': total_files,
            'recent_news_file': recent_file,
            'trending_news_file': trending_file,
            'excel_status': excel_status,
            'excel_count': excel_count,
            'upload_status': upload_status,
            'upload_message': upload_message,
            'test_date': '2025-08-13',
            'timestamp': datetime.now().isoformat(),
            'status': 'completed' if total_files > 0 else 'failed'
        }
        
    except Exception as e:
        logging.error(f"❌ 테스트 결과 집계 중 오류: {str(e)}")
        raise

# Task 정의

# Chrome 프로세스 정리 (시작 전)
cleanup_start = PythonOperator(
    task_id='cleanup_chrome_start',
    python_callable=cleanup_chrome_processes,
    dag=dag,
    execution_timeout=timedelta(minutes=5)
)

# 최근 뉴스 크롤링 (테스트)
crawl_recent_news_test = PythonOperator(
    task_id='crawl_recent_news_test',
    python_callable=run_recent_news_crawler_test,
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

# 트렌딩 뉴스 크롤링 (테스트)
crawl_trending_news_test = PythonOperator(
    task_id='crawl_trending_news_test',
    python_callable=run_trending_news_crawler_test,
    dag=dag,
    execution_timeout=timedelta(minutes=30)
)

# Excel 파일 생성 (테스트)
create_excel_test_task = PythonOperator(
    task_id='create_medical_excel_test',
    python_callable=create_medical_excel_report_test,
    dag=dag,
    execution_timeout=timedelta(minutes=10)
)

# Medical Excel 파일 업로드 (테스트)
upload_medical_excel_test_task = PythonOperator(
    task_id='upload_medical_excel_test',
    python_callable=upload_medical_excel_to_db_test,
    dag=dag,
    execution_timeout=timedelta(minutes=5)
)

cleanup_recent_json_test_task = PythonOperator(
    task_id='cleanup_medical_recent_json_test',
    python_callable=cleanup_medical_recent_json_files,
    dag=dag,
)

cleanup_trending_json_test_task = PythonOperator(
    task_id='cleanup_medical_trending_json_test',
    python_callable=cleanup_medical_trending_json_files,
    dag=dag,
)

# 결과 집계
aggregate_task = PythonOperator(
    task_id='aggregate_test_results',
    python_callable=aggregate_test_results,
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

# Task 의존성 설정 - Excel 생성 및 DB 업로드 추가
cleanup_start >> crawl_recent_news_test >> delay_task >> crawl_trending_news_test >> create_excel_test_task >> upload_medical_excel_test_task >> cleanup_recent_json_test_task >> cleanup_trending_json_test_task >> aggregate_task >> cleanup_end

# DAG 문서화
dag.doc_md = """
# 의료뉴스 크롤링 테스트 DAG - 2025년 8월 13일

## 개요
이 DAG는 2025년 8월 13일 날짜로 의료뉴스 크롤링을 테스트합니다.

## 테스트 설정
- **테스트 날짜**: 2025년 8월 13일 (환경변수 TEST_DATE로 전달)
- **실행 방식**: 수동 실행 (schedule=None)
- **대상**: 최근 뉴스 + 트렌딩 뉴스

## 주요 기능
1. **최근 뉴스 수집**: 2025-08-13 날짜 뉴스 크롤링
2. **트렌딩 뉴스 수집**: 2025-08-13 날짜 트렌딩 뉴스 크롤링
3. **AI 요약**: OpenAI GPT-4o를 사용한 뉴스 요약 생성
4. **순차 실행**: 리소스 경합 방지를 위한 순차 실행

## Task 순서
1. `cleanup_chrome_start`: Chrome 프로세스 정리
2. `crawl_recent_news_test`: 최근 뉴스 크롤링 (2025-08-13)
3. `delay_between_crawlers`: 크롤러 간 대기 (30초)
4. `crawl_trending_news_test`: 트렌딩 뉴스 크롤링 (2025-08-13)
5. `create_medical_excel_test`: 크롤링 결과로 Excel 파일 생성
6. `upload_medical_excel_test`: Excel 파일을 데이터베이스에 업로드
7. `aggregate_test_results`: 테스트 결과 집계
8. `cleanup_chrome_end`: Chrome 프로세스 정리

## 환경 설정
- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- `ACCESS_TOKEN`: DB 업로드용 API 인증 토큰 (필수)
- `TEST_DATE`: 2025-08-13 (자동 설정)

## 산출물
- `medical_recent_news_YYYYMMDD_HHMMSS.json`: 최근 뉴스 테스트 결과
- `medical_top_trending_news_YYYYMMDD_HHMMSS.json`: 트렌딩 뉴스 테스트 결과
- `medical_news_unique_YYYYMMDD_HHMMSS.xlsx`: 통합 Excel 보고서
- **데이터베이스 업로드**: FastAPI 백엔드를 통해 DB에 자동 업로드
"""