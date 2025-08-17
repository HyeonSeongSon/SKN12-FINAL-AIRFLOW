import json
import pandas as pd
import glob
import os
from datetime import datetime

def process_medical_recent_news():
    """
    medical_recent_news JSON 파일들을 처리하여 고유한 뉴스만 반환하는 함수
    """
    print("=" * 60)
    print("MEDICAL RECENT NEWS 처리 시작")
    print("=" * 60)
    
    # crawler_result 디렉토리에서 medical_recent_news가 포함된 JSON 파일들 찾기
    json_files = glob.glob('/home/son/SKN12-FINAL-AIRFLOW/crawler_result/medical_recent_news_*.json')
    
    if not json_files:
        print("medical_recent_news JSON 파일을 찾을 수 없습니다.")
        return []
    
    if len(json_files) < 2:
        print("비교할 파일이 부족합니다. 최소 2개 파일이 필요합니다.")
        return []
    
    # 파일들을 생성 시간 기준으로 정렬 (가장 최신 파일을 찾기 위해)
    json_files.sort(key=os.path.getctime)
    latest_file = json_files[-1]  # 가장 최신 파일
    other_files = json_files[:-1]  # 나머지 파일들
    
    print(f"가장 최신 파일: {os.path.basename(latest_file)}")
    print(f"비교할 다른 파일들: {len(other_files)}개")
    
    # 1. 최신 파일 읽기
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            latest_data = json.load(f)
    except Exception as e:
        print(f"최신 파일 읽기 실패: {str(e)}")
        return []
    
    # JSON 구조 확인 및 news_list 추출
    if isinstance(latest_data, dict) and 'news_list' in latest_data:
        latest_news_list = latest_data['news_list']
    else:
        print("최신 파일이 예상된 구조가 아닙니다. (news_list 키를 찾을 수 없음)")
        return []
    
    print(f"최신 파일에서 {len(latest_news_list)}개 기사 발견")
    
    # 2. 다른 모든 파일들에서 URL과 title 조합 수집
    existing_url_title_pairs = set()
    
    for file_path in other_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'news_list' in data:
                news_list = data['news_list']
                for item in news_list:
                    url = item.get('url', '').strip()
                    title = item.get('title', '').strip()
                    if url and title:
                        existing_url_title_pairs.add((url, title))
        except Exception:
            continue
    
    # 3. 최신 파일에서 중복되지 않는 기사만 필터링
    unique_articles = []
    duplicate_count = 0
    
    for item in latest_news_list:
        url = item.get('url', '').strip()
        title = item.get('title', '').strip()
        
        if url and title:
            current_pair = (url, title)
            
            if current_pair not in existing_url_title_pairs:
                processed_item = {
                    '제목': title,
                    'url': url,
                    '언론사': 'yakup.com',  # 고정값
                    '업로드_날짜': item.get('date', ''),
                    '타입': 'medical news',  # 고정값
                    '요약': item.get('summary', '')
                }
                unique_articles.append(processed_item)
            else:
                duplicate_count += 1
        else:
            duplicate_count += 1
    
    print(f"Recent News 중복 제거 결과:")
    print(f"  - 최신 파일 총 기사: {len(latest_news_list)}개")
    print(f"  - 중복된 기사: {duplicate_count}개")
    print(f"  - 고유한 기사: {len(unique_articles)}개")
    
    return unique_articles

