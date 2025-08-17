#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
최근 뉴스 크롤러 (오늘/어제 뉴스만 필터링)
XPath를 사용하여 날짜 기반으로 뉴스를 필터링하고 상세 정보를 크롤링
"""

import json
import time
from datetime import datetime, timedelta
import os
import tempfile
import uuid
import random
import subprocess
import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import openai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def setup_chrome_driver():
    """Chrome 드라이버 설정 (Docker 환경 최적화)"""
    
    # 기존 Chrome 프로세스 정리
    try:
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
        time.sleep(1)
        print("🧹 기존 Chrome 프로세스 정리 완료")
    except:
        pass
    
    try:
        chrome_options = Options()
        
        # Docker 환경 필수 옵션
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--window-size=1280,720')
        
        # SSL 및 보안 관련 옵션
        chrome_options.add_argument('--ignore-ssl-errors-on-quic')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--ignore-certificate-errors-spki-list')
        chrome_options.add_argument('--disable-extensions-file-access-check')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        # 세션 충돌 방지 및 안정성 옵션
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
        
        # 고유 세션 생성
        temp_dir = tempfile.mkdtemp(prefix=f'recent_news_chrome_{uuid.uuid4().hex[:8]}_')
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        debug_port = random.randint(9500, 9999)
        chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
        
        # 성능 최적화
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=2048')
        chrome_options.add_argument('--aggressive-cache-discard')
        
        # User Agent 설정 (모바일)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1')
        
        # 자동화 감지 방지
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        print(f"🔧 Chrome 세션 디렉토리: {temp_dir}")
        print(f"🔧 디버깅 포트: {debug_port}")
        
        # Chrome 드라이버 초기화 - Docker 환경에서는 시스템 ChromeDriver 사용
        driver = None
        try:
            # Docker 환경에서는 시스템 ChromeDriver 직접 사용 (아키텍처 호환성 문제 방지)
            driver = webdriver.Chrome(options=chrome_options)
            
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
            
            # 자동화 감지 방지 스크립트
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Chrome 드라이버 초기화 완료")
            return driver
        
    except Exception as e:
        print(f"❌ Chrome 드라이버 설정 실패: {e}")
        return None

def parse_date(date_str):
    """날짜 문자열을 datetime 객체로 변환"""
    try:
        # "2025.08.08" 형태의 날짜 문자열을 처리
        if "." in date_str:
            return datetime.strptime(date_str.strip(), '%Y.%m.%d')
        # 다른 형태의 날짜 처리 가능성 고려
        return None
    except Exception as e:
        print(f"❌ 날짜 파싱 실패: {date_str} - {e}")
        return None

def is_recent_news(date_str, target_dates):
    """뉴스 날짜가 오늘 또는 어제인지 확인"""
    news_date = parse_date(date_str)
    if news_date is None:
        return False
    
    # 날짜만 비교 (시간 제외)
    news_date_only = news_date.date()
    return news_date_only in target_dates

def collect_recent_news_urls(driver, target_dates=None):
    """최근 뉴스 URL 수집"""
    print("🔍 최근 뉴스 URL 수집 시작...")
    
    # 대상 날짜 설정
    if target_dates is None:
        # TEST_DATE 환경변수 확인
        import os
        test_date_env = os.getenv('TEST_DATE')
        if test_date_env:
            try:
                # TEST_DATE 파싱 (형식: 'YYYY-MM-DD')
                test_date = datetime.strptime(test_date_env, '%Y-%m-%d').date()
                yesterday = test_date - timedelta(days=1)
                target_dates = {test_date, yesterday}
                print(f"🎯 TEST_DATE 사용: {test_date.strftime('%Y.%m.%d')} (지정일), {yesterday.strftime('%Y.%m.%d')} (전일)")
            except ValueError:
                print(f"❌ 잘못된 TEST_DATE 형식: {test_date_env}, 현재 날짜 사용")
                # 기본값: 오늘과 어제 날짜
                today = datetime.now().date()
                yesterday = today - timedelta(days=1)
                target_dates = {today, yesterday}
                print(f"🎯 기본 대상 날짜: {today.strftime('%Y.%m.%d')} (오늘), {yesterday.strftime('%Y.%m.%d')} (어제)")
        else:
            # 기본값: 오늘과 어제 날짜
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            target_dates = {today, yesterday}
            print(f"🎯 기본 대상 날짜: {today.strftime('%Y.%m.%d')} (오늘), {yesterday.strftime('%Y.%m.%d')} (어제)")
    else:
        # 사용자 지정 날짜
        date_strings = [date.strftime('%Y.%m.%d') for date in target_dates]
        print(f"🎯 사용자 지정 날짜: {', '.join(date_strings)}")
    
    news_urls = []
    
    # 페이지 구조 확인 및 뉴스 리스트 찾기
    print("📦 페이지 구조 확인 중...")
    
    try:
        # main_con 요소 직접 찾기 (기존 크롤러와 동일하게)
        main_con_xpath = "//*[@id='main_con']/div[1]/div/div[1]/ul"
        print(f"📦 뉴스 리스트 검색: {main_con_xpath}")
        
        # main_con 요소 대기 (더 오래)
        print("🔍 main_con 요소 대기 중...")
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "main_con"))
            )
            print("✅ main_con 발견")
        except Exception as debug_e:
            print(f"❌ main_con 찾기 실패: {debug_e}")
            # 추가 대기 후 재시도
            print("⏰ 추가 대기 후 재시도...")
            time.sleep(10)
            try:
                driver.find_element(By.ID, "main_con")
                print("✅ main_con 재시도 성공")
            except:
                print("❌ main_con 재시도도 실패")
        
        news_list = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, main_con_xpath))
        )
        print("✅ 뉴스 리스트 발견")
        
        # li 요소들 찾기
        li_elements = news_list.find_elements(By.TAG_NAME, "li")
        print(f"📄 li 요소 {len(li_elements)}개 발견")
        
        for li_idx, li_element in enumerate(li_elements, 1):
            try:
                # 날짜 확인 (사용자가 제시한 경로: li[n]/a/table/tbody/tr/td[2]/div[2]/span/text()[2])
                news_date = None
                try:
                    # div[2] 전체 텍스트에서 날짜 찾기
                    date_div_xpath = ".//a/table/tbody/tr/td[2]/div[2]"
                    date_div = li_element.find_element(By.XPATH, date_div_xpath)
                    date_text = date_div.text.strip()
                    
                    # YYYY.MM.DD 패턴 찾기
                    import re
                    date_match = re.search(r'\d{4}\.\d{2}\.\d{2}', date_text)
                    if date_match:
                        news_date = date_match.group()
                except Exception as date_e:
                    print(f"         ❌ 날짜 div 찾기 실패: {date_e}")
                    
                    # span에서 직접 찾기 시도
                    try:
                        date_spans = li_element.find_elements(By.XPATH, ".//a/table/tbody/tr/td[2]/div[2]/span")
                        for span in date_spans:
                            text_content = span.text.strip()
                            if re.match(r'\d{4}\.\d{2}\.\d{2}', text_content):
                                news_date = text_content
                                break
                    except:
                        pass
                
                if not news_date:
                    print(f"     ❌ li[{li_idx}]에서 날짜를 찾을 수 없음")
                    continue
                
                print(f"     📅 li[{li_idx}] 날짜: {news_date}")
                
                # 원하는 날짜인지 확인 (효율성 개선)
                if is_recent_news(news_date, target_dates):
                    print(f"     ✅ 대상 뉴스 발견! 상세 정보 수집 시작...")
                    
                    # 링크 URL 가져오기 (li[n]/a)
                    try:
                        link_element = li_element.find_element(By.XPATH, ".//a")
                        news_url = link_element.get_attribute('href')
                        
                        # 제목 미리보기 가져오기 (li[n]/a/table/tbody/tr/td[2]/div[1])
                        title_preview = ""
                        try:
                            title_element = li_element.find_element(By.XPATH, ".//a/table/tbody/tr/td[2]/div[1]")
                            title_preview = title_element.text.strip()[:50]
                        except:
                            title_preview = "제목 미리보기 없음"
                        
                        if news_url:
                            # 중복 체크
                            duplicate = False
                            for existing in news_urls:
                                if existing['url'] == news_url:
                                    duplicate = True
                                    break
                            
                            if not duplicate:
                                news_urls.append({
                                    'url': news_url,
                                    'date': news_date,
                                    'title_preview': title_preview,
                                    'li_index': li_idx
                                })
                                print(f"         📰 {title_preview}...")
                                print(f"         🔗 {news_url}")
                            else:
                                print(f"         ⚠️ 중복 URL 건너뜀")
                    except Exception as e:
                        print(f"         ❌ 링크 추출 실패: {e}")
                else:
                    print(f"     ⏭️ 대상 외 날짜, 건너뜀: {news_date}")
                    
            except Exception as e:
                print(f"     ❌ li[{li_idx}] 처리 실패: {e}")
                continue
                
    except TimeoutException:
        print("❌ 뉴스 리스트를 찾을 수 없음")
    except Exception as e:
        print(f"❌ 뉴스 리스트 처리 실패: {e}")
    
    print(f"🎯 총 {len(news_urls)}개의 최근 뉴스 URL 수집 완료")
    return news_urls

def extract_article_date_recent(driver):
    """최근 뉴스 크롤러용 기사에서 업로드 날짜 추출 (직접 XPath 사용)"""
    try:
        # 사용자가 제공한 정확한 XPath 사용
        date_xpath = "//*[@id='main_con']/div[1]/div/div[1]/div[1]/div[2]/div[2]"
        
        try:
            date_element = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, date_xpath))
            )
            date_text = date_element.text.strip()
            
            if date_text:
                print(f"    🔍 업로드 날짜 발견: {date_text}")
                return parse_and_format_date_recent(date_text)
            else:
                print("    ⚠️ 날짜 요소는 있지만 텍스트가 없음")
                
        except TimeoutException:
            print(f"    ⚠️ 지정된 XPath에서 날짜 요소를 찾을 수 없음: {date_xpath}")
        except Exception as e:
            print(f"    ❌ 날짜 요소 접근 오류: {e}")
        
        # 백업: 다른 가능한 위치들 빠르게 확인
        backup_selectors = [
            "//*[@id='main_con']/div[1]/div/div[1]/div[2]/div[1]/span",
            "//*[@id='main_con']/div[1]/div/div[1]/div[2]/div[1]",
            "//*[@id='main_con']/div[1]/div/div[1]/div[2]/span"
        ]
        
        for selector in backup_selectors:
            try:
                elem = driver.find_element(By.XPATH, selector)
                text = elem.text.strip()
                if text and (re.search(r'\d{4}', text) or '시간 전' in text or '분 전' in text):
                    print(f"    🔍 백업으로 날짜 발견: {selector} -> {text}")
                    return parse_and_format_date_recent(text)
            except:
                continue
        
        print("    ⚠️ 모든 시도에서 날짜를 찾을 수 없음")
        return None
        
    except Exception as e:
        print(f"    ❌ 날짜 추출 오류: {e}")
        return None

def parse_and_format_date_recent(date_text):
    """다양한 날짜 형식을 파싱하여 YYYY.MM.DD hh:mm 형태로 변환"""
    try:
        current_time = datetime.now()
        
        print(f"    🔍 날짜 파싱 시도: '{date_text}'")
        
        # "입력"과 "수정" 날짜가 함께 있는 경우 처리
        if '입력' in date_text:
            # "입력 2025-08-12 09:34 수정 2025.08.12 09:34" 에서 입력 날짜만 추출
            input_match = re.search(r'입력[^\d]*(\d{4}[-.\s]\d{1,2}[-.\s]\d{1,2}[^\d]*\d{1,2}:\d{2})', date_text)
            if input_match:
                input_date = input_match.group(1).strip()
                print(f"    ✅ 입력 날짜 추출: '{input_date}'")
                # 하이픈을 점으로 변환하고 공백 제거
                input_date = re.sub(r'[-\s]', '.', input_date)
                input_date = re.sub(r'\.+', '.', input_date)  # 연속된 점 제거
                # 재귀 호출 방지를 위해 직접 처리
                try:
                    dt = parser.parse(input_date, fuzzy=True)
                    return dt.strftime("%Y.%m.%d %H:%M")
                except:
                    # 수동 파싱
                    parts = input_date.split()
                    if len(parts) >= 2:
                        date_part = parts[0].replace('.', '-')
                        time_part = parts[1]
                        try:
                            dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
                            return dt.strftime("%Y.%m.%d %H:%M")
                        except:
                            pass
                    return current_time.strftime("%Y.%m.%d %H:%M")
            
            # 시간이 없는 경우: "입력 2025-08-12"
            input_match_no_time = re.search(r'입력[^\d]*(\d{4}[-.\s]\d{1,2}[-.\s]\d{1,2})', date_text)
            if input_match_no_time:
                input_date = input_match_no_time.group(1).strip() + " 00:00"
                print(f"    ✅ 입력 날짜 추출 (시간 없음): '{input_date}'")
                input_date = re.sub(r'[-\s]', '.', input_date)
                # 재귀 호출 방지를 위해 직접 처리
                try:
                    dt = parser.parse(input_date, fuzzy=True)
                    return dt.strftime("%Y.%m.%d %H:%M")
                except:
                    return current_time.strftime("%Y.%m.%d %H:%M")
        
        # "작성"이 있는 경우 처리 (SBS와 유사한 패턴)
        elif '작성' in date_text:
            created_match = re.search(r'작성[^\d]*(\d{4}[-.\s]\d{1,2}[-.\s]\d{1,2}[^\d]*\d{1,2}:\d{2})', date_text)
            if created_match:
                created_date = created_match.group(1).strip()
                print(f"    ✅ 작성 날짜 추출: '{created_date}'")
                created_date = re.sub(r'[-\s]', '.', created_date)
                created_date = re.sub(r'\.+', '.', created_date)
                # 재귀 호출 방지를 위해 직접 처리
                try:
                    dt = parser.parse(created_date, fuzzy=True)
                    return dt.strftime("%Y.%m.%d %H:%M")
                except:
                    return current_time.strftime("%Y.%m.%d %H:%M")
        
        # 상대적 시간 표현 처리
        elif '시간 전' in date_text:
            hours_ago = int(re.search(r'(\d+)시간', date_text).group(1))
            target_time = current_time - timedelta(hours=hours_ago)
            return target_time.strftime("%Y.%m.%d %H:%M")
        
        elif '분 전' in date_text:
            minutes_ago = int(re.search(r'(\d+)분', date_text).group(1))
            target_time = current_time - timedelta(minutes=minutes_ago)
            return target_time.strftime("%Y.%m.%d %H:%M")
        
        elif '일 전' in date_text:
            days_ago = int(re.search(r'(\d+)일', date_text).group(1))
            target_time = current_time - timedelta(days=days_ago)
            return target_time.strftime("%Y.%m.%d %H:%M")
        
        # 하이픈 형식 날짜 처리: "2025-08-12 09:34" 등
        elif re.search(r'\d{4}-\d{1,2}-\d{1,2}', date_text):
            try:
                # 시간이 있는 경우: "2025-08-12 09:34"
                datetime_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})', date_text)
                if datetime_match:
                    year, month, day, hour, minute = datetime_match.groups()
                    result = f"{year}.{month.zfill(2)}.{day.zfill(2)} {hour.zfill(2)}:{minute}"
                    print(f"    ✅ 하이픈 형식 날짜 파싱: '{result}'")
                    return result
                
                # 날짜만 있는 경우: "2025-08-12"
                date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_text)
                if date_match:
                    year, month, day = date_match.groups()
                    result = f"{year}.{month.zfill(2)}.{day.zfill(2)} 00:00"
                    print(f"    ✅ 하이픈 형식 날짜 파싱 (시간 없음): '{result}'")
                    return result
                    
            except Exception as e:
                print(f"    ❌ 하이픈 형식 파싱 오류: {e}")
        
        # 약업닷컴 특수 형식: "2024. 1. 15. 14:30"
        elif re.match(r'\d{4}\. \d{1,2}\. \d{1,2}\. \d{1,2}:\d{2}', date_text):
            # "2024. 1. 15. 14:30" -> "2024.01.15 14:30"
            parts = date_text.split('. ')
            if len(parts) >= 4:
                year = parts[0]
                month = parts[1].zfill(2)
                day = parts[2].zfill(2)
                time_part = parts[3] if ':' in parts[3] else "00:00"
                return f"{year}.{month}.{day} {time_part}"
        
        # 한국어 날짜 형식 처리
        elif '년' in date_text and '월' in date_text and '일' in date_text:
            date_match = re.search(r'(\d{4})년 (\d{1,2})월 (\d{1,2})일\s*(\d{1,2}):(\d{2})', date_text)
            if date_match:
                year, month, day, hour, minute = date_match.groups()
                return f"{year}.{month.zfill(2)}.{day.zfill(2)} {hour.zfill(2)}:{minute}"
        
        # 일반적인 날짜 형식들 시도
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y.%m.%d %H:%M',
            '%Y/%m/%d %H:%M',
            '%Y-%m-%d',
            '%Y.%m.%d',
            '%Y/%m/%d'
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_text.strip(), fmt)
                return dt.strftime("%Y.%m.%d %H:%M")
            except ValueError:
                continue
        
        # dateutil.parser 사용 (마지막 시도)
        try:
            dt = parser.parse(date_text, fuzzy=True)
            return dt.strftime("%Y.%m.%d %H:%M")
        except:
            pass
        
        # 파싱 실패 시 현재 시간 반환
        print(f"    ⚠️ 날짜 파싱 실패, 현재 시간 사용: '{date_text}'")
        return current_time.strftime("%Y.%m.%d %H:%M")
        
    except Exception as e:
        print(f"    ❌ 날짜 파싱 오류: {e}")
        return datetime.now().strftime("%Y.%m.%d %H:%M")

def crawl_news_detail(driver, news_item, rank):
    """개별 뉴스 상세 정보 크롤링"""
    news_url = news_item['url']
    print(f"📰 [{rank}] 뉴스 상세 정보 크롤링 중...")
    print(f"   📅 날짜: {news_item['date']}")
    print(f"   🌐 URL: {news_url}")
    
    try:
        # 해당 URL로 이동
        driver.get(news_url)
        time.sleep(2)
        
        news_info = {
            'rank': rank,
            'title': '',
            'content': '',
            'summary': '',  # AI 요약 추가
            'url': news_url,
            'date': news_item['date'],
            'pub_time': None,  # 업로드 날짜/시간
            'li_index': news_item['li_index'],
            'title_preview': news_item['title_preview'],
            'type': 'medical news'
        }
        
        # 업로드 날짜 추출
        print("   📅 업로드 날짜 추출 중...")
        pub_time = extract_article_date_recent(driver)
        if pub_time:
            news_info['pub_time'] = pub_time
            print(f"   ✅ 업로드 날짜: {pub_time}")
        else:
            news_info['pub_time'] = datetime.now().strftime("%Y.%m.%d %H:%M")
            print("   ⚠️ 날짜 추출 실패, 현재 시간 사용")
        
        # 제목 추출 (기존 크롤러와 동일)
        try:
            title_xpath = "//*[@id='main_con']/div[1]/div/div[1]/div[1]"
            title_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, title_xpath))
            )
            news_info['title'] = title_element.text.strip()
            print(f"   ✅ 제목: {news_info['title']}")
        except Exception as e:
            print(f"   ❌ 제목 추출 실패: {e}")
            news_info['title'] = "제목 추출 실패"
        
        # 내용 추출 (사용자 요청에 따른 XPath)
        try:
            content_xpath = "//*[@id='main_con']/div[1]/div/div[1]/div[2]/div[2]"
            content_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, content_xpath))
            )
            news_info['content'] = content_element.text.strip()
            print(f"   ✅ 내용: {len(news_info['content'])}자 추출")
        except Exception as e:
            print(f"   ❌ 내용 추출 실패: {e}")
            news_info['content'] = "내용 추출 실패"
        
        # AI 요약 생성
        if news_info['content'] and news_info['content'] != "내용 추출 실패":
            print("   🤖 AI 요약 생성 중...")
            summary = summarize_with_gpt4o(news_info['title'], news_info['content'])
            if summary:
                news_info['summary'] = summary
                print(f"   ✅ AI 요약: {summary[:50]}...")
            else:
                news_info['summary'] = "요약 생성 실패"
                print("   ❌ AI 요약 생성 실패")
        else:
            news_info['summary'] = "본문 내용 부족"
            print("   ❌ 본문 내용이 부족하여 요약 불가")
        
        return news_info
        
    except Exception as e:
        print(f"   ❌ 뉴스 [{rank}] 상세 정보 크롤링 실패: {e}")
        return None

def should_filter_by_time_recent():
    """현재 시간에 따른 뉴스 필터링 여부 결정"""
    current_hour = datetime.now().hour
    
    if current_hour >= 13:
        print(f"⏰ 현재 시각: {current_hour}시 - 09시 이후 뉴스만 크롤링합니다.")
        return True
    else:
        print(f"⏰ 현재 시각: {current_hour}시 - 모든 뉴스를 크롤링합니다.")
        return False

def is_news_time_valid_recent(news_pub_time, filter_enabled):
    """뉴스 발행 시간이 필터링 조건에 맞는지 확인"""
    if not filter_enabled or not news_pub_time:
        return True
    
    try:
        # YYYY.MM.DD hh:mm 형식 파싱
        news_datetime = datetime.strptime(news_pub_time, "%Y.%m.%d %H:%M")
        today = datetime.now().date()
        
        # 오늘 날짜인 경우만 시간 필터 적용
        if news_datetime.date() == today:
            if news_datetime.hour >= 9:
                print(f"    ✅ 시간 필터 통과: {news_pub_time} (09시 이후)")
                return True
            else:
                print(f"    ❌ 시간 필터 제외: {news_pub_time} (09시 이전)")
                return False
        else:
            # 오늘이 아닌 날짜는 모두 포함
            print(f"    ✅ 날짜 필터 통과: {news_pub_time} (오늘이 아닌 날짜)")
            return True
            
    except Exception as e:
        print(f"    ⚠️ 날짜 파싱 오류, 뉴스 포함: {news_pub_time} - {e}")
        return True

def summarize_with_gpt4o(title, content):
    """GPT-4o를 사용한 기사 요약"""
    try:
        # OpenAI API 키 확인
        if not os.getenv('OPENAI_API_KEY'):
            print("    ⚠️ OpenAI API 키가 설정되지 않음")
            return None
        
        if not content or len(content.strip()) < 50 or "추출 실패" in content:
            return "본문 내용이 부족합니다."
        
        # 내용이 너무 길면 자르기 (GPT-4o는 더 긴 텍스트 처리 가능)
        if len(content) > 8000:
            content = content[:8000] + "..."
        
        # OpenAI 클라이언트 초기화
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # 프롬프트 생성 (한국어 의료/제약 뉴스에 특화)
        prompt = f"""다음 의료/제약 관련 뉴스 기사를 3-4문장으로 간결하고 정확하게 요약해주세요.

