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

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

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

def crawl_hira_data(test_date=None):
    driver = setup_driver()
    scraped_data = []
    
    try:
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
        
    except Exception as e:
        print(f"Error during crawling: {str(e)}")
    
    finally:
        driver.quit()
    
    return scraped_data

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
    data = crawl_hira_data()  # This now includes pagination logic
    
    if data:
        filepath = save_to_json(data)
        print(f"크롤링이 성공적으로 완료되었습니다: {len(data)}개 레코드")
        print(f"데이터 저장 완료: {filepath}")
    else:
        print("크롤링 결과가 없습니다.")
        print("- 해당 날짜 범위에 HIRA 고시 데이터가 없습니다")

# 테스트 모드: 2024-08-01 ~ 2025-08-01 날짜 범위로 테스트
def test_crawling():
    print("HIRA 데이터 크롤링 테스트를 시작합니다 (2024-08-01 ~ 2025-08-01)...")
    
    driver = setup_driver()
    scraped_data = []
    
    try:
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
            
    except Exception as e:
        print(f"Error during crawling: {str(e)}")
    
    finally:
        driver.quit()
    
    if scraped_data:
        filepath = save_to_json(scraped_data, "hira_data_test_range.json")
        print(f"테스트: 크롤링이 성공적으로 완료되었습니다 - {len(scraped_data)}개 레코드")
        print(f"테스트: 데이터 저장 완료 - {filepath}")
    else:
        print("테스트: 크롤링 결과가 없습니다.")
        print("- 해당 날짜 범위에 HIRA 고시 데이터가 없습니다")

if __name__ == "__main__":
    main()