#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime
from bs4 import BeautifulSoup
import os
import tempfile
import uuid
import random
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def setup_chrome_driver_ubuntu():
    """우분투 환경에 최적화된 Chrome 드라이버 설정"""
    
    # 기존 Chrome 프로세스 정리
    try:
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
        time.sleep(2)
        print("🧹 기존 Chrome/ChromeDriver 프로세스 정리 완료")
    except:
        pass
    
    try:
        chrome_options = Options()
        
        # Docker 환경에서는 반드시 headless 모드 필요
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--window-size=1280,720')
        
        # 세션 충돌 방지를 위한 핵심 옵션들
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor,ChromeWhatsNewUI')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-client-side-phishing-detection')
        chrome_options.add_argument('--disable-component-extensions-with-background-pages')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-images')  # 이미지 로딩 비활성화로 속도 향상
        
        # 고유 세션을 위한 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp(prefix=f'chrome_session_{uuid.uuid4().hex[:8]}_')
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        # 고유 디버깅 포트 설정
        debug_port = random.randint(9500, 9999)
        chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
        
        # 메모리 및 성능 최적화
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=2048')
        chrome_options.add_argument('--aggressive-cache-discard')
        
        # User Agent 설정
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
        
        # 자동화 감지 방지
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        print(f"🔧 임시 세션 디렉토리: {temp_dir}")
        print(f"🔧 디버깅 포트: {debug_port}")
        
        # Chrome 드라이버 초기화 - 명시적 ChromeDriver 경로 사용
        try:
            # ChromeDriver 경로 설정 (Docker 우선, 로컬 대안)
            chromedriver_paths = [
                '/usr/local/bin/chromedriver',  # Docker 환경
                '/home/son/chromedriver'        # 로컬 환경
            ]
            
            service = None
            for path in chromedriver_paths:
                if os.path.exists(path):
                    service = Service(path)
                    print(f"🔧 ChromeDriver 경로 발견: {path}")
                    break
            
            if service:
                driver = webdriver.Chrome(service=service, options=chrome_options)
                print(f"✅ Chrome 드라이버 생성 성공 (명시적 경로)")
            else:
                # fallback to system path
                driver = webdriver.Chrome(options=chrome_options)
                print("✅ Chrome 드라이버 생성 성공 (시스템 경로)")
            
        except Exception as e:
            print(f"❌ Chrome 드라이버 생성 실패: {e}")
            return None
        
        if driver:
            # 타임아웃 및 기본 설정
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)
            
            # 세션 정보 저장 (정리용)
            driver._temp_dir = temp_dir
            driver._debug_port = debug_port
            
            # 자동화 감지 방지 스크립트 실행
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Chrome 드라이버 설정 완료")
            return driver
        else:
            return None
                
    except Exception as e:
        print(f"❌ Chrome 드라이버 설정 중 전체 오류: {e}")
        return None

def get_webpage_with_selenium(url, attempt=1, max_attempts=5):
    """Selenium을 사용한 동적 웹페이지 HTML 가져오기 (재시도 메커니즘 포함)"""
    driver = None
    
    for current_attempt in range(attempt, max_attempts + 1):
        try:
            print(f"🔄 Selenium WebDriver 시작... (시도 {current_attempt}/{max_attempts})")
            
            # 이전 시도에서 실패한 경우 Chrome 프로세스 정리
            if current_attempt > 1:
                try:
                    subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                    subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
                    time.sleep(3)
                    print("🧹 이전 Chrome 프로세스 정리 완료")
                except:
                    pass
            
            driver = setup_chrome_driver_ubuntu()
            if not driver:
                if current_attempt < max_attempts:
                    print(f"❌ Chrome 드라이버 설정 실패 (시도 {current_attempt}/{max_attempts}) - 재시도")
                    continue
                else:
                    print(f"❌ Chrome 드라이버 설정 최종 실패")
                    return None
            
            print(f"📄 페이지 로딩 중: {url} (시도 {current_attempt}/{max_attempts})")
            driver.get(url)
            
            # 페이지 기본 로드 대기
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            print("✅ 기본 페이지 로드 완료")
            
            # 동적 콘텐츠 로딩 대기
            time.sleep(5)
            
            # 핵심 요소들 대기
            for element_id in ["contentBody", "conScroll"]:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, element_id))
                    )
                    print(f"✅ {element_id} 요소 로드 확인")
                except:
                    print(f"⚠️ {element_id} 요소 대기 타임아웃")
            
            # pgroup 클래스 요소들 대기
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "pgroup"))
                )
                print("✅ pgroup 요소 로드 확인")
            except:
                print("⚠️ pgroup 요소 대기 타임아웃")
            
            time.sleep(3)
            
            html_content = driver.page_source
            
            # 성공적으로 HTML 내용을 얻었는지 검증
            if html_content and len(html_content) > 1000:  # 최소 길이 확인
                print(f"✅ Selenium으로 웹페이지 요청 성공: {len(html_content)}자 (시도 {current_attempt}/{max_attempts})")
                return html_content
            else:
                raise Exception(f"HTML 내용이 부족함: {len(html_content) if html_content else 0}자")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Selenium 웹페이지 요청 실패 (시도 {current_attempt}/{max_attempts}): {error_msg}")
            
            if current_attempt < max_attempts:
                wait_time = current_attempt * 2  # 재시도 간격 증가
                print(f"⏰ {wait_time}초 후 재시도...")
                time.sleep(wait_time)
            else:
                print(f"💥 모든 시도 실패 ({max_attempts}회)")
                return None
                
        finally:
            # 각 시도마다 드라이버 정리
            if driver:
                try:
                    # 임시 디렉토리 정보 저장
                    temp_dir = getattr(driver, '_temp_dir', None)
                    driver.quit()
                    print(f"🔚 브라우저 종료 (시도 {current_attempt})")
                    
                    # 임시 디렉토리 정리
                    if temp_dir:
                        try:
                            import shutil
                            shutil.rmtree(temp_dir)
                            print(f"🧹 임시 디렉토리 정리: {temp_dir}")
                        except:
                            pass
                except:
                    pass
                driver = None
    
    return None

