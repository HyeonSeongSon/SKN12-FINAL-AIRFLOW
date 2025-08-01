#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 뉴스스탠드 iframe 기반 KBS/MBC/SBS 뉴스 크롤러
우분투 환경 대응
"""

import requests
import os
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

# .env 파일 로드
load_dotenv()

def setup_chrome_driver_ubuntu():
    """우분투 환경에 최적화된 Chrome 드라이버 설정"""
    
    # 기존 Chrome 프로세스 정리
    try:
        import subprocess
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
        time.sleep(2)
        print("🧹 기존 Chrome/ChromeDriver 프로세스 정리 완료")
    except:
        pass
    
    try:
        chrome_options = Options()
        
        # 우분투 환경 최적화 옵션 (충돌 방지 중심)
        # chrome_options.add_argument('--headless')  # GUI 보기 위해 주석처리
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
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        print(f"🔧 임시 세션 디렉토리: {temp_dir}")
        print(f"🔧 디버깅 포트: {debug_port}")
        
        # Chrome 드라이버 초기화 시도
        driver = None
        try:
            # ChromeDriverManager 사용 시도
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ ChromeDriverManager로 드라이버 생성 성공")
            
        except Exception as e:
            print(f"❌ ChromeDriverManager 실패: {e}")
            
            # 시스템 chromedriver 사용 시도
            try:
                driver = webdriver.Chrome(options=chrome_options)
                print("✅ 시스템 chromedriver 사용 성공")
            except Exception as e2:
                print(f"❌ 시스템 chromedriver 실패: {e2}")
                
                # 마지막 시도: headless 모드로
                try:
                    chrome_options.add_argument('--headless')
                    driver = webdriver.Chrome(options=chrome_options)
                    print("✅ Headless 모드로 드라이버 생성 성공")
                except Exception as e3:
                    print(f"❌ Headless 모드도 실패: {e3}")
                    return None
        
        if driver:
            # 타임아웃 및 기본 설정
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)
            
            # 세션 정보 저장 (정리용)
            driver._temp_dir = temp_dir
            driver._debug_port = debug_port
            
            print("✅ Chrome 드라이버 설정 완료")
            return driver
        else:
            return None
                
    except Exception as e:
        print(f"❌ Chrome 드라이버 설정 중 전체 오류: {e}")
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
                print(f"🔍 감지된 alt 텍스트: '{alt_text}'")
                
                # 대상 언론사인지 정확히 확인 (부분 문자열이 아닌 정확한 매칭)
                for press in target_presses:
                    if press == 'KBS':
                        # KBS는 정확히 'KBS'만 매칭 (KBS World 제외)
                        if alt_text == 'KBS' or alt_text.startswith('KBS ') or alt_text.endswith(' KBS') or ' KBS ' in alt_text:
                            # KBS World는 제외
                            if 'World' not in alt_text and 'world' not in alt_text:
                                print(f"🎯 현재 언론사: KBS 감지됨 (alt: '{alt_text}')")
                                return 'KBS'
                    else:
                        # MBC, SBS는 기존 방식대로
                        if press in alt_text:
                            print(f"🎯 현재 언론사: {press} 감지됨 (alt: '{alt_text}')")
                            return press
                
                print(f"❌ 대상 언론사가 아님: {alt_text}")
                return None
            else:
                print("❌ 언론사 이미지가 표시되지 않음")
                return None
                
        except NoSuchElementException:
            print(f"❌ 지정된 xpath에서 이미지를 찾을 수 없음: {press_img_xpath}")
            
            # 대체 방법: 일반적인 alt 속성 검색
            print("🔄 대체 방법으로 언론사 검색 중...")
            for press in target_presses:
                try:
                    if press == 'KBS':
                        # KBS는 정확한 매칭으로 검색
                        press_img = driver.find_element(By.XPATH, f"//img[@alt='KBS']")
                        if press_img.is_displayed():
                            print(f"🎯 대체 방법으로 KBS 감지됨")
                            return 'KBS'
                    else:
                        # MBC, SBS는 기존 방식
                        press_img = driver.find_element(By.XPATH, f"//img[@alt='{press}']")
                        if press_img.is_displayed():
                            print(f"🎯 대체 방법으로 {press} 감지됨")
                            return press
                except NoSuchElementException:
                    continue
            
            print("❌ 대체 방법으로도 언론사를 찾을 수 없음")
            return None
        
    except Exception as e:
        print(f"❌ 언론사 감지 중 오류: {e}")
        
        # 현재 페이지 상태 디버깅 정보 출력
        try:
            print(f"📄 현재 URL: {driver.current_url}")
            print(f"📄 페이지 제목: {driver.title}")
            
            # 페이지에 있는 모든 img 태그의 alt 속성 확인
            all_imgs = driver.find_elements(By.TAG_NAME, "img")
            print(f"📷 페이지 내 총 이미지 수: {len(all_imgs)}")
            
            for i, img in enumerate(all_imgs[:10]):  # 처음 10개만 확인
                try:
                    alt = img.get_attribute('alt')
                    src = img.get_attribute('src')
                    if alt:
                        print(f"  [{i+1}] alt='{alt}', src='{src[:50]}...'")
                except:
                    continue
                    
        except Exception as debug_e:
            print(f"❌ 디버깅 정보 출력 실패: {debug_e}")
        
        return None

def extract_news_from_iframe(driver, press_name):
    """iframe 내부에서 뉴스 추출"""
    try:
        print(f"📰 {press_name} iframe에서 뉴스 추출 중...")
        
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
                print(f"✅ {press_name} iframe 전환 완료 (선택자: {selector})")
                iframe_found = True
                break
                
            except TimeoutException:
                continue
            except Exception as e:
                print(f"❌ iframe 선택자 '{selector}' 오류: {e}")
                continue
        
        if not iframe_found:
            print(f"❌ {press_name} iframe을 찾을 수 없음")
            return []
            
        # iframe 내부 페이지 로딩 대기
        time.sleep(3)
        
        # iframe 내부 페이지 상태 확인
        try:
            current_url = driver.current_url
            page_source_length = len(driver.page_source)
            print(f"📄 iframe 내부 URL: {current_url}")
            print(f"📄 iframe 페이지 소스 길이: {page_source_length}")
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
                print(f"  🔍 [{selector_index + 1}/{len(news_selectors)}] '{selector}' 선택자 검색 중...")
                
                news_links = driver.find_elements(By.XPATH, selector)
                
                if not news_links:
                    print(f"    ❌ 뉴스 링크 없음")
                    continue
                
                print(f"    ✅ {len(news_links)}개 링크 발견")
                
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
                        print(f"      [{len(headlines)}] {title[:50]}...")
                            
                    except Exception as e:
                        continue
                    
            except Exception as e:
                print(f"    ❌ '{selector}' 선택자 오류: {e}")
                continue
        
        # iframe에서 벗어나기
        driver.switch_to.default_content()
        print(f"✅ {press_name}에서 {len(headlines)}개 뉴스 수집 완료")
        
        return headlines
        
    except Exception as e:
        print(f"❌ {press_name} iframe 뉴스 추출 오류: {e}")
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
            print(f"🔄 다음 버튼 클릭 시도 {retry + 1}/{max_retries}")
            
            # 여러 xpath 시도
            next_button = None
            for xpath in next_button_xpaths:
                try:
                    next_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    print(f"✅ 버튼 발견: {xpath}")
                    break
                except:
                    continue
            
            if next_button is None:
                print(f"❌ {retry + 1}번째 시도: 다음 버튼을 찾을 수 없음")
                continue
            
            # 버튼 클릭 시도 (두 가지 방법)
            try:
                # 방법 1: JavaScript 클릭
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(2)  # 페이지 전환 대기 (2초)
                print("✅ JavaScript로 버튼 클릭 성공")
                return True
            except Exception as e1:
                print(f"❌ JavaScript 클릭 실패: {e1}")
                try:
                    # 방법 2: 일반 클릭
                    next_button.click()
                    time.sleep(2)  # 페이지 전환 대기 (2초)
                    print("✅ 일반 클릭 성공")
                    return True
                except Exception as e2:
                    print(f"❌ 일반 클릭도 실패: {e2}")
                    continue
                    
        except Exception as e:
            print(f"❌ {retry + 1}번째 시도 전체 실패: {e}")
            if retry < max_retries - 1:
                print("🔄 페이지 새로고침 후 재시도...")
                try:
                    driver.refresh()
                    time.sleep(3)
                except:
                    pass
            continue
    
    print(f"❌ {max_retries}번 시도 후 버튼 클릭 최종 실패")
    return False

def crawl_newsstand_with_iframe(driver):
    """iframe 기반 뉴스스탠드 크롤링 메인 함수"""
    try:
        print("📰 네이버 뉴스스탠드 접속 중...")
        
        # 페이지 접속 전 대기
        time.sleep(2)
        
        # 뉴스스탠드 페이지 접속
        driver.get("https://newsstand.naver.com/")
        
        # 페이지 로딩 대기 (더 안정적으로)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            print("✅ 페이지 로딩 완료")
        except TimeoutException:
            print("❌ 페이지 로딩 타임아웃")
            return []
        
        # 추가 로딩 대기
        time.sleep(5)
        
        # 현재 페이지 상태 확인
        print(f"📄 현재 페이지 제목: {driver.title}")
        print(f"📄 현재 URL: {driver.current_url}")
        
        all_headlines = []
        found_presses = []  # KBS/MBC/SBS 수집 완료된 언론사
        all_seen_presses = []  # 모든 본 언론사 기록 (중복 감지용)
        max_attempts = 100  # 최대 100번 시도 (주요 언론사 52개 + 여유분)
        
        for attempt in range(max_attempts):
            print(f"\n🔄 {attempt + 1}번째 시도...")
            
            # 현재 언론사 감지
            current_press = detect_current_press(driver)
            
            if current_press:
                # 이미 본 언론사인지 확인 (한 바퀴 완료 판단)
                if current_press in all_seen_presses:
                    print(f"🔄 이미 확인한 언론사({current_press})가 다시 나타남 - 한 바퀴 완료!")
                    print(f"📋 총 {len(all_seen_presses)}개 언론사를 확인했습니다: {all_seen_presses}")
                    break
                else:
                    # 새로운 언론사 기록
                    all_seen_presses.append(current_press)
                    print(f"📋 새로운 언론사 발견: {current_press} (총 {len(all_seen_presses)}개 확인)")
                    print(f"📋 확인한 모든 언론사: {all_seen_presses}")
            
                # KBS/MBC/SBS 중 하나이고 아직 수집하지 않았다면 뉴스 수집
                target_presses = ['KBS', 'MBC', 'SBS']
                if current_press in target_presses and current_press not in found_presses:
                    print(f"🎯 대상 언론사 발견: {current_press}")
                    
                    # iframe에서 뉴스 추출
                    news_from_iframe = extract_news_from_iframe(driver, current_press)
                    
                    if news_from_iframe:
                        all_headlines.extend(news_from_iframe)
                        found_presses.append(current_press)
                        print(f"✅ {current_press} 뉴스 {len(news_from_iframe)}개 수집 완료")
                    
                    # 3개 언론사 모두 찾았으면 종료
                    if len(found_presses) >= 3:
                        print("🎉 KBS, MBC, SBS 모두 찾았습니다!")
                        break
                elif current_press in target_presses:
                    print(f"⏭️ {current_press}는 이미 수집했습니다.")
                else:
                    print(f"⏭️ {current_press}는 대상 언론사가 아닙니다.")
            else:
                print("⏭️ 언론사를 감지할 수 없습니다.")
            
            # 다음 버튼 클릭 (재시도 포함)
            click_success = click_next_button(driver, max_retries=3)
            if not click_success:
                print("⚠️ 다음 버튼 클릭 실패, 하지만 탐색 계속...")
                # 버튼 클릭에 실패해도 탐색을 계속하기 위해 짧은 대기 후 진행
                time.sleep(2)
                # 페이지 새로고침으로 복구 시도
                try:
                    print("🔄 페이지 새로고침으로 복구 시도...")
                    driver.refresh()
                    time.sleep(3)
                except Exception as refresh_e:
                    print(f"❌ 페이지 새로고침 실패: {refresh_e}")
                    # 그래도 계속 시도
                    pass
        
        print(f"\n📊 최종 수집 결과:")
        print(f"   시도 횟수: {attempt + 1}/{max_attempts}")
        print(f"   확인한 모든 언론사: {all_seen_presses}")
        print(f"   수집 완료된 언론사: {found_presses}")
        print(f"   총 뉴스 수: {len(all_headlines)}개")
        
        for press in ['KBS', 'MBC', 'SBS']:
            press_count = len([n for n in all_headlines if n['press'] == press])
            print(f"   - {press}: {press_count}개")
        
        return all_headlines
        
    except Exception as e:
        print(f"❌ 뉴스스탠드 크롤링 오류: {e}")
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
        print(f"    ❌ 본문 추출 오류: {e}")
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
            model="gpt-3.5-turbo",
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
        print(f"    ❌ LLM 요약 오류: {e}")
        return None

def save_news_data(news_list, filename=None):
    """뉴스 데이터를 JSON 파일로 저장"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"newsstand_iframe_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(news_list, f, ensure_ascii=False, indent=2)
        print(f"💾 데이터 저장 완료: {filename}")
        return filename
    except Exception as e:
        print(f"❌ 파일 저장 오류: {e}")
        return None

