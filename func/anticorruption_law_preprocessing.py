import json
import pandas as pd
import glob
import os
from datetime import datetime

def preprocess_anticorruption_law():
    """
    anticorruption_law JSON 파일들을 처리하여 DataFrame으로 변환하고 Excel 파일로 저장하는 함수
    """
    # crawler_result 디렉토리에서 anticorruption_law로 시작하는 JSON 파일들 찾기
    json_files = glob.glob('/home/son/SKN12-FINAL-AIRFLOW/crawler_result/anticorruption_law_*.json')
    
    if not json_files:
        print("anticorruption_law JSON 파일을 찾을 수 없습니다.")
        return
    
    print(f"총 {len(json_files)}개의 파일을 처리합니다.")
    
    # 모든 데이터를 저장할 리스트
    all_data = []
    
    # 각 JSON 파일 처리
    for json_file in json_files:
        print(f"처리 중: {os.path.basename(json_file)}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # JSON 파일에서 필요한 기본 정보 추출
            법명 = data.get('법명', '')
            법률정보 = data.get('시행_법률_정보', '')
            소스_URL = data.get('소스_URL', '')
            pgroup_텍스트 = data.get('pgroup_텍스트', [])
            
            if not pgroup_텍스트:
                print(f"  - {os.path.basename(json_file)}: pgroup_텍스트가 없습니다.")
                continue
            
            # pgroup_텍스트 파싱
            current_장 = ""
            
            for text in pgroup_텍스트:
                text = text.strip()
                
                # 제n장 패턴 확인
                if text.startswith('제') and '장' in text and not '조(' in text:
                    current_장 = text
                    continue
                
                # 제n조(...) 패턴 확인
                if text.startswith('제') and '조(' in text:
                    # ')' 첫 번째 등장 위치로 split
                    close_paren_index = text.find(')')
                    if close_paren_index != -1:
                        조문_part = text[:close_paren_index + 1]  # 제n조(...) 부분
                        내용_part = text[close_paren_index + 1:]  # 나머지 부분
                        
                        # 조문에는 현재 장 + 조문 결합
                        if current_장:
                            조문 = f"{current_장} {조문_part}"
                        else:
                            조문 = 조문_part
                        
                        # DataFrame 행 생성
                        processed_item = {
                            '법명': 법명,
                            '법률정보': 법률정보,
                            '조문': 조문,
                            '내용': 내용_part.strip(),
                            '소스_URL': 소스_URL
                        }
                        all_data.append(processed_item)
            
            print(f"  - {os.path.basename(json_file)}: {len([item for item in all_data if item['법명'] == 법명])}개 조문 처리")
            
        except Exception as e:
            print(f"파일 {json_file} 처리 중 오류 발생: {e}")
            continue
    
    if not all_data:
        print("처리할 데이터가 없습니다.")
        return
    
    # DataFrame 생성
    df = pd.DataFrame(all_data)
    
    print(f"총 {len(df)}개의 조문이 처리되었습니다.")
    
    # 빈 내용이 있는 행들 확인 및 정리
    empty_content_count = len(df[df['내용'].str.strip() == ''])
    if empty_content_count > 0:
        print(f"빈 내용이 있는 조문 {empty_content_count}개 발견")
        df = df[df['내용'].str.strip() != '']
        print(f"빈 내용 제거 후 {len(df)}개 조문")
    
    # Excel 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'/home/son/SKN12-FINAL-AIRFLOW/crawler_result/anticorruption_law_processed_{timestamp}.xlsx'
    
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"전처리 완료. 저장된 파일: {output_file}")
    
    # 법률별 통계 출력
    print("\n법률별 조문 수:")
    law_counts = df['법명'].value_counts()
    for law, count in law_counts.items():
        print(f"  {law}: {count}개")
    
    return df

if __name__ == "__main__":
    preprocess_anticorruption_law()