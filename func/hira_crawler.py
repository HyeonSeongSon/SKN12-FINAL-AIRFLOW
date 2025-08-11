#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import tempfile
import uuid
import random
import subprocess

def setup_driver():
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
        temp_dir = tempfile.mkdtemp(prefix=f'hira_chrome_{uuid.uuid4().hex[:8]}_')
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        
        debug_port = random.randint(9500, 9999)
        chrome_options.add_argument(f'--remote-debugging-port={debug_port}')
        
        # 성능 최적화
        chrome_options.add_argument('--memory-pressure-off')
        chrome_options.add_argument('--max_old_space_size=2048')
        chrome_options.add_argument('--aggressive-cache-discard')
        
        # 자동화 감지 방지
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        print(f"🔧 Chrome 세션 디렉토리: {temp_dir}")
        print(f"🔧 디버깅 포트: {debug_port}")
        
        # 드라이버 생성
        driver = webdriver.Chrome(options=chrome_options)
        
        # 세션 정보 저장
        driver._temp_dir = temp_dir
        driver._debug_port = debug_port
        
        # 타임아웃 설정
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)
        
        # 자동화 감지 방지 스크립트
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("✅ Chrome 드라이버 설정 완료")
        return driver
        
    except Exception as e:
        print(f"❌ Chrome 드라이버 설정 실패: {e}")
        return None

def get_today_date():
    today = datetime.now()
    return today.strftime('%Y-%m-%d')

def get_yesterday_date():
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def crawl_page_data(driver, wait):
    """Crawl data from current page"""
    page_data = []
    
    tbody = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="cont"]/div[1]/div[3]/table/tbody')))
    rows = tbody.find_elements(By.TAG_NAME, 'tr')
    
    for i, row in enumerate(rows, 1):
        try:
            # Re-find elements each time to avoid stale reference
            tbody = driver.find_element(By.XPATH, '//*[@id="cont"]/div[1]/div[3]/table/tbody')
            current_row = tbody.find_element(By.XPATH, f'./tr[{i}]')
            
            td2_element = current_row.find_element(By.XPATH, './td[2]')
            td3_element = current_row.find_element(By.XPATH, './td[3]')
            td5_element = current_row.find_element(By.XPATH, './td[5]')
            
            고시 = td2_element.text.strip()
            타이틀 = td3_element.text.strip()
            날짜 = td5_element.text.strip()
            
            url = None
            try:
                link_element = td3_element.find_element(By.TAG_NAME, 'a')
                if link_element:
                    # Store current window handle
                    main_window = driver.current_window_handle
                    
                    # Click the link (opens in new window)
                    link_element.click()
                    time.sleep(2)
                    
                    # Switch to new window
                    for window_handle in driver.window_handles:
                        if window_handle != main_window:
                            driver.switch_to.window(window_handle)
                            url = driver.current_url
                            driver.close()
                            break
                    
                    # Switch back to main window
                    driver.switch_to.window(main_window)
                    time.sleep(1)
            except:
                pass
            
            row_data = {
                'row_number': len(page_data) + 1,
                '고시': 고시,
                '타이틀': 타이틀,
                '날짜': 날짜,
                'url': url,
                'crawled_date': datetime.now().isoformat()
            }
            
            page_data.append(row_data)
            
        except Exception as e:
            print(f"Error processing row {i}: {str(e)}")
            continue
    
    return page_data