def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("📺 네이버 뉴스스탠드 iframe 기반 KBS/MBC/SBS 뉴스 크롤러")
    print("🐧 우분투 환경 최적화")
    print("=" * 80)
    
    # OpenAI API 키 확인
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ 환경변수에서 OpenAI API 키를 찾을 수 없습니다.")
        print("📝 .env 파일에 다음 변수를 설정해주세요:")
        print("   OPENAI_API_KEY=your_openai_api_key")
        return
    
    driver = None
    try:
        # 1단계: 브라우저 설정
        print("\n🚀 1단계: Chrome 브라우저 설정 중...")
        driver = setup_chrome_driver_ubuntu()
        if not driver:
            print("❌ Chrome 드라이버를 설정할 수 없습니다.")
            return
        
        # 2단계: 뉴스스탠드 크롤링
        print("\n📰 2단계: iframe 기반 뉴스 수집 중...")
        headlines = crawl_newsstand_with_iframe(driver)
        
        if not headlines:
            print("❌ 뉴스를 수집할 수 없습니다.")
            return
        
        print(f"✅ 총 {len(headlines)}개의 뉴스를 수집했습니다.")
        
        # 3단계: 본문 추출 및 요약
        print(f"\n📝 3단계: 뉴스 본문 추출 및 AI 요약 생성 중...")
        
        processed_news = []
        
        for i, news in enumerate(headlines, 1):
            print(f"\n[{i:2d}/{len(headlines)}] {news['press']} - {news['title'][:60]}...")
            
            # 본문 추출
            print("    📄 본문 추출 중...")
            content = crawl_article_content(news['url'])
            
            if content:
                print(f"    ✅ 본문 추출 성공 (길이: {len(content)}자)")
                
                # LLM 요약
                print("    🤖 AI 요약 생성 중...")
                summary = summarize_with_llm(content, news['title'], news['press'])
                
                if summary:
                    print(f"    📝 AI 요약: {summary}")
                    news['ai_summary'] = summary
                else:
                    print("    ❌ AI 요약 실패")
                    news['ai_summary'] = None
            else:
                print("    ❌ 본문 추출 실패")
                news['ai_summary'] = None
            
            processed_news.append(news)
            
            # API 제한 고려한 대기
            if i < len(headlines):
                time.sleep(2)
        
        # 4단계: 결과 저장
        print(f"\n💾 4단계: 결과 저장 중...")
        filename = save_news_data(processed_news)
        
        # 5단계: 요약 결과 출력
        print(f"\n📋 5단계: 최종 결과")
        print("=" * 80)
        
        success_count = sum(1 for news in processed_news if news.get('ai_summary'))
        
        print(f"📊 전체 뉴스: {len(processed_news)}개")
        print(f"✅ 요약 성공: {success_count}개")
        print(f"❌ 요약 실패: {len(processed_news) - success_count}개")
        
        for press in ['KBS', 'MBC', 'SBS']:
            press_news = [n for n in processed_news if n['press'] == press]
            press_summaries = [n for n in press_news if n.get('ai_summary')]
            print(f"📺 {press}: {len(press_news)}개 (요약 완료: {len(press_summaries)}개)")
        
        print(f"\n💾 저장된 파일: {filename}")
        
        print("\n📺 방송3사 뉴스 요약:")
        print("-" * 80)
        
        for i, news in enumerate(processed_news, 1):
            print(f"\n[{i:2d}] {news['press']} - {news['title']}")
            if news.get('ai_summary'):
                print(f"    📝 {news['ai_summary']}")
            else:
                print(f"    ❌ 요약 없음")
        
        print("\n" + "=" * 80)
        print("🎉 네이버 뉴스스탠드 iframe 크롤링 완료!")
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            try:
                driver.quit()
                print("🔚 브라우저 종료 완료")
            except:
                pass
        
        # Chrome 프로세스 및 임시 디렉토리 정리
        try:
            import subprocess
            import shutil
            
            # Chrome 프로세스 정리
            subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
            subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
            
            # 임시 디렉토리 정리 (driver에 저장된 정보 활용)
            if hasattr(driver, '_temp_dir'):
                try:
                    shutil.rmtree(driver._temp_dir)
                    print(f"🧹 임시 디렉토리 정리: {driver._temp_dir}")
                except:
                    pass
            
            # 추가 임시 디렉토리 정리
            import glob
            temp_dirs = glob.glob('/tmp/chrome_session_*')
            for temp_dir in temp_dirs:
                try:
                    shutil.rmtree(temp_dir)
                    print(f"🧹 임시 디렉토리 정리: {temp_dir}")
                except:
                    pass
                    
            print("🧹 Chrome 프로세스 및 임시 파일 정리 완료")
        except:
            pass

if __name__ == "__main__":
    main()