def process_medical_top_trending_news():
    """
    medical_top_trending_news JSON 파일들을 처리하여 고유한 뉴스만 반환하는 함수
    """
    print("=" * 60)
    print("MEDICAL TOP TRENDING NEWS 처리 시작")
    print("=" * 60)
    
    # crawler_result 디렉토리에서 medical_top_trending_news가 포함된 JSON 파일들 찾기
    json_files = glob.glob('/home/son/SKN12-FINAL-AIRFLOW/crawler_result/medical_top_trending_news_*.json')
    
    if not json_files:
        print("medical_top_trending_news JSON 파일을 찾을 수 없습니다.")
        return []
    
    if len(json_files) < 2:
        print("비교할 파일이 부족합니다. 최소 2개 파일이 필요합니다.")
        return []
    
    # 파일들을 생성 시간 기준으로 정렬 (가장 최신 파일을 찾기 위해)
    json_files.sort(key=os.path.getctime)
    latest_file = json_files[-1]  # 가장 최신 파일
    other_files = json_files[:-1]  # 나머지 파일들
    
    print(f"가장 최신 파일: {os.path.basename(latest_file)}")
    print(f"비교할 다른 파일들: {len(other_files)}개")
    
    # 1. 최신 파일 읽기
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            latest_data = json.load(f)
    except Exception as e:
        print(f"최신 파일 읽기 실패: {str(e)}")
        return []
    
    # JSON 구조 확인 및 news_list 추출
    if isinstance(latest_data, dict) and 'news_list' in latest_data:
        latest_news_list = latest_data['news_list']
    else:
        print("최신 파일이 예상된 구조가 아닙니다. (news_list 키를 찾을 수 없음)")
        return []
    
    print(f"최신 파일에서 {len(latest_news_list)}개 기사 발견")
    
    # 2. 다른 모든 파일들에서 URL과 title 조합 수집
    existing_url_title_pairs = set()
    
    for file_path in other_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'news_list' in data:
                news_list = data['news_list']
                for item in news_list:
                    url = item.get('url', '').strip()
                    title = item.get('title', '').strip()
                    if url and title:
                        existing_url_title_pairs.add((url, title))
        except Exception:
            continue
    
    # 3. 최신 파일에서 중복되지 않는 기사만 필터링
    unique_articles = []
    duplicate_count = 0
    
    for item in latest_news_list:
        url = item.get('url', '').strip()
        title = item.get('title', '').strip()
        
        if url and title:
            current_pair = (url, title)
            
            if current_pair not in existing_url_title_pairs:
                processed_item = {
                    '제목': title,
                    'url': url,
                    '언론사': item.get('source', ''),  # JSON의 source 값
                    '업로드_날짜': item.get('pub_time', ''),  # JSON의 pub_time 값
                    '타입': item.get('type', ''),  # JSON의 type 값
                    '요약': item.get('summary', '')
                }
                unique_articles.append(processed_item)
            else:
                duplicate_count += 1
        else:
            duplicate_count += 1
    
    print(f"Top Trending News 중복 제거 결과:")
    print(f"  - 최신 파일 총 기사: {len(latest_news_list)}개")
    print(f"  - 중복된 기사: {duplicate_count}개")
    print(f"  - 고유한 기사: {len(unique_articles)}개")
    
    return unique_articles

def preprocess_medical_news():
    """
    medical_recent_news와 medical_top_trending_news를 모두 처리하여 
    하나의 Excel 파일로 저장하는 함수
    """
    print("🏥 MEDICAL NEWS 전처리 시작")
    print("=" * 80)
    
    # 1. Recent News 처리
    recent_articles = process_medical_recent_news()
    
    # 2. Top Trending News 처리  
    trending_articles = process_medical_top_trending_news()
    
    # 3. 두 결과 합치기
    all_articles = recent_articles + trending_articles
    
    print("=" * 60)
    print("전체 결과 합계")
    print("=" * 60)
    print(f"Recent News 고유 기사: {len(recent_articles)}개")
    print(f"Top Trending News 고유 기사: {len(trending_articles)}개")
    print(f"전체 고유 기사: {len(all_articles)}개")
    
    if not all_articles:
        print("처리할 고유한 기사가 없습니다. Excel 파일을 생성하지 않습니다.")
        return None
    
    # 4. DataFrame 생성
    df = pd.DataFrame(all_articles)
    
    # 빈 URL 제거 (추가 안전장치)
    df = df[df['url'].str.strip() != '']
    
    print(f"최종 처리된 기사: {len(df)}개")
    
    # 5. Excel 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'/home/son/SKN12-FINAL-AIRFLOW/crawler_result/medical_news_unique_{timestamp}.xlsx'
    
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"\n✅ 전처리 완료. 저장된 파일: {output_file}")
    
    # 통계 정보 출력
    if len(df) > 0:
        print("\n📊 통합 기사 통계:")
        
        # 언론사별 통계
        if '언론사' in df.columns:
            press_counts = df['언론사'].value_counts()
            print("\n언론사별 기사 수:")
            for press, count in press_counts.items():
                print(f"  {press}: {count}개")
        
        # 타입별 통계  
        if '타입' in df.columns:
            type_counts = df['타입'].value_counts()
            print("\n타입별 기사 수:")
            for news_type, count in type_counts.items():
                print(f"  {news_type}: {count}개")
        
        # 날짜별 통계
        if '업로드_날짜' in df.columns:
            date_counts = df['업로드_날짜'].value_counts()
            print("\n날짜별 기사 수 (상위 5개):")
            for date, count in date_counts.head(5).items():
                print(f"  {date}: {count}개")
    
    return df

# 하위 호환성을 위한 별칭
def preprocess_medical_recent_news():
    """하위 호환성을 위한 함수 (기존 함수명)"""
    return preprocess_medical_news()

if __name__ == "__main__":
    preprocess_medical_news()