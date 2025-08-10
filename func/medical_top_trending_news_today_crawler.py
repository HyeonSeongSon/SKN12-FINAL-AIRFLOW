#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
약업닷컴 의료뉴스 크롤러
정확한 XPath를 사용하여 dl 요소에서 뉴스 링크를 수집하고 상세 정보를 크롤링
"""

import json
import time
from datetime import datetime
import os
import tempfile
import uuid
import random
import subprocess
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
        temp_dir = tempfile.mkdtemp(prefix=f'yakup_chrome_{uuid.uuid4().hex[:8]}_')
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

def collect_news_urls(driver):
    """뉴스 URL 수집 (지정된 XPath 패턴 사용)"""
    print("🔍 뉴스 URL 수집 시작...")
    
    news_urls = []
    
    # 컨테이너 1: dl[n]/dt/a 패턴
    container1_xpath = "//*[@id='main_con']/div[1]/div/div[2]/div[2]/div[1]"
    print(f"📦 컨테이너 1 검색 (dl/dt/a 패턴): {container1_xpath}")
    
    try:
        container1 = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, container1_xpath))
        )
        print(f"✅ 컨테이너 1 발견")
        
        # dl 요소들 찾기
        dl_elements = container1.find_elements(By.TAG_NAME, "dl")
        print(f"   📄 dl 요소 {len(dl_elements)}개 발견")
        
        for dl_idx, dl_element in enumerate(dl_elements, 1):
            try:
                # dt/a 링크 찾기
                link_selectors = [
                    ".//dt/a",      # 일반적인 패턴
                    ".//dt/a[1]"    # 첫 번째 링크
                ]
                
                link_found = False
                for selector in link_selectors:
                    try:
                        link_element = dl_element.find_element(By.XPATH, selector)
                        url = link_element.get_attribute('href')
                        title_preview = link_element.text.strip()[:40]
                        
                        if url and url not in news_urls:
                            news_urls.append(url)
                            print(f"     [{len(news_urls)}] 📰 {title_preview}...")
                            print(f"         🔗 {url}")
                            link_found = True
                            break
                    except:
                        continue
                
                if not link_found:
                    print(f"     ❌ dl[{dl_idx}]에서 링크를 찾을 수 없음")
                    
            except Exception as e:
                print(f"     ❌ dl[{dl_idx}] 처리 실패: {e}")
                continue
                
    except TimeoutException:
        print(f"❌ 컨테이너 1을 찾을 수 없음")
    except Exception as e:
        print(f"❌ 컨테이너 1 처리 실패: {e}")
    
    # 컨테이너 2: p[n]/a 패턴
    container2_xpath = "//*[@id='main_con']/div[1]/div/div[2]/div[2]/div[2]"
    print(f"📦 컨테이너 2 검색 (p/a 패턴): {container2_xpath}")
    
    try:
        container2 = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, container2_xpath))
        )
        print(f"✅ 컨테이너 2 발견")
        
        # p 요소들 찾기
        p_elements = container2.find_elements(By.TAG_NAME, "p")
        print(f"   📄 p 요소 {len(p_elements)}개 발견")
        
        for p_idx, p_element in enumerate(p_elements, 1):
            try:
                # p/a 링크 찾기
                link_selectors = [
                    ".//a",      # 일반적인 패턴
                    ".//a[1]"    # 첫 번째 링크
                ]
                
                link_found = False
                for selector in link_selectors:
                    try:
                        link_element = p_element.find_element(By.XPATH, selector)
                        url = link_element.get_attribute('href')
                        title_preview = link_element.text.strip()[:40]
                        
                        if url and url not in news_urls:
                            news_urls.append(url)
                            print(f"     [{len(news_urls)}] 📰 {title_preview}...")
                            print(f"         🔗 {url}")
                            link_found = True
                            break
                    except:
                        continue
                
                if not link_found:
                    print(f"     ❌ p[{p_idx}]에서 링크를 찾을 수 없음")
                    
            except Exception as e:
                print(f"     ❌ p[{p_idx}] 처리 실패: {e}")
                continue
                
    except TimeoutException:
        print(f"❌ 컨테이너 2를 찾을 수 없음")
    except Exception as e:
        print(f"❌ 컨테이너 2 처리 실패: {e}")
    
    print(f"🎯 총 {len(news_urls)}개의 뉴스 URL 수집 완료")
    return news_urls

def crawl_news_detail(driver, news_url, rank):
    """개별 뉴스 상세 정보 크롤링"""
    print(f"📰 [{rank}] 뉴스 상세 정보 크롤링 중...")
    print(f"   🌐 URL: {news_url}")
    
    try:
        # 해당 URL로 이동
        driver.get(news_url)
        time.sleep(2)
        
        news_info = {
            'rank': rank,
            'title': '',
            'content': '',
            'summary': '',
            'url': news_url,
            'date': datetime.now().strftime('%Y%m%d'),
            'source': 'yakup.com'
        }
        
        # 제목 추출 (//*[@id="main_con"]/div[1]/div/div[1]/div[1])
        try:
            title_xpath = "//*[@id='main_con']/div[1]/div/div[1]/div[1]"
            title_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, title_xpath))
            )
            news_info['title'] = title_element.text.strip()
            print(f"   ✅ 제목: {news_info['title']}")
        except Exception as e:
            print(f"   ❌ 제목 추출 실패: {e}")
            news_info['title'] = f"제목 추출 실패"
        
        # 내용 추출 (//*[@id="main_con"]/div[1]/div/div[1]/div[2]/div[2]/span)
        try:
            content_xpath = "//*[@id='main_con']/div[1]/div/div[1]/div[2]/div[2]/span"
            content_elements = driver.find_elements(By.XPATH, content_xpath)
            
            if content_elements:
                content_texts = []
                for elem in content_elements:
                    text = elem.text.strip()
                    if text:
                        content_texts.append(text)
                
                news_info['content'] = ' '.join(content_texts)
                print(f"   ✅ 내용: {len(news_info['content'])}자 추출")
            else:
                print(f"   ❌ 내용 요소를 찾을 수 없음")
                news_info['content'] = "내용 추출 실패"
                
        except Exception as e:
            print(f"   ❌ 내용 추출 실패: {e}")
            news_info['content'] = "내용 추출 실패"
        
        return news_info
        
    except Exception as e:
        print(f"   ❌ 뉴스 [{rank}] 상세 정보 크롤링 실패: {e}")
        return None

def summarize_with_openai(title, content):
    """OpenAI API로 기사 요약"""
    try:
        # OpenAI API 키 확인
        if not os.getenv('OPENAI_API_KEY'):
            print("    ⚠️ OpenAI API 키가 설정되지 않음")
            return None
        
        if not content or len(content.strip()) < 50 or "추출 실패" in content:
            return "본문 내용이 부족합니다."
        
        # 내용이 너무 길면 자르기
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        # OpenAI 클라이언트 초기화
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # 프롬프트 생성
        prompt = f"""다음 의료/제약 뉴스 기사를 2-3문장으로 간결하게 요약해주세요.
        