def crawl_anticorruption_law_with_retry(max_attempts=5):
    """청탁금지법 크롤링 함수 (재시도 메커니즘 포함)"""
    iframe_url = "https://www.law.go.kr/LSW//lsInfoP.do?lsiSeq=268655&chrClsCd=010202&urlMode=lsInfoP&efYd=20250121&ancYnChk=0"
    
    for attempt in range(1, max_attempts + 1):
        scraped_data = {}
        
        try:
            print(f"\n🔄 청탁금지법 크롤링 시작 (시도 {attempt}/{max_attempts})")
            print(f"📄 iframe 페이지 접속: {iframe_url}")
            
            # Selenium으로 동적 콘텐츠 로딩 (재시도 메커니즘 포함)
            html_content = get_webpage_with_selenium(iframe_url, attempt=1, max_attempts=3)
            if not html_content:
                raise Exception("iframe 페이지 HTML을 가져올 수 없습니다")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            print("✅ HTML 파싱 완료")
            
            # 법명 수집
            try:
                con_top = soup.find('div', id='conTop')
                if con_top and con_top.find('h2'):
                    law_name = con_top.find('h2').get_text(strip=True)
                    scraped_data['법명'] = law_name
                    print(f"✅ 법명 수집 완료: {law_name}")
                else:
                    scraped_data['법명'] = "법명 수집 실패"
            except Exception as e:
                scraped_data['법명'] = f"수집 실패: {str(e)}"
            
            # 시행 법률 정보 수집
            try:
                con_top = soup.find('div', id='conTop')
                if con_top:
                    div_elements = con_top.find_all('div', recursive=False)
                    if div_elements:
                        law_info = div_elements[0].get_text(strip=True)
                        scraped_data['시행_법률_정보'] = law_info
                        print(f"✅ 시행 법률 정보 수집 완료: {law_info[:100]}...")
                    else:
                        scraped_data['시행_법률_정보'] = "시행 법률 정보 없음"
                else:
                    scraped_data['시행_법률_정보'] = "conTop div 없음"
            except Exception as e:
                scraped_data['시행_법률_정보'] = f"수집 실패: {str(e)}"
            
            # pgroup 텍스트 추출 (핵심 기능)
            try:
                # DOM 구조 탐색: bodyId → searchForm → container → center → bodyContentTOP → viewwrapCenter → bodyContent → contentBody → sideCenter → conScroll
                path_elements = [
                    'bodyId', 'searchForm', 'container', 'center', 'bodyContentTOP', 
                    'viewwrapCenter', 'bodyContent', 'contentBody', 'sideCenter', 'conScroll'
                ]
                
                current_element = soup
                for element_id in path_elements:
                    current_element = current_element.find(id=element_id)
                    if current_element:
                        print(f"✓ {element_id} 발견")
                    else:
                        print(f"✗ {element_id} 찾을 수 없음")
                        break
                
                # conScroll에서 pgroup 요소들 추출
                if current_element:  # conScroll이 발견된 경우
                    all_pgroups = current_element.find_all('div', class_='pgroup')
                    if all_pgroups:
                        print(f"✓ pgroup 클래스 div {len(all_pgroups)}개 발견")
                        
                        pgroup_texts = []
                        for i, pgroup in enumerate(all_pgroups):
                            text = pgroup.get_text(strip=True)
                            if text:
                                pgroup_texts.append(text)
                                print(f"  - pgroup {i+1}: {len(text)}자")
                        
                        scraped_data['pgroup_텍스트'] = pgroup_texts
                        scraped_data['pgroup_개수'] = len(pgroup_texts)
                        print(f"✅ 총 {len(pgroup_texts)}개 pgroup 텍스트 수집 완료")
                        
                        # 성공 조건 확인
                        if len(pgroup_texts) > 0:
                            # 크롤링 메타데이터
                            scraped_data['크롤링_시간'] = datetime.now().isoformat()
                            scraped_data['소스_URL'] = iframe_url
                            scraped_data['크롤링_상태'] = "성공"
                            scraped_data['시도_횟수'] = attempt
                            
                            print(f"🎉 청탁금지법 크롤링 성공! (시도 {attempt}/{max_attempts})")
                            return scraped_data
                        else:
                            raise Exception("pgroup 텍스트가 수집되지 않음")
                    else:
                        raise Exception("pgroup 클래스를 찾을 수 없음")
                else:
                    raise Exception("DOM 구조 탐색 실패 - conScroll 요소 없음")
                    
            except Exception as e:
                print(f"❌ pgroup 텍스트 추출 실패: {str(e)}")
                raise e
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 크롤링 실패 (시도 {attempt}/{max_attempts}): {error_msg}")
            
            if attempt < max_attempts:
                wait_time = attempt * 3  # 재시도 간격 증가
                print(f"⏰ {wait_time}초 후 재시도...")
                time.sleep(wait_time)
            else:
                print(f"💥 모든 시도 실패 ({max_attempts}회)")
                # 최종 실패 시 오류 정보 반환
                scraped_data = {
                    '법명': "크롤링 실패",
                    '시행_법률_정보': "크롤링 실패", 
                    '크롤링_시간': datetime.now().isoformat(),
                    '소스_URL': iframe_url,
                    '크롤링_상태': "실패",
                    '시도_횟수': max_attempts,
                    '오류_메시지': error_msg
                }
                return scraped_data
    
    # 여기까지 오면 안됨, 하지만 안전장치
    return {
        '크롤링_상태': "실패",
        '오류_메시지': "예상치 못한 오류"
    }