def crawl_hira_data_with_retry(test_date=None, max_retries=3):
    """재시도 메커니즘이 포함된 HIRA 데이터 크롤링 함수"""
    
    for attempt in range(1, max_retries + 1):
        print(f"\n🔄 HIRA 크롤링 시도 {attempt}/{max_retries}")
        
        driver = None
        try:
            # Chrome 프로세스 정리 (재시도 전)
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
                time.sleep(2)
                print("🧹 이전 Chrome 프로세스 정리 완료")
            except:
                pass
            
            # 새 드라이버 생성
            driver = setup_driver()
            if not driver:
                raise Exception("Chrome 드라이버 생성 실패")
            
            # 크롤링 실행
            scraped_data = []
            url = "https://www.hira.or.kr/rc/insu/insuadtcrtr/InsuAdtCrtrList.do?pgmid=HIRAA030069000400&WT.gnb=%EB%B3%B4%ED%97%98%EC%9D%B8%EC%A0%95%EA%B8%B0%EC%A4%80"
            driver.get(url)
            
            wait = WebDriverWait(driver, 10)
            
            # Use yesterday for start date and today for end date
            if test_date:
                start_date = test_date
                end_date = test_date
            else:
                start_date = get_yesterday_date()  # 어제 날짜
                end_date = get_today_date()       # 오늘 날짜
            
            start_date_input = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="startDt"]')))
            start_date_input.clear()
            start_date_input.send_keys(start_date)
            
            end_date_input = driver.find_element(By.XPATH, '//*[@id="endDt"]')
            end_date_input.clear()
            end_date_input.send_keys(end_date)
            
            search_button = driver.find_element(By.XPATH, '//*[@id="searchForm"]/div[2]/div[2]/a')
            search_button.click()
            
            time.sleep(3)
            
            # Pagination loop - continue until no more pages
            page_set_number = 1
            crawled_pages = set()  # Track crawled page numbers
            
            while True:
                print(f"Processing page set {page_set_number}")
                
                # Get all available pages in current set
                try:
                    paging_ul = driver.find_element(By.XPATH, '//*[@id="pagingPc"]/ul')
                    page_li_elements = paging_ul.find_elements(By.TAG_NAME, 'li')
                    print(f"Found {len(page_li_elements)} page buttons in current set")
                    
                    # Click through all li pages in current set
                    for i in range(len(page_li_elements)):
                        try:
                            # Re-find pagination elements to avoid stale references
                            paging_ul = driver.find_element(By.XPATH, '//*[@id="pagingPc"]/ul')
                            current_page_li_elements = paging_ul.find_elements(By.TAG_NAME, 'li')
                            
                            # Check if current index is still valid
                            if i >= len(current_page_li_elements):
                                print(f"Index {i} out of range, skipping...")
                                continue
                                
                            # Get page number from li element
                            page_link = current_page_li_elements[i].find_element(By.TAG_NAME, 'a')
                            page_text = page_link.text.strip()
                            
                            # Skip if already crawled
                            if page_text in crawled_pages:
                                print(f"Page {page_text} already crawled, skipping...")
                                continue
                            
                            print(f"Clicking page {page_text} (li index {i})...")
                            page_link.click()
                            time.sleep(2)
                            
                            # Crawl current page data
                            print(f"Crawling page {page_text}...")
                            page_data = crawl_page_data(driver, wait)
                            scraped_data.extend(page_data)
                            
                            # Mark as crawled
                            crawled_pages.add(page_text)
                            
                        except Exception as e:
                            print(f"Error processing li index {i}: {str(e)}")
                            continue
                    
                except Exception as e:
                    print(f"No pagination ul found or error: {str(e)}")
                    break
                
                # Look for next page set button (class="next")
                try:
                    next_button = driver.find_element(By.XPATH, '//*[@id="pagingPc"]/a[@class="next"]')
                    if next_button.is_enabled() and next_button.is_displayed():
                        print("Found next page set button, clicking...")
                        next_button.click()
                        time.sleep(3)
                        page_set_number += 1
                    else:
                        print("Next button exists but not clickable, finishing crawling")
                        break
                        
                except Exception as e:
                    print(f"No next page set button found: {str(e)}")
                    print("Finished crawling all available pages")
                    break
            
            # Update row numbers to be sequential across all pages
            for i, row in enumerate(scraped_data, 1):
                row['row_number'] = i
            
            # 성공적으로 완료됨
            if scraped_data:
                print(f"✅ HIRA 크롤링 성공! ({attempt}/{max_retries}) - {len(scraped_data)}개 레코드 수집")
                return scraped_data
            else:
                print(f"⚠️ HIRA 크롤링 완료했지만 데이터 없음 ({attempt}/{max_retries})")
                return []  # 빈 결과도 성공으로 간주
        
        except Exception as e:
            print(f"❌ HIRA 크롤링 시도 {attempt} 실패: {e}")
            
            # 마지막 시도가 아니면 재시도 안내
            if attempt < max_retries:
                wait_time = attempt * 5  # 재시도 간격을 점진적으로 증가
                print(f"⏰ {wait_time}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                print(f"💥 모든 시도 실패. 최대 재시도 횟수({max_retries}) 도달")
        
        finally:
            # 각 시도마다 Chrome 프로세스 정리
            if driver:
                try:
                    driver.quit()
                    print(f"🔚 HIRA 브라우저 종료 (시도 {attempt})")
                except:
                    pass
                
                # 임시 디렉토리 정리
                if hasattr(driver, '_temp_dir'):
                    try:
                        import shutil
                        shutil.rmtree(driver._temp_dir)
                        print(f"🧹 HIRA 임시 디렉토리 정리: {driver._temp_dir}")
                    except:
                        pass
            
            # Chrome 프로세스 강제 정리
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
            except:
                pass
    
    # 모든 재시도 실패
    print("💥 HIRA 크롤링 최종 실패!")
    return []

def crawl_hira_data(test_date=None):
    """하위 호환성을 위한 기존 함수 (재시도 메커니즘 사용)"""
    return crawl_hira_data_with_retry(test_date, max_retries=3)

def save_to_json(data, filename=None):
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'hira_data_{timestamp}.json'
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filepath

def main():
    print(f"HIRA 데이터 크롤링을 시작합니다 ({get_yesterday_date()} ~ {get_today_date()})...")
    print("🔄 최대 3회 재시도 메커니즘 활성화")
    
    data = crawl_hira_data()  # 재시도 메커니즘이 포함된 함수 호출
    
    if data:
        filepath = save_to_json(data)
        print(f"🎉 크롤링이 성공적으로 완료되었습니다: {len(data)}개 레코드")
        print(f"💾 데이터 저장 완료: {filepath}")
    else:
        print("💥 크롤링 최종 실패!")
        print("- 모든 재시도가 실패했거나 해당 날짜 범위에 HIRA 고시 데이터가 없습니다")

# 테스트 모드: 2024-08-01 ~ 2025-08-01 날짜 범위로 테스트 (재시도 메커니즘 포함)
def test_crawling_with_retry(max_retries=3):
    """재시도 메커니즘이 포함된 테스트 크롤링 함수"""
    
    for attempt in range(1, max_retries + 1):
        print(f"\n🔄 HIRA 테스트 크롤링 시도 {attempt}/{max_retries}")
        
        driver = None
        try:
            # Chrome 프로세스 정리 (재시도 전)
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
                time.sleep(2)
                print("🧹 이전 Chrome 프로세스 정리 완료")
            except:
                pass
            
            # 새 드라이버 생성
            driver = setup_driver()
            if not driver:
                raise Exception("Chrome 드라이버 생성 실패")
            
            url = "https://www.hira.or.kr/rc/insu/insuadtcrtr/InsuAdtCrtrList.do?pgmid=HIRAA030069000400&WT.gnb=%EB%B3%B4%ED%97%98%EC%9D%B8%EC%A0%95%EA%B8%B0%EC%A4%80"
            driver.get(url)
            
            wait = WebDriverWait(driver, 10)
            
            # Set specific date range for test
            start_date_input = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="startDt"]')))
            start_date_input.clear()
            start_date_input.send_keys("2024-08-01")
            
            end_date_input = driver.find_element(By.XPATH, '//*[@id="endDt"]')
            end_date_input.clear()
            end_date_input.send_keys("2025-08-01")
            
            search_button = driver.find_element(By.XPATH, '//*[@id="searchForm"]/div[2]/div[2]/a')
            search_button.click()
            
            time.sleep(3)
            
            # Pagination loop - continue until no more pages
            page_set_number = 1
            crawled_pages = set()  # Track crawled page numbers
            scraped_data = []
            
            while True:
                print(f"Processing page set {page_set_number}")
                
                # Get all available pages in current set
                try:
                    paging_ul = driver.find_element(By.XPATH, '//*[@id="pagingPc"]/ul')
                    page_li_elements = paging_ul.find_elements(By.TAG_NAME, 'li')
                    print(f"Found {len(page_li_elements)} page buttons in current set")
                    
                    # Click through all li pages in current set
                    for i in range(len(page_li_elements)):
                        try:
                            # Re-find pagination elements to avoid stale references
                            paging_ul = driver.find_element(By.XPATH, '//*[@id="pagingPc"]/ul')
                            current_page_li_elements = paging_ul.find_elements(By.TAG_NAME, 'li')
                            
                            # Check if current index is still valid
                            if i >= len(current_page_li_elements):
                                print(f"Index {i} out of range, skipping...")
                                continue
                                
                            # Get page number from li element
                            page_link = current_page_li_elements[i].find_element(By.TAG_NAME, 'a')
                            page_text = page_link.text.strip()
                            
                            # Skip if already crawled
                            if page_text in crawled_pages:
                                print(f"Page {page_text} already crawled, skipping...")
                                continue
                            
                            print(f"Clicking page {page_text} (li index {i})...")
                            page_link.click()
                            time.sleep(2)
                            
                            # Crawl current page data
                            print(f"Crawling page {page_text}...")
                            page_data = crawl_page_data(driver, wait)
                            scraped_data.extend(page_data)
                            
                            # Mark as crawled
                            crawled_pages.add(page_text)
                            
                        except Exception as e:
                            print(f"Error processing li index {i}: {str(e)}")
                            continue
                    
                except Exception as e:
                    print(f"No pagination ul found or error: {str(e)}")
                    break
                
                # Look for next page set button (class="next")
                try:
                    next_button = driver.find_element(By.XPATH, '//*[@id="pagingPc"]/a[@class="next"]')
                    if next_button.is_enabled() and next_button.is_displayed():
                        print("Found next page set button, clicking...")
                        next_button.click()
                        time.sleep(3)
                        page_set_number += 1
                    else:
                        print("Next button exists but not clickable, finishing crawling")
                        break
                        
                except Exception as e:
                    print(f"No next page set button found: {str(e)}")
                    print("Finished crawling all available pages")
                    break
            
            # Update row numbers to be sequential across all pages
            for i, row in enumerate(scraped_data, 1):
                row['row_number'] = i
            
            # 성공적으로 완료됨
            if scraped_data:
                print(f"✅ HIRA 테스트 크롤링 성공! ({attempt}/{max_retries}) - {len(scraped_data)}개 레코드 수집")
                return scraped_data
            else:
                print(f"⚠️ HIRA 테스트 크롤링 완료했지만 데이터 없음 ({attempt}/{max_retries})")
                return []  # 빈 결과도 성공으로 간주
        
        except Exception as e:
            print(f"❌ HIRA 테스트 크롤링 시도 {attempt} 실패: {e}")
            
            # 마지막 시도가 아니면 재시도 안내
            if attempt < max_retries:
                wait_time = attempt * 5  # 재시도 간격을 점진적으로 증가
                print(f"⏰ {wait_time}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                print(f"💥 모든 시도 실패. 최대 재시도 횟수({max_retries}) 도달")
        
        finally:
            # 각 시도마다 Chrome 프로세스 정리
            if driver:
                try:
                    driver.quit()
                    print(f"🔚 HIRA 테스트 브라우저 종료 (시도 {attempt})")
                except:
                    pass
                
                # 임시 디렉토리 정리
                if hasattr(driver, '_temp_dir'):
                    try:
                        import shutil
                        shutil.rmtree(driver._temp_dir)
                        print(f"🧹 HIRA 테스트 임시 디렉토리 정리: {driver._temp_dir}")
                    except:
                        pass
            
            # Chrome 프로세스 강제 정리
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, timeout=5)
            except:
                pass
    
    # 모든 재시도 실패
    print("💥 HIRA 테스트 크롤링 최종 실패!")
    return []

def test_crawling():
    """하위 호환성을 위한 기존 함수 (재시도 메커니즘 사용)"""
    print("🔄 최대 3회 재시도 메커니즘 활성화")
    data = test_crawling_with_retry(max_retries=3)
    
    if data:
        filepath = save_to_json(data, "hira_data_test_range.json")
        print(f"🎉 테스트: 크롤링이 성공적으로 완료되었습니다 - {len(data)}개 레코드")
        print(f"💾 테스트: 데이터 저장 완료 - {filepath}")
    else:
        print("💥 테스트: 크롤링 최종 실패!")
        print("- 모든 재시도가 실패했거나 해당 날짜 범위에 HIRA 고시 데이터가 없습니다")

if __name__ == "__main__":
    main()