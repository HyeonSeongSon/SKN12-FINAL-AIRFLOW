import json
import pandas as pd
import glob
import os
from datetime import datetime

def preprocess_newsstand_iframe():
    """
    newsstand_iframe JSON 파일들을 처리하여 가장 최신 파일에서 
    다른 파일들과 중복되지 않는 URL만 Excel로 저장하는 함수
    """
    # crawler_result 디렉토리에서 newsstand_iframe이 포함된 JSON 파일들 찾기
    json_files = glob.glob('/home/son/SKN12-FINAL-AIRFLOW/crawler_result/newsstand_iframe_*.json')
    
    if not json_files:
        print("newsstand_iframe JSON 파일을 찾을 수 없습니다.")
        return
    
    if len(json_files) < 2:
        print("비교할 파일이 부족합니다. 최소 2개 파일이 필요합니다.")
        return
    
    # 파일들을 생성 시간 기준으로 정렬 (가장 최신 파일을 찾기 위해)
    json_files.sort(key=os.path.getctime)
    latest_file = json_files[-1]  # 가장 최신 파일
    other_files = json_files[:-1]  # 나머지 파일들
    
    print(f"가장 최신 파일: {os.path.basename(latest_file)}")
    print(f"비교할 다른 파일들: {len(other_files)}개")
    for file in other_files:
        print(f"  - {os.path.basename(file)}")
    
    # 1. 최신 파일 읽기
    print(f"\n최신 파일 처리 중: {os.path.basename(latest_file)}")
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            latest_data = json.load(f)
    except Exception as e:
        print(f"최신 파일 읽기 실패: {e}")
        return
    
    # 최신 파일이 리스트가 아닌 경우 처리
    if not isinstance(latest_data, list):
        print("최신 파일이 예상된 리스트 형태가 아닙니다.")
        return
    
    print(f"최신 파일에서 {len(latest_data)}개 기사 발견")
    
    # 2. 다른 모든 파일들에서 URL과 title 조합 수집
    print(f"\n다른 파일들에서 기존 URL과 title 조합 수집 중...")
    existing_url_title_pairs = set()
    
    for file_path in other_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                file_pairs = []
                for item in data:
                    url = item.get('url', '').strip()
                    title = item.get('title', '').strip()
                    if url and title:
                        # URL과 title을 조합해서 저장
                        pair = (url, title)
                        existing_url_title_pairs.add(pair)
                        file_pairs.append(pair)
                
                print(f"  - {os.path.basename(file_path)}: {len(file_pairs)}개 URL-title 조합")
            
        except Exception as e:
            print(f"  - {os.path.basename(file_path)}: 읽기 실패 ({e})")
            continue
    
    print(f"총 기존 URL-title 조합: {len(existing_url_title_pairs)}개")
    
    # 3. 최신 파일에서 URL과 title이 모두 중복되지 않는 기사만 필터링
    print(f"\nURL과 title 중복 필터링 중...")
    unique_articles = []
    duplicate_count = 0
    
    for item in latest_data:
        url = item.get('url', '').strip()
        title = item.get('title', '').strip()
        
        if url and title:
            # URL과 title 조합 생성
            current_pair = (url, title)
            
            # URL과 title이 모두 일치하는 조합이 기존에 없는 경우만 포함
            if current_pair not in existing_url_title_pairs:
                processed_item = {
                    '제목': title,
                    'url': url,
                    '언론사': item.get('press', ''),
                    '업로드_날짜': item.get('pub_time', ''),
                    '타입': item.get('type', ''),
                    '요약': item.get('ai_summary', '')
                }
                unique_articles.append(processed_item)
            else:
                duplicate_count += 1
        else:
            # URL이나 title이 없는 경우는 제외
            duplicate_count += 1
    
    print(f"중복 제거 결과:")
    print(f"  - 최신 파일 총 기사: {len(latest_data)}개")
    print(f"  - 중복된 기사: {duplicate_count}개")
    print(f"  - 고유한 기사: {len(unique_articles)}개")
    
    if not unique_articles:
        print("고유한 기사가 없습니다. Excel 파일을 생성하지 않습니다.")
        return
    
    # 4. DataFrame 생성
    df = pd.DataFrame(unique_articles)
    
    # 빈 URL 제거 (추가 안전장치)
    df = df[df['url'].str.strip() != '']
    
    print(f"최종 처리된 기사: {len(df)}개")
    
    # 5. Excel 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'/home/son/SKN12-FINAL-AIRFLOW/crawler_result/newsstand_iframe_unique_{timestamp}.xlsx'
    
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"\n전처리 완료. 저장된 파일: {output_file}")
    
    # 언론사별 통계 출력
    if len(df) > 0:
        print(f"\n언론사별 고유 기사 수:")
        press_counts = df['언론사'].value_counts()
        for press, count in press_counts.items():
            print(f"  {press}: {count}개")
    
    return df

if __name__ == "__main__":
    preprocess_newsstand_iframe()