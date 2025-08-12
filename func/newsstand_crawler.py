#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 뉴스스탠드 iframe 기반 KBS/MBC/SBS 뉴스 크롤러
우분투 환경 대응
"""

# 실시간 출력을 위한 설정
import sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import requests
import os
import subprocess
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import openai
import re
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# 전역 설정: 데이터 수집 완료 후 로그 최소화
QUIET_MODE = True  # True면 로그 최소화

def log_message(message, force=False, flush=True):
    """조건부 로그 출력"""
    if not QUIET_MODE or force:
        print(message, flush=flush)

# .env 파일 로드 (프로젝트 루트에서)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def setup_chrome_driver_ubuntu():
    """우분투 환경에 최적화된 Chrome 드라이버 설정"""
    
    # 기존 Chrome 프로세스 정리
    try:
        import subprocess
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
        time.sleep(2)
        log_message("🧹 기존 Chrome/ChromeDriver 프로세스 정리 완료")
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
        
        # 고유 세션을 위한 임시 디렉토리 생성
        import tempfile
        import uuid
        temp_dir = tempfile.mkdtemp(prefix=f'chrome_session_{uuid.uuid4().hex[:8]}_')
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        # 고유 디버깅 포트 설정
        import random
        debug_port = random.randint(9500, 9999)
        chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
        
        # 메모리 및 성능 최적화
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=2048')
        chrome_options.add_argument('--aggressive-cache-discard')
        
        # User Agent 설정
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
        
        log_message(f"🔧 임시 세션 디렉토리: {temp_dir}")
        log_message(f"🔧 디버깅 포트: {debug_port}")
        
        # Chrome 드라이버 초기화 - 명시적 ChromeDriver 경로 사용
        driver = None
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
                    log_message(f"🔧 ChromeDriver 경로 발견: {path}")
                    break
            
            if service:
                driver = webdriver.Chrome(service=service, options=chrome_options)
                log_message(f"✅ Chrome 드라이버 생성 성공 (명시적 경로)")
            else:
                # fallback to system path
                driver = webdriver.Chrome(options=chrome_options)
                log_message("✅ Chrome 드라이버 생성 성공 (시스템 경로)")
            
        except Exception as e:
            log_message(f"❌ Chrome 드라이버 생성 실패: {e}")
            return None
        
        if driver:
            # 타임아웃 및 기본 설정
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)
            
            # 세션 정보 저장 (정리용)
            driver._temp_dir = temp_dir
            driver._debug_port = debug_port
            
            log_message("✅ Chrome 드라이버 설정 완료")
            return driver
        else:
            return None
                
    except Exception as e:
        log_message(f"❌ Chrome 드라이버 설정 중 전체 오류: {e}")
        return None

def detect_current_press(driver):
    """현재 화면에 표시된 언론사 감지 (정확한 xpath 기반)"""
    try:
        # 정확한 xpath로 언론사 이미지 찾기
        press_img_xpath = "//*[@id='focusPanelCenter']/div/h3/a/img"
        target_presses = ['KBS', 'MBC', 'SBS']
        
        try:
            # 해당 위치의 이미지 요소 찾기
            press_img = driver.find_element(By.XPATH, press_img_xpath)
            
            if press_img.is_displayed():
                # alt 속성 확인
                alt_text = press_img.get_attribute('alt')
                log_message(f"🔍 감지된 alt 텍스트: '{alt_text}'")
                
                # 대상 언론사인지 정확히 확인 (부분 문자열이 아닌 정확한 매칭)
                for press in target_presses:
                    if press == 'KBS':
                        # KBS는 정확히 'KBS'만 매칭 (KBS World 제외)
                        if alt_text == 'KBS' or alt_text.startswith('KBS ') or alt_text.endswith(' KBS') or ' KBS ' in alt_text:
                            # KBS World는 제외
                            if 'World' not in alt_text and 'world' not in alt_text:
                                log_message(f"🎯 현재 언론사: KBS 감지됨 (alt: '{alt_text}')")
                                return 'KBS'
                    else:
                        # MBC, SBS는 기존 방식대로
                        if press in alt_text:
                            log_message(f"🎯 현재 언론사: {press} 감지됨 (alt: '{alt_text}')")
                            return press
                
                log_message(f"❌ 대상 언론사가 아님: {alt_text}")
                return None
            else:
                log_message("❌ 언론사 이미지가 표시되지 않음")
                return None
                
        except NoSuchElementException:
            log_message(f"❌ 지정된 xpath에서 이미지를 찾을 수 없음: {press_img_xpath}")
            
            # 대체 방법: 일반적인 alt 속성 검색
            log_message("🔄 대체 방법으로 언론사 검색 중...")
            for press in target_presses:
                try:
                    if press == 'KBS':
                        # KBS는 정확한 매칭으로 검색
                        press_img = driver.find_element(By.XPATH, f"//img[@alt='KBS']")
                        if press_img.is_displayed():
                            log_message(f"🎯 대체 방법으로 KBS 감지됨")
                            return 'KBS'
                    else:
                        # MBC, SBS는 기존 방식
                        press_img = driver.find_element(By.XPATH, f"//img[@alt='{press}']")
                        if press_img.is_displayed():
                            log_message(f"🎯 대체 방법으로 {press} 감지됨")
                            return press
                except NoSuchElementException:
                    continue
            
            log_message("❌ 대체 방법으로도 언론사를 찾을 수 없음")
            return None
        
    except Exception as e:
        log_message(f"❌ 언론사 감지 중 오류: {e}")
        
        # 현재 페이지 상태 디버깅 정보 출력
        try:
            log_message(f"📄 현재 URL: {driver.current_url}")
            log_message(f"📄 페이지 제목: {driver.title}")
            
            # 페이지에 있는 모든 img 태그의 alt 속성 확인
            all_imgs = driver.find_elements(By.TAG_NAME, "img")
            log_message(f"📷 페이지 내 총 이미지 수: {len(all_imgs)}")
            
            for i, img in enumerate(all_imgs[:10]):  # 처음 10개만 확인
                try:
                    alt = img.get_attribute('alt')
                    src = img.get_attribute('src')
                    if alt:
                        log_message(f"  [{i+1}] alt='{alt}', src='{src[:50]}...'")
                except:
                    continue
                    
        except Exception as debug_e:
            log_message(f"❌ 디버깅 정보 출력 실패: {debug_e}")
        
        return None

def extract_news_from_iframe(driver, press_name):
    """iframe 내부에서 뉴스 추출"""
    try:
        log_message(f"📰 {press_name} iframe에서 뉴스 추출 중...")
        
        # iframe 찾기를 위한 다양한 선택자 시도
        iframe_selectors = [
            "//*[@id='focusPanelCenter']/div/iframe",
            "//iframe[contains(@src, 'newsstand')]",
            "//iframe",
            "#focusPanelCenter iframe",
            ".focus_panel iframe"
        ]
        
        iframe_found = False
        for selector in iframe_selectors:
            try:
                if selector.startswith("//") or selector.startswith("/"):
                    iframe = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                else:
                    iframe = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                
                # iframe으로 전환
                driver.switch_to.frame(iframe)
                log_message(f"✅ {press_name} iframe 전환 완료 (선택자: {selector})")
                iframe_found = True
                break
                
            except TimeoutException:
                continue
            except Exception as e:
                log_message(f"❌ iframe 선택자 '{selector}' 오류: {e}")
                continue
        
        if not iframe_found:
            log_message(f"❌ {press_name} iframe을 찾을 수 없음")
            return []
            
        # iframe 내부 페이지 로딩 대기
        time.sleep(3)
        
        # iframe 내부 페이지 상태 확인
        try:
            current_url = driver.current_url
            page_source_length = len(driver.page_source)
            log_message(f"📄 iframe 내부 URL: {current_url}")
            log_message(f"📄 iframe 페이지 소스 길이: {page_source_length}")
        except:
            pass
        
        headlines = []
        
        # iframe 내부에서 뉴스 링크 찾기
        news_selectors = [
            "//a[contains(@href, 'news')]",
            # "//a[contains(@href, f'{press_name.lower()}')]",
            # "//div[contains(@class, 'news')]//a",
            # "//div[contains(@class, 'headline')]//a",
            # "//div[contains(@class, 'article')]//a",
            # "//ul//a",
            # "//li//a",
            # "//h1//a",
            # "//h2//a",
            # "//h3//a",
            # "//span//a",
            # "//p//a"
        ]
        
        for selector_index, selector in enumerate(news_selectors):
            try:
                log_message(f"  🔍 [{selector_index + 1}/{len(news_selectors)}] '{selector}' 선택자 검색 중...")
                
                news_links = driver.find_elements(By.XPATH, selector)
                
                if not news_links:
                    log_message(f"    ❌ 뉴스 링크 없음")
                    continue
                
                log_message(f"    ✅ {len(news_links)}개 링크 발견")
                
                for link in news_links[:20]:  # 각 선택자당 최대 20개
                    try:
                        title = link.text.strip()
                        url = link.get_attribute('href')
                        
                        if not title or not url:
                            continue
                        
                        if len(title) < 5:  # 너무 짧은 제목 제외
                            continue
                        
                        # 중복 체크
                        if any(news['title'] == title for news in headlines):
                            continue
                        
                        # 뉴스 데이터 생성
                        news_data = {
                            'rank': len(headlines) + 1,
                            'title': title,
                            'url': url,
                            'press': press_name,
                            'pub_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            'source': f'iframe_{press_name.lower()}_selector_{selector_index + 1}'
                        }
                        
                        headlines.append(news_data)
                        log_message(f"      [{len(headlines)}] {title[:50]}...")
                            
                    except Exception as e:
                        continue
                    
            except Exception as e:
                log_message(f"    ❌ '{selector}' 선택자 오류: {e}")
                continue
        
        # iframe에서 벗어나기
        driver.switch_to.default_content()
        log_message(f"✅ {press_name}에서 {len(headlines)}개 뉴스 수집 완료")
        
        return headlines
        
    except Exception as e:
        log_message(f"❌ {press_name} iframe 뉴스 추출 오류: {e}")
        # iframe에서 벗어나기
        try:
            driver.switch_to.default_content()
        except:
            pass
        return []

def click_next_button(driver, max_retries=3):
    """다음 버튼 클릭 (재시도 로직 포함)"""
    next_button_xpaths = [
        "//*[@id='content']/div[2]/div/div[4]/a[2]",
        "//a[contains(@class, 'next')]",
        "//a[contains(text(), '다음')]",
        "//button[contains(@class, 'next')]",
        "//div[contains(@class, 'paging')]//a[2]"
    ]
    
    for retry in range(max_retries):
        try:
            log_message(f"🔄 다음 버튼 클릭 시도 {retry + 1}/{max_retries}")
            
            # 여러 xpath 시도
            next_button = None
            for xpath in next_button_xpaths:
                try:
                    next_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    log_message(f"✅ 버튼 발견: {xpath}")
                    break
                except:
                    continue
            
            if next_button is None:
                log_message(f"❌ {retry + 1}번째 시도: 다음 버튼을 찾을 수 없음")
                continue
            
            # 버튼 클릭 시도 (두 가지 방법)
            try:
                # 방법 1: JavaScript 클릭
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(3)  # 페이지 전환 대기 (3초)
                log_message("✅ JavaScript로 버튼 클릭 성공")
                return True
            except Exception as e1:
                log_message(f"❌ JavaScript 클릭 실패: {e1}")
                try:
                    # 방법 2: 일반 클릭
                    next_button.click()
                    time.sleep(3)  # 페이지 전환 대기 (3초)
                    log_message("✅ 일반 클릭 성공")
                    return True
                except Exception as e2:
                    log_message(f"❌ 일반 클릭도 실패: {e2}")
                    continue
                    
        except Exception as e:
            log_message(f"❌ {retry + 1}번째 시도 전체 실패: {e}")
            if retry < max_retries - 1:
                log_message("🔄 페이지 새로고침 후 재시도...")
                try:
                    driver.refresh()
                    time.sleep(3)
                except:
                    pass
            continue
    
    log_message(f"❌ {max_retries}번 시도 후 버튼 클릭 최종 실패")
    return False

def crawl_newsstand_with_iframe(driver):
    """iframe 기반 뉴스스탠드 크롤링 메인 함수"""
    try:
        log_message("📰 네이버 뉴스스탠드 접속 중...")
        
        # 페이지 접속 전 대기
        time.sleep(2)
        
        # 뉴스스탠드 페이지 접속
        driver.get("https://newsstand.naver.com/")
        
        # 페이지 로딩 대기 (더 안정적으로)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            log_message("✅ 페이지 로딩 완료")
        except TimeoutException:
            log_message("❌ 페이지 로딩 타임아웃")
            return []
        
        # 추가 로딩 대기
        time.sleep(5)
        
        # 현재 페이지 상태 확인
        log_message(f"📄 현재 페이지 제목: {driver.title}")
        log_message(f"📄 현재 URL: {driver.current_url}")
        
        all_headlines = []
        found_presses = []  # KBS/MBC/SBS 수집 완료된 언론사
        all_seen_presses = []  # 모든 본 언론사 기록 (중복 감지용)
        max_attempts = 200  # 최대 200번 시도로 증가
        cycles_completed = 0  # 완료된 순환 횟수
        first_press_in_cycle = None  # 각 사이클의 첫 언론사
        
        for attempt in range(max_attempts):
            log_message(f"\n🔄 {attempt + 1}번째 시도...")
            
            # 현재 언론사 감지
            current_press = detect_current_press(driver)
            
            if current_press:
                # 사이클 시작 감지
                if cycles_completed == 0 and first_press_in_cycle is None:
                    first_press_in_cycle = current_press
                    log_message(f"🏁 첫 번째 사이클 시작 - 첫 언론사: {first_press_in_cycle}")
                
                # 이미 본 언론사가 다시 나타났는지 확인 (한 사이클 완료)
                if cycles_completed > 0 and current_press == first_press_in_cycle:
                    cycles_completed += 1
                    log_message(f"🔄 {cycles_completed}번째 사이클 완룉! (다시 {first_press_in_cycle} 등장)")
                    log_message(f"📋 이번 사이클에서 확인한 언론사: {all_seen_presses[-(len(all_seen_presses) % 52):] if len(all_seen_presses) > 52 else all_seen_presses}")
                    
                    # 아직 못 찾은 언론사 확인
                    missing_presses = [p for p in ['KBS', 'MBC', 'SBS'] if p not in found_presses]
                    if missing_presses:
                        log_message(f"⚠️ 아직 못 찾은 언론사: {missing_presses}")
                        log_message("🔄 다음 사이클 진행...")
                    else:
                        log_message("✅ 모든 대상 언론사를 찾았습니다!", force=True)
                        break
                
                # 언론사 기록
                all_seen_presses.append(current_press)
                if cycles_completed == 0 and len(all_seen_presses) > 0 and current_press == all_seen_presses[0] and len(all_seen_presses) > 1:
                    cycles_completed = 1
                    log_message(f"🔄 첫 번째 사이클 완룉 감지!")
                
                # KBS/MBC/SBS 중 하나이고 아직 수집하지 않았다면 뉴스 수집
                target_presses = ['KBS', 'MBC', 'SBS']
                if current_press in target_presses and current_press not in found_presses:
                    log_message(f"🎯 대상 언론사 발견: {current_press}", force=True)
                    
                    # iframe에서 뉴스 추출
                    news_from_iframe = extract_news_from_iframe(driver, current_press)
                    
                    if news_from_iframe:
                        all_headlines.extend(news_from_iframe)
                        found_presses.append(current_press)
                        log_message(f"✅ {current_press} 뉴스 {len(news_from_iframe)}개 수집 완룉", force=True)
                        log_message(f"📊 현재까지 수집한 언론사: {found_presses} ({len(found_presses)}/3)", force=True)
                    else:
                        log_message(f"⚠️ {current_press}에서 뉴스를 추출하지 못했습니다.", force=True)
                    
                    # 3개 언론사 모두 찾았으면 종료
                    if len(found_presses) >= 3:
                        log_message("🎉 KBS, MBC, SBS 모두 찾았습니다!", force=True)
                        break
                elif current_press in target_presses:
                    log_message(f"⏭️ {current_press}는 이미 수집했습니다.")
                else:
                    log_message(f"⏭️ {current_press}는 대상 언론사가 아닙니다.")
                
                # 2사이클 이상 돌았는데도 못 찾았으면 경고
                if cycles_completed >= 2:
                    missing = [p for p in ['KBS', 'MBC', 'SBS'] if p not in found_presses]
                    if missing:
                        log_message(f"⚠️ {cycles_completed}번의 사이클 후에도 {missing}를 찾지 못했습니다.", force=True)
            else:
                log_message("⏭️ 언론사를 감지할 수 없습니다.")
            
            # 다음 버튼 클릭 (재시도 포함)
            click_success = click_next_button(driver, max_retries=3)
            if not click_success:
                log_message("⚠️ 다음 버튼 클릭 실패, 하지만 탐색 계속...")
                # 버튼 클릭에 실패해도 탐색을 계속하기 위해 짧은 대기 후 진행
                time.sleep(2)
                # 페이지 새로고침으로 복구 시도
                try:
                    log_message("🔄 페이지 새로고침으로 복구 시도...")
                    driver.refresh()
                    time.sleep(3)
                except Exception as refresh_e:
                    log_message(f"❌ 페이지 새로고침 실패: {refresh_e}")
                    # 그래도 계속 시도
                    pass
        
        log_message(f"\n📊 최종 수집 결과:", force=True)
        log_message(f"   시도 횟수: {attempt + 1}/{max_attempts}", force=True)
        log_message(f"   완료된 사이클 수: {cycles_completed}회", force=True)
        log_message(f"   확인한 고유 언론사 수: {len(set(all_seen_presses))}개", force=True)
        log_message(f"   수집 완료된 언론사: {found_presses} ({len(found_presses)}/3)", force=True)
        log_message(f"   총 뉴스 수: {len(all_headlines)}개", force=True)
        
        # 누락된 언론사 표시
        missing = [p for p in ['KBS', 'MBC', 'SBS'] if p not in found_presses]
        if missing:
            log_message(f"   ⚠️ 수집하지 못한 언론사: {missing}", force=True)
        
        for press in ['KBS', 'MBC', 'SBS']:
            press_count = len([n for n in all_headlines if n['press'] == press])
            log_message(f"   - {press}: {press_count}개", force=True)
        
        return all_headlines
        
    except Exception as e:
        log_message(f"❌ 뉴스스탠드 크롤링 오류: {e}", force=True)
        return []

def crawl_article_content(url):
    """뉴스 기사 본문 추출"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 다양한 본문 선택자 시도
        content_selectors = [
            'div#articleBodyContents',
            'div.news_end',
            'div.article_body',
            'div._article_body_contents',
            'div.go_trans._article_content',
            'article',
            'div.article-view-content-div',
            'div#newsEndContents',
            'div.article_body_text',
            'div.article-body',
            '.article_content'
        ]
        
        article_content = ""
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                for script in content_elem(["script", "style"]):
                    script.decompose()
                article_content = content_elem.get_text(strip=True)
                break
        
        if not article_content:
            paragraphs = soup.find_all('p')
            article_content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # 텍스트 정리
        article_content = re.sub(r'\s+', ' ', article_content)
        article_content = re.sub(r'\n+', ' ', article_content)
        
        return article_content.strip() if article_content else None
        
    except Exception as e:
        log_message(f"    ❌ 본문 추출 오류: {e}")
        return None

