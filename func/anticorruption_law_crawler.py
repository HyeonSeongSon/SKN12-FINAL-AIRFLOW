#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime
from bs4 import BeautifulSoup
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def get_webpage_with_selenium(url):
    """Selenium을 사용한 동적 웹페이지 HTML 가져오기"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        print("Selenium WebDriver 시작...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"페이지 로딩 중: {url}")
        driver.get(url)
        
        # 페이지 기본 로드 대기
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("기본 페이지 로드 완료")
        
        # 동적 콘텐츠 로딩 대기
        time.sleep(5)
        
        # 핵심 요소들 대기
        for element_id in ["contentBody", "conScroll"]:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, element_id))
                )
                print(f"{element_id} 요소 로드 확인")
            except:
                print(f"{element_id} 요소 대기 타임아웃")
        
        # pgroup 클래스 요소들 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "pgroup"))
            )
            print("pgroup 요소 로드 확인")
        except:
            print("pgroup 요소 대기 타임아웃")
        
        time.sleep(3)
        
        html_content = driver.page_source
        driver.quit()
        
        print(f"Selenium으로 웹페이지 요청 성공: {len(html_content)}자")
        return html_content
        
    except Exception as e:
        print(f"Selenium 웹페이지 요청 실패: {str(e)}")
        try:
            driver.quit()
        except:
            pass
        return None

def crawl_anticorruption_law():
    """청탁금지법 크롤링 함수"""
    scraped_data = {}
    iframe_url = "https://www.law.go.kr/LSW//lsInfoP.do?lsiSeq=268655&chrClsCd=010202&urlMode=lsInfoP&efYd=20250121&ancYnChk=0"
    
    try:
        print(f"청탁금지법 iframe 페이지 접속: {iframe_url}")
        
        # Selenium으로 동적 콘텐츠 로딩
        html_content = get_webpage_with_selenium(iframe_url)
        if not html_content:
            raise Exception("iframe 페이지 HTML을 가져올 수 없습니다")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        print("HTML 파싱 완료")
        
        # 법명 수집
        try:
            con_top = soup.find('div', id='conTop')
            if con_top and con_top.find('h2'):
                law_name = con_top.find('h2').get_text(strip=True)
                scraped_data['법명'] = law_name
                print(f"법명 수집 완료: {law_name}")
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
                    print(f"시행 법률 정보 수집 완료: {law_info[:100]}...")
                else:
                    scraped_data['시행_법률_정보'] = "시행 법률 정보 없음"
            else:
                scraped_data['시행_법률_정보'] = "conTop div 없음"
        except Exception as e:
            scraped_data['시행_법률_정보'] = f"수집 실패: {str(e)}"
        
        # pgroup 텍스트 추출 (핵심 기능)
        try:
            # DOM 구조 탐색: bodyId → searchForm → container → center → bodyContentTOP → viewwrapCenter → bodyContent → contentBody → sideCenter → conScroll
            path = [
                ('bodyId', 'body_id'),
                ('searchForm', 'search_form'),
                ('container', 'container'),
                ('center', 'center'),
                ('bodyContentTOP', 'body_content_top'),
                ('viewwrapCenter', 'viewwrap_center'),
                ('bodyContent', 'body_content'),
                ('contentBody', 'content_body'),
                ('sideCenter', 'side_center'),
                ('conScroll', 'con_scroll')
            ]
            
            current_element = soup
            for element_id, var_name in path:
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
                    print(f"총 {len(pgroup_texts)}개 pgroup 텍스트 수집 완료")
                else:
                    print("pgroup 클래스를 찾을 수 없음")
            else:
                print("DOM 구조 탐색 실패")
                
        except Exception as e:
            print(f"pgroup 텍스트 추출 실패: {str(e)}")
        
        # 크롤링 메타데이터
        scraped_data['크롤링_시간'] = datetime.now().isoformat()
        scraped_data['소스_URL'] = iframe_url
        scraped_data['크롤링_상태'] = "성공"
        
    except Exception as e:
        print(f"크롤링 중 오류 발생: {str(e)}")
        scraped_data = {
            '법명': "크롤링 실패",
            '시행_법률_정보': "크롤링 실패", 
            '크롤링_시간': datetime.now().isoformat(),
            '소스_URL': iframe_url,
            '크롤링_상태': "실패",
            '오류_메시지': str(e)
        }
    
    return scraped_data

def save_to_json(data, filename=None):
    """JSON 파일로 저장"""
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'anticorruption_law_{timestamp}.json'
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filepath

def main():
    """메인 실행 함수"""
    print("청탁금지법 크롤링을 시작합니다...")
    data = crawl_anticorruption_law()
    
    if data and data.get('크롤링_상태') == '성공':
        filepath = save_to_json(data)
        print("크롤링이 성공적으로 완료되었습니다.")
        print(f"데이터 저장 완료: {filepath}")
        
        # 수집 결과 요약
        print("\n=== 수집 결과 요약 ===")
        print(f"법명: {data.get('법명', 'N/A')}")
        print(f"시행 정보: {data.get('시행_법률_정보', 'N/A')}")
        print(f"pgroup 개수: {data.get('pgroup_개수', 0)}개")
            
    else:
        print("크롤링 실패")
        print(f"오류: {data.get('오류_메시지', '알 수 없는 오류')}")
        save_to_json(data, 'anticorruption_law_failed.json')

if __name__ == "__main__":
    main()