제목: {title}

내용: {content}

요약 시 다음 사항을 고려해주세요:
1. 핵심 내용과 주요 수치를 포함하세요
2. 의료진, 환자, 제약업계에 미치는 영향을 언급하세요
3. 객관적이고 중립적인 어조로 작성하세요

요약:"""
        
        # OpenAI API 호출
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        print(f"    ❌ GPT-4o 요약 오류: {e}")
        return None

def crawl_recent_news(base_url=None, target_dates=None):
    """최근 뉴스 크롤링 메인 함수"""
    if base_url is None:
        base_url = "http://m.yakup.com/news/index.html?cat=11"  
    
    print("=" * 80)
    if target_dates is None:
        print("📰 최근 뉴스 크롤러 (오늘/어제 뉴스)")
    else:
        date_strings = [date.strftime('%Y.%m.%d') for date in target_dates]
        print(f"📰 최근 뉴스 크롤러 ({', '.join(date_strings)})")
    print("=" * 80)
    print(f"🌐 접속 URL: {base_url}")
    
    driver = None
    news_data = []
    
    try:
        # Chrome 드라이버 설정
        driver = setup_chrome_driver()
        if not driver:
            raise Exception("Chrome 드라이버 설정 실패")
        
        print("📱 메인 페이지 로딩 중...")
        driver.get(base_url)
        
        # 기본 페이지 로딩 대기
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("✅ 메인 페이지 로드 완료")
        
        # 동적 콘텐츠 로딩 대기 (더 긴 시간)
        print("⏰ 동적 콘텐츠 로딩 대기 중...")
        time.sleep(8)
        
        # 1단계: 최근 뉴스 URL 수집 (날짜 필터링)
        recent_news = collect_recent_news_urls(driver, target_dates)
        
        if not recent_news:
            print("⚠️ 수집된 최근 뉴스 URL이 없습니다")
            return {
                'base_url': base_url,
                'status': '성공',
                'error': None,
                'news_count': 0,
                'news_list': [],
                'crawling_time': datetime.now().isoformat()
            }
        
        # 2단계: 각 뉴스 상세 정보 크롤링
        print(f"\n📊 {len(recent_news)}개 최근 뉴스의 상세 정보 크롤링 시작...")
        
        i = 1
        while i <= len(recent_news):
            news_item = recent_news[i-1]
            
            # 10개마다 또는 첫 시작 시 ChromeDriver 세션 초기화
            if (i-1) % 10 == 0:
                print(f"   🔄 ChromeDriver 세션 초기화 ({i}번째 뉴스)")
                
                # 기존 드라이버 정리
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                
                # 새 드라이버 생성
                driver = setup_chrome_driver()
                if not driver:
                    print(f"   ❌ ChromeDriver 초기화 실패 - 크롤링 중단")
                    break
                print("   ✅ ChromeDriver 초기화 완료")
            
            # 개별 뉴스 크롤링 시도 (재시도 메커니즘 포함)
            max_attempts = 5
            success = False
            
            for attempt in range(1, max_attempts + 1):
                try:
                    print(f"📰 [{i}] 뉴스 상세 정보 크롤링 시도 {attempt}/{max_attempts}...")
                    
                    # 세션 상태 확인
                    try:
                        driver.current_url  # 세션 확인
                    except Exception as session_error:
                        print(f"   ⚠️ ChromeDriver 세션 문제 감지: {session_error}")
                        
                        # 세션 재생성
                        try:
                            driver.quit()
                        except:
                            pass
                        
                        driver = setup_chrome_driver()
                        if not driver:
                            print(f"   ❌ ChromeDriver 재생성 실패")
                            raise Exception("ChromeDriver 재생성 실패")
                        print("   ✅ ChromeDriver 재생성 완료")
                    
                    # 뉴스 상세 정보 크롤링
                    news_info = crawl_news_detail(driver, news_item, i)
                    
                    if news_info and news_info['title'] != "제목 추출 실패":
                        news_data.append(news_info)
                        print(f"   ✅ 뉴스 [{i}] 수집 완료")
                        success = True
                        break
                    else:
                        raise Exception("뉴스 정보 추출 실패")
                        
                except Exception as e:
                    print(f"   ❌ 뉴스 [{i}] 시도 {attempt} 실패: {e}")
                    
                    if attempt < max_attempts:
                        wait_time = attempt * 2
                        print(f"   ⏰ {wait_time}초 후 재시도...")
                        time.sleep(wait_time)
                    else:
                        print(f"   💥 뉴스 [{i}] 최종 실패 - 다음 뉴스로 진행")
            
            if not success:
                print(f"   ⚠️ 뉴스 [{i}] 수집 실패 - 다음으로 이동")
            
            # 다음 뉴스로 이동
            i += 1
            
            # 요청 간격 조정
            if i <= len(recent_news):
                time.sleep(1)
        
        print(f"\n🎉 크롤링 완료: {len(news_data)}개 최근 뉴스 수집")
        
        # 시간 기반 필터링 적용
        time_filter_enabled = should_filter_by_time_recent()
        filtered_news_data = []
        filtered_count = 0
        
        if time_filter_enabled:
            print(f"\n🔍 시간 기반 필터링 적용 중...")
            for news in news_data:
                if is_news_time_valid_recent(news.get('pub_time'), time_filter_enabled):
                    filtered_news_data.append(news)
                else:
                    filtered_count += 1
            
            print(f"🕘 시간 필터로 제외된 뉴스: {filtered_count}개")
            print(f"✅ 최종 처리된 뉴스: {len(filtered_news_data)}개")
            final_news_data = filtered_news_data
        else:
            final_news_data = news_data
        
        return {
            'base_url': base_url,
            'status': '성공',
            'error': None,
            'news_count': len(final_news_data),
            'filtered_count': filtered_count,
            'news_list': final_news_data,
            'crawling_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")
        return {
            'base_url': base_url,
            'status': '실패',
            'error': str(e),
            'news_count': 0,
            'news_list': [],
            'crawling_time': datetime.now().isoformat()
        }
        
    finally:
        if driver:
            try:
                driver.quit()
                print("🔚 브라우저 종료")
            except:
                pass
            
            # 임시 디렉토리 정리
            if hasattr(driver, '_temp_dir'):
                try:
                    import shutil
                    shutil.rmtree(driver._temp_dir)
                    print(f"🧹 임시 디렉토리 정리: {driver._temp_dir}")
                except:
                    pass

def save_to_json(data, filename=None):
    """JSON 파일로 저장"""
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        today = datetime.now().strftime('%Y%m%d')
        filename = f'medical_recent_news_{today}_{timestamp}.json'
    
    # crawler_result 디렉토리에 저장 - Docker 볼륨 마운트된 경로 사용
    result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
    
    os.makedirs(result_dir, exist_ok=True)
    filepath = os.path.join(result_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 데이터 저장 완료: {filepath}")
    return filepath

def main_with_retry(base_url=None, target_dates=None, max_retries=5):
    """재시도 메커니즘이 포함된 메인 실행 함수"""
    
    # 기본 URL 설정
    if base_url is None:
        base_url = "http://m.yakup.com/news/index.html?cat=11"
    
    # 기본 날짜 설정
    if target_dates is None:
        # TEST_DATE 환경변수 확인
        import os
        test_date_env = os.getenv('TEST_DATE')
        if test_date_env:
            try:
                # TEST_DATE 파싱 (형식: 'YYYY-MM-DD')
                test_date = datetime.strptime(test_date_env, '%Y-%m-%d').date()
                yesterday = test_date - timedelta(days=1)
                target_dates = {test_date, yesterday}
                print(f"📅 TEST_DATE 기본 날짜 설정: {test_date.strftime('%Y.%m.%d')} (지정일), {yesterday.strftime('%Y.%m.%d')} (전일)")
            except ValueError:
                print(f"❌ 잘못된 TEST_DATE 형식: {test_date_env}, 현재 날짜 사용")
                today = datetime.now().date()
                yesterday = today - timedelta(days=1)
                target_dates = {today, yesterday}
                print(f"📅 기본 날짜 설정: {today.strftime('%Y.%m.%d')} (오늘), {yesterday.strftime('%Y.%m.%d')} (어제)")
        else:
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            target_dates = {today, yesterday}
            print(f"📅 기본 날짜 설정: {today.strftime('%Y.%m.%d')} (오늘), {yesterday.strftime('%Y.%m.%d')} (어제)")
    
    result = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"\n🔄 크롤링 시도 {attempt}/{max_retries}")
            
            # Chrome 프로세스 정리 (재시도 전)
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
                time.sleep(2)  # 프로세스 정리 대기
                print("🧹 이전 Chrome 프로세스 정리 완료")
            except:
                pass
            
            # 크롤링 실행
            result = crawl_recent_news(base_url, target_dates)
            
            # 성공 여부 확인
            if result['status'] == '성공' and result['news_count'] > 0:
                print(f"✅ 크롤링 성공! ({attempt}/{max_retries})")
                break
            else:
                raise Exception(f"크롤링 결과 불량: {result.get('error', '뉴스 수집 실패')}")
                
        except KeyboardInterrupt:
            print("\n⚠️ 사용자에 의해 중단되었습니다.")
            return
        except Exception as e:
            print(f"❌ 시도 {attempt} 실패: {e}")
            
            # 마지막 시도가 아니면 재시도 안내
            if attempt < max_retries:
                wait_time = attempt * 5  # 재시도 간격을 점진적으로 증가
                print(f"⏰ {wait_time}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                print(f"💥 모든 시도 실패. 최대 재시도 횟수({max_retries}) 도달")
                # 마지막 실패 시에도 결과 객체 생성
                if result is None:
                    result = {
                        'base_url': base_url,
                        'status': '실패',
                        'error': str(e),
                        'news_count': 0,
                        'news_list': [],
                        'crawling_time': datetime.now().isoformat()
                    }
        finally:
            # Chrome 프로세스 정리
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
            except:
                pass
    
    if result:
        # 결과 저장
        filepath = save_to_json(result)
        
        # 결과 출력
        print("\n" + "=" * 80)
        print("📊 크롤링 결과 요약")
        print("=" * 80)
        print(f"🌐 URL: {result['base_url']}")
        print(f"📈 상태: {result['status']}")
        print(f"📰 수집된 뉴스: {result['news_count']}개")
        
        if result['error']:
            print(f"❌ 오류: {result['error']}")
        
        if result['news_list']:
            print("\n📋 수집된 최근 뉴스 목록:")
            print("-" * 80)
            for news in result['news_list']:
                print(f"[{news['rank']:2d}] {news['title']}")
                print(f"     📅 날짜: {news['date']}")
                if news['url']:
                    print(f"     🔗 {news['url']}")
                if news['summary'] and news['summary'] not in ["", "본문 내용 부족", "요약 생성 실패"]:
                    print(f"     📝 요약: {news['summary']}")
                else:
                    # 요약이 없으면 원본 내용의 일부 표시
                    if news['content'] and news['content'] != "내용 추출 실패":
                        content_preview = news['content'][:100] + "..." if len(news['content']) > 100 else news['content']
                        print(f"     📝 원문: {content_preview}")
                print()
        
        print(f"💾 결과 파일: {filepath}")
        if result['status'] == '성공':
            print("🎉 크롤링 완료!")
        else:
            print("💥 크롤링 최종 실패!")

def main(base_url=None, target_dates=None):
    """메인 실행 함수 (하위 호환성 유지)"""
    main_with_retry(base_url, target_dates, max_retries=5)

if __name__ == "__main__":
    
    # 날짜 설정 (TEST_DATE 환경변수 우선)
    base_url = "http://m.yakup.com/news/index.html?cat=11"
    
    # TEST_DATE 환경변수 확인
    import os
    test_date_env = os.getenv('TEST_DATE')
    if test_date_env:
        try:
            # TEST_DATE 파싱 (형식: 'YYYY-MM-DD')
            target_date = datetime.strptime(test_date_env, '%Y-%m-%d').date()
            yesterday = target_date - timedelta(days=1)
            target_dates = {target_date, yesterday}
            print(f"📅 TEST_DATE로 크롤링: {target_date.strftime('%Y.%m.%d')} (지정일), {yesterday.strftime('%Y.%m.%d')} (전일)")
        except ValueError:
            print(f"❌ 잘못된 TEST_DATE 형식: {test_date_env}, 현재 날짜 사용")
            target_date = datetime.now().date()  # 오늘 날짜
            yesterday = target_date - timedelta(days=1)  # 어제 날짜 자동 계산
            target_dates = {target_date, yesterday}
    else:
        # 오늘 날짜로 크롤링 (자동으로 어제 날짜도 포함)
        target_date = datetime.now().date()  # 오늘 날짜
        yesterday = target_date - timedelta(days=1)  # 어제 날짜 자동 계산
        target_dates = {target_date, yesterday}
    
    print(f"🎯 크롤링 URL: {base_url}")
    print(f"🎯 크롤링 날짜: {target_date.strftime('%Y.%m.%d')} (오늘), {yesterday.strftime('%Y.%m.%d')} (어제)")
    
    main(base_url, target_dates)