def summarize_with_llm(content, title, press):
    """OpenAI를 사용하여 기사 요약"""
    if not content or len(content.strip()) < 50:
        return None
    
    try:
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": f"당신은 {press} 뉴스 기사를 간결하고 명확하게 요약하는 전문가입니다. 2-3문장으로 핵심 내용만 요약해주세요."
                },
                {
                    "role": "user", 
                    "content": f"다음 {press} 뉴스 기사를 2-3문장으로 요약해주세요:\n\n제목: {title}\n\n내용: {content}"
                }
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        log_message(f"    ❌ LLM 요약 오류: {e}")
        return None

def save_news_data(news_list, filename=None):
    """뉴스 데이터를 JSON 파일로 저장"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"newsstand_iframe_{timestamp}.json"
    
    # crawler_result 디렉토리에 저장 - Docker 볼륨 마운트된 경로 사용
    result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
    
    os.makedirs(result_dir, exist_ok=True)
    filepath = os.path.join(result_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(news_list, f, ensure_ascii=False, indent=2)
        log_message(f"💾 데이터 저장 완룉: {filepath}", force=True)
        # 파일 존재 확인
        if os.path.exists(filepath):
            log_message(f"✅ 파일 확인됨: {os.path.getsize(filepath)} bytes", force=True)
        return filepath
    except Exception as e:
        log_message(f"❌ 파일 저장 오류: {e}", force=True)
        log_message(f"    시도한 경로: {filepath}", force=True)
        return None

def main_with_retry(max_retries=3):
    """재시도 메커니즘이 포함된 메인 실행 함수"""
    log_message("=" * 80, force=True)
    log_message("📺 네이버 뉴스스탠드 iframe 기반 KBS/MBC/SBS 뉴스 크롤러", force=True)
    log_message("🐧 우분투 환경 최적화 + 3회 재시도 메커니즘", force=True)
    log_message("=" * 80, force=True)
    
    # OpenAI API 키 확인
    if not os.getenv('OPENAI_API_KEY'):
        log_message("❌ 환경변수에서 OpenAI API 키를 찾을 수 없습니다.", force=True)
        log_message("📝 .env 파일에 다음 변수를 설정해주세요:", force=True)
        log_message("   OPENAI_API_KEY=your_openai_api_key", force=True)
        return
    
    headlines = []
    
    for attempt in range(1, max_retries + 1):
        driver = None
        try:
            log_message(f"\n🔄 뉴스스탠드 크롤링 시도 {attempt}/{max_retries}", force=True)
            
            # Chrome 프로세스 정리 (재시도 전)
            try:
                import subprocess
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
                time.sleep(2)
                log_message("🧹 이전 Chrome 프로세스 정리 완료")
            except:
                pass
            
            # 새로운 드라이버 설정
            log_message(f"🚀 1단계: Chrome 브라우저 설정 중... (시도 {attempt}/{max_retries})", force=True)
            driver = setup_chrome_driver_ubuntu()
            if not driver:
                raise Exception("Chrome 드라이버 설정 실패")
            
            # 뉴스스탠드 크롤링
            log_message(f"📰 2단계: iframe 기반 뉴스 수집 중... (시도 {attempt}/{max_retries})", force=True)
            headlines = crawl_newsstand_with_iframe(driver)
            
            if not headlines:
                raise Exception("뉴스 수집 실패: 헤드라인 없음")
            
            # 크롤링 결과 검증
            found_presses = list(set([news['press'] for news in headlines]))
            required_presses = ['KBS', 'MBC', 'SBS']
            missing_presses = [p for p in required_presses if p not in found_presses]
            
            log_message(f"✅ 총 {len(headlines)}개의 뉴스를 수집했습니다.", force=True)
            log_message(f"📊 수집된 언론사: {found_presses}", force=True)
            
            # 성공 조건: 최소 2개 언론사 또는 마지막 시도에서는 1개 이상
            min_required = 2 if attempt < max_retries else 1
            if len(found_presses) >= min_required:
                log_message(f"✅ 뉴스스탠드 크롤링 성공! ({attempt}/{max_retries})", force=True)
                if missing_presses:
                    log_message(f"⚠️ 일부 누락된 언론사: {missing_presses}", force=True)
                break
            else:
                raise Exception(f"불충분한 언론사 수집: {found_presses} (최소 {min_required}개 필요)")
                
        except Exception as e:
            log_message(f"❌ 시도 {attempt} 실패: {e}", force=True)
            
            # 마지막 시도가 아니면 재시도 안내
            if attempt < max_retries:
                wait_time = attempt * 5  # 재시도 간격을 점진적으로 증가
                log_message(f"⏰ {wait_time}초 후 재시도합니다...", force=True)
                time.sleep(wait_time)
            else:
                log_message(f"💥 모든 시도 실패. 최대 재시도 횟수({max_retries}) 도달", force=True)
                headlines = []  # 빈 결과 설정
        
        finally:
            # 각 시도마다 드라이버 정리
            if driver:
                try:
                    driver.quit()
                    log_message(f"🔚 브라우저 종료 (시도 {attempt})")
                    time.sleep(2)
                except:
                    pass
            
            # Chrome 프로세스 강제 정리
            try:
                import subprocess
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
            except:
                pass
    
    # 결과 처리
    if not headlines:
        log_message("💥 뉴스스탠드 크롤링 최종 실패!", force=True)
        return
        
    return headlines

def main():
    """메인 실행 함수 (하위 호환성 유지)"""
    headlines = main_with_retry(max_retries=3)
    
    if not headlines:
        log_message("💥 뉴스스탠드 크롤링 최종 실패!", force=True)
        return
        
    # 3단계: 본문 추출 및 요약
    log_message(f"\n📝 3단계: 뉴스 본문 추출 및 AI 요약 생성 중...", force=True)
    
    processed_news = []
    
    for i, news in enumerate(headlines, 1):
        print(f"\n[{i:2d}/{len(headlines)}] {news['press']} - {news['title'][:60]}...", flush=True)
        
        # 본문 추출
        print("    📄 본문 추출 중...", flush=True)
        content = crawl_article_content(news['url'])
        
        if content:
            print(f"    ✅ 본문 추출 성공 (길이: {len(content)}자)", flush=True)
            
            # LLM 요약
            print("    🤖 AI 요약 생성 중...", flush=True)
            summary = summarize_with_llm(content, news['title'], news['press'])
            
            if summary:
                print(f"    📝 AI 요약: {summary}", flush=True)
                news['ai_summary'] = summary
            else:
                print("    ❌ AI 요약 실패", flush=True)
                news['ai_summary'] = None
        else:
            print("    ❌ 본문 추출 실패", flush=True)
            news['ai_summary'] = None
        
        processed_news.append(news)
        
        # API 제한 고려한 대기
        if i < len(headlines):
            time.sleep(2)
    
    # 4단계: 결과 저장
    print(f"\n💾 4단계: 결과 저장 중...", flush=True)
    filename = save_news_data(processed_news)
    
    # 5단계: 요약 결과 출력
    print(f"\n📋 5단계: 최종 결과", flush=True)
    print("=" * 80, flush=True)
    
    success_count = sum(1 for news in processed_news if news.get('ai_summary'))
    
    print(f"📊 전체 뉴스: {len(processed_news)}개", flush=True)
    print(f"✅ 요약 성공: {success_count}개", flush=True)
    print(f"❌ 요약 실패: {len(processed_news) - success_count}개", flush=True)
    
    for press in ['KBS', 'MBC', 'SBS']:
        press_news = [n for n in processed_news if n['press'] == press]
        press_summaries = [n for n in press_news if n.get('ai_summary')]
        print(f"📺 {press}: {len(press_news)}개 (요약 완료: {len(press_summaries)}개)", flush=True)
    
    print(f"\n💾 저장된 파일: {filename}", flush=True)
    
    print("\n📺 방송3사 뉴스 요약:", flush=True)
    print("-" * 80, flush=True)
    
    for i, news in enumerate(processed_news, 1):
        print(f"\n[{i:2d}] {news['press']} - {news['title']}", flush=True)
        if news.get('ai_summary'):
            print(f"    📝 {news['ai_summary']}", flush=True)
        else:
            print(f"    ❌ 요약 없음", flush=True)
    
    print("\n" + "=" * 80, flush=True)
    print("🎉 네이버 뉴스스탠드 iframe 크롤링 완료!", flush=True)

def cleanup_resources():
    """리소스 정리 함수"""
    try:
        import subprocess
        import shutil
        import glob
        
        # Chrome 프로세스 정리
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
        
        # 임시 디렉토리 정리
        temp_dirs = glob.glob('/tmp/chrome_session_*')
        for temp_dir in temp_dirs:
            try:
                shutil.rmtree(temp_dir)
                print(f"🧹 임시 디렉토리 정리: {temp_dir}", flush=True)
            except:
                pass
                
        print("🧹 Chrome 프로세스 및 임시 파일 정리 완료", flush=True)
    except:
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.", flush=True)
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        cleanup_resources()