제목: {title}

내용: {content}

요약:"""
        
        # OpenAI API 호출
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        print(f"    ❌ OpenAI 요약 오류: {e}")
        return None

def add_summaries(news_list):
    """뉴스 목록에 AI 요약 추가"""
    print(f"\n🤖 AI 요약 생성 중... ({len(news_list)}개)")
    
    for i, news in enumerate(news_list, 1):
        print(f"\n[{i}/{len(news_list)}] {news['title'][:50]}...")
        
        if news['content'] and "추출 실패" not in news['content']:
            print("    🤖 AI 요약 생성 중...")
            summary = summarize_with_openai(news['title'], news['content'])
            
            if summary:
                news['summary'] = summary
                print(f"    📝 요약: {summary}")
            else:
                news['summary'] = "요약 생성 실패"
                print("    ❌ AI 요약 생성 실패")
        else:
            news['summary'] = "본문 내용 부족"
            print("    ❌ 본문 내용이 부족하여 요약 불가")
        
        # API 요청 간격 조정
        if i < len(news_list):
            time.sleep(2)
    
    return news_list

def crawl_yakup_news(target_date=None):
    """약업닷컴 의료뉴스 크롤링 메인 함수"""
    
    # 기본값: 오늘 날짜
    if target_date is None:
        target_date = datetime.now().strftime('%Y%m%d')
    
    # 날짜 형식 유효성 검사 (YYYYMMDD 형식)
    try:
        datetime.strptime(target_date, '%Y%m%d')
    except ValueError:
        print(f"❌ 잘못된 날짜 형식: {target_date}. YYYYMMDD 형식을 사용해주세요.")
        return {
            'target_date': target_date,
            'target_url': '',
            'status': '실패',
            'error': f'잘못된 날짜 형식: {target_date}',
            'news_count': 0,
            'news_list': [],
            'crawling_time': datetime.now().isoformat()
        }
    
    base_url = "http://m.yakup.com/news/index.html"
    target_url = f"{base_url}?cat=bclick&bc_date={target_date}"
    
    print("=" * 80)
    print("📰 약업닷컴 의료뉴스 크롤러")
    print("=" * 80)
    print(f"🎯 대상 날짜: {target_date}")
    print(f"🌐 접속 URL: {target_url}")
    
    driver = None
    news_data = []
    
    try:
        # Chrome 드라이버 설정
        driver = setup_chrome_driver()
        if not driver:
            raise Exception("Chrome 드라이버 설정 실패")
        
        print("📱 메인 페이지 로딩 중...")
        driver.get(target_url)
        
        # 기본 페이지 로딩 대기
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("✅ 메인 페이지 로드 완료")
        
        # 동적 콘텐츠 로딩 대기
        time.sleep(3)
        
        # 1단계: 뉴스 URL 수집
        news_urls = collect_news_urls(driver)
        
        if not news_urls:
            print("⚠️ 수집된 뉴스 URL이 없습니다")
            return {
                'target_date': target_date,
                'target_url': target_url,
                'status': '성공',
                'error': None,
                'news_count': 0,
                'news_list': []
            }
        
        # 2단계: 각 뉴스 상세 정보 크롤링
        print(f"\n📊 {len(news_urls)}개 뉴스의 상세 정보 크롤링 시작...")
        
        for i, news_url in enumerate(news_urls, 1):
            news_info = crawl_news_detail(driver, news_url, i)
            
            if news_info and news_info['title'] != "제목 추출 실패":
                news_data.append(news_info)
                print(f"   ✅ 뉴스 [{i}] 수집 완료")
            else:
                print(f"   ❌ 뉴스 [{i}] 수집 실패")
            
            # 요청 간격 조정
            if i < len(news_urls):
                time.sleep(1)
        
        print(f"\n🎉 크롤링 완료: {len(news_data)}개 뉴스 수집")
        
        # 3단계: AI 요약 생성
        if news_data:
            news_data = add_summaries(news_data)
        
        return {
            'target_date': target_date,
            'target_url': target_url,
            'status': '성공',
            'error': None,
            'news_count': len(news_data),
            'news_list': news_data,
            'crawling_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")
        return {
            'target_date': target_date,
            'target_url': target_url,
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
        target_date = data.get('target_date', 'unknown')
        filename = f'medical_top_trending_news_{target_date}_{timestamp}.json'
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 데이터 저장 완료: {filepath}")
    return filepath

def main_with_retry(target_date=None, max_retries=3):
    """재시도 메커니즘이 포함된 메인 실행 함수"""
    
    # 사용자 입력 날짜가 있으면 사용, 없으면 오늘 날짜 사용
    if target_date is None:
        target_date = datetime.now().strftime('%Y%m%d')
        print(f"📅 날짜가 지정되지 않아 오늘 날짜를 사용합니다: {target_date}")
    else:
        print(f"📅 지정된 날짜로 크롤링합니다: {target_date}")
    
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
            result = crawl_yakup_news(target_date)
            
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
                        'target_date': target_date,
                        'target_url': f"http://m.yakup.com/news/index.html?cat=bclick&bc_date={target_date}",
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
        print(f"📅 대상 날짜: {result['target_date']}")
        print(f"🌐 URL: {result['target_url']}")
        print(f"📈 상태: {result['status']}")
        print(f"📰 수집된 뉴스: {result['news_count']}개")
        
        if result['error']:
            print(f"❌ 오류: {result['error']}")
        
        if result['news_list']:
            print("\n📋 수집된 뉴스 목록:")
            print("-" * 80)
            for news in result['news_list']:
                print(f"[{news['rank']:2d}] {news['title']}")
                if news['url']:
                    print(f"     🔗 {news['url']}")
                if news['summary'] and news['summary'] not in ["", "본문 내용 부족", "요약 생성 실패"]:
                    print(f"     📝 {news['summary']}")
                print()
        
        print(f"💾 결과 파일: {filepath}")
        if result['status'] == '성공':
            print("🎉 크롤링 완료!")
        else:
            print("💥 크롤링 최종 실패!")

def main(target_date=None):
    """메인 실행 함수 (하위 호환성 유지)"""
    main_with_retry(target_date, max_retries=3)

if __name__ == "__main__":
    # 오늘 날짜로 크롤링
    target_date = datetime.now().strftime('%Y%m%d')
    print(f"🎯 설정된 날짜: {target_date}")
    
    main(target_date)