def save_to_json(data, filename=None):
    """JSON 파일로 저장"""
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'anticorruption_law_{timestamp}.json'
    
    # crawler_result 디렉토리에 저장 - Docker 볼륨 마운트된 경로 사용
    result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
    
    os.makedirs(result_dir, exist_ok=True)
    filepath = os.path.join(result_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filepath

def main():
    """메인 실행 함수 (재시도 메커니즘 포함)"""
    print("🔄 청탁금지법 크롤링을 시작합니다...")
    print("=" * 60)
    
    try:
        # 재시도 메커니즘이 포함된 크롤링 실행
        data = crawl_anticorruption_law_with_retry(max_attempts=5)
        
        if data and data.get('크롤링_상태') == '성공':
            filepath = save_to_json(data)
            print("\n🎉 크롤링이 성공적으로 완료되었습니다!")
            print(f"💾 데이터 저장 완료: {filepath}")
            
            # 수집 결과 요약
            print("\n" + "=" * 60)
            print("📊 수집 결과 요약")
            print("=" * 60)
            print(f"📄 법명: {data.get('법명', 'N/A')}")
            print(f"📅 시행 정보: {data.get('시행_법률_정보', 'N/A')[:100]}...")
            print(f"📝 pgroup 개수: {data.get('pgroup_개수', 0)}개")
            print(f"🔄 성공한 시도: {data.get('시도_횟수', 'N/A')}번째")
            print(f"⏰ 크롤링 시간: {data.get('크롤링_시간', 'N/A')}")
                
        else:
            print(f"\n💥 크롤링 최종 실패")
            print(f"❌ 오류: {data.get('오류_메시지', '알 수 없는 오류')}")
            print(f"🔄 총 시도 횟수: {data.get('시도_횟수', 'N/A')}회")
            
            # 실패한 데이터도 저장
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            failed_filename = f'anticorruption_law_failed_{timestamp}.json'
            filepath = save_to_json(data, failed_filename)
            print(f"💾 실패 로그 저장: {filepath}")
    
    except Exception as unexpected_error:
        print(f"\n💥 예상치 못한 오류 발생: {str(unexpected_error)}")
        
        # 예상치 못한 오류도 기록
        error_data = {
            '크롤링_상태': "예상치_못한_오류",
            '오류_메시지': str(unexpected_error),
            '크롤링_시간': datetime.now().isoformat()
        }
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        error_filename = f'anticorruption_law_unexpected_error_{timestamp}.json'
        save_to_json(error_data, error_filename)
    
    finally:
        # Chrome 프로세스 최종 정리
        try:
            subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
            subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
            print("\n🧹 Chrome 프로세스 최종 정리 완료")
        except:
            pass
        
        print("\n" + "=" * 60)
        print("🏁 청탁금지법 크롤링 프로세스 종료")
        print("=" * 60)

if __name__ == "__main__":
    main()