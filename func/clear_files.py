import os
import re
from datetime import datetime
from collections import defaultdict


def _clear_files_by_patterns(patterns, description):
    """
    지정된 패턴들의 파일이 3개 초과하면 최근 3개만 남기고 나머지 삭제
    
    Args:
        patterns: 대상 파일 패턴들 (리스트)
        description: 로그에 표시할 설명
    """
    crawler_result_path = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
    
    try:
        # 디렉토리가 존재하는지 확인
        if not os.path.exists(crawler_result_path):
            print(f"❌ 디렉토리가 존재하지 않습니다: {crawler_result_path}")
            return
        
        # 파일 목록 가져오기
        all_files = os.listdir(crawler_result_path)
        print(f"📁 {description} - 전체 파일 개수: {len(all_files)}")
        
        # 각 패턴별로 파일 그룹화
        file_groups = defaultdict(list)
        
        for filename in all_files:
            # JSON 파일만 처리
            if not filename.endswith('.json'):
                continue
                
            # 대상 패턴에 해당하는 파일인지 확인
            for pattern in patterns:
                if filename.startswith(pattern):
                    # 파일의 전체 경로
                    file_path = os.path.join(crawler_result_path, filename)
                    
                    # 파일 생성 시간 가져오기
                    creation_time = os.path.getctime(file_path)
                    
                    # 파일명에서 날짜 정보 추출 시도
                    date_match = re.search(r'(\d{8})', filename)
                    if date_match:
                        try:
                            # 파일명의 날짜를 우선 사용
                            date_str = date_match.group(1)
                            file_date = datetime.strptime(date_str, '%Y%m%d')
                            sort_key = file_date.timestamp()
                        except:
                            # 날짜 파싱 실패 시 파일 생성 시간 사용
                            sort_key = creation_time
                    else:
                        # 날짜 정보가 없으면 파일 생성 시간 사용
                        sort_key = creation_time
                    
                    file_groups[pattern].append({
                        'filename': filename,
                        'path': file_path,
                        'sort_key': sort_key,
                        'creation_time': creation_time
                    })
                    break
        
        # 각 그룹별로 파일 정리
        total_deleted = 0
        
        for pattern, files in file_groups.items():
            if len(files) <= 3:
                print(f"✅ {pattern}: {len(files)}개 파일 - 정리 불필요")
                continue
            
            print(f"🔍 {pattern}: {len(files)}개 파일 발견")
            
            # 최신 순으로 정렬 (sort_key 기준 내림차순)
            files.sort(key=lambda x: x['sort_key'], reverse=True)
            
            # 최신 3개를 제외한 나머지 파일들
            files_to_delete = files[3:]
            
            print(f"📋 보존할 파일 (최신 3개):")
            for i, file_info in enumerate(files[:3]):
                date_str = datetime.fromtimestamp(file_info['sort_key']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {i+1}. {file_info['filename']} ({date_str})")
            
            print(f"🗑️  삭제할 파일 ({len(files_to_delete)}개):")
            for file_info in files_to_delete:
                try:
                    os.remove(file_info['path'])
                    date_str = datetime.fromtimestamp(file_info['sort_key']).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  ✅ 삭제: {file_info['filename']} ({date_str})")
                    total_deleted += 1
                except Exception as e:
                    print(f"  ❌ 삭제 실패: {file_info['filename']} - {str(e)}")
            
            print()
        
        print(f"🎉 {description} 정리 완료! 총 {total_deleted}개 파일 삭제됨")
        
    except Exception as e:
        print(f"❌ {description} 정리 중 오류 발생: {str(e)}")


def clear_medical_news_files():
    """
    의료 뉴스 관련 파일 정리
    대상: medical_top_trending_news_, medical_recent_news_
    """
    patterns = ['medical_top_trending_news_', 'medical_recent_news_']
    _clear_files_by_patterns(patterns, "의료 뉴스 파일")


def clear_newsstand_files():
    """
    뉴스스탠드 관련 파일 정리
    대상: newsstand_iframe_
    """
    patterns = ['newsstand_iframe_']
    _clear_files_by_patterns(patterns, "뉴스스탠드 파일")


def clear_all_files():
    """
    모든 대상 파일 정리
    """
    print("🧹 전체 파일 정리 시작")
    print("=" * 50)
    clear_medical_news_files()
    print()
    clear_newsstand_files()


def _get_file_status_by_patterns(patterns, description):
    """
    지정된 패턴들의 현재 파일 상태 확인
    
    Args:
        patterns: 대상 파일 패턴들 (리스트)
        description: 로그에 표시할 설명
    """
    crawler_result_path = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
    
    try:
        if not os.path.exists(crawler_result_path):
            print(f"❌ 디렉토리가 존재하지 않습니다: {crawler_result_path}")
            return
        
        all_files = os.listdir(crawler_result_path)
        file_groups = defaultdict(list)
        
        for filename in all_files:
            if not filename.endswith('.json'):
                continue
                
            for pattern in patterns:
                if filename.startswith(pattern):
                    file_path = os.path.join(crawler_result_path, filename)
                    creation_time = os.path.getctime(file_path)
                    
                    date_match = re.search(r'(\d{8})', filename)
                    if date_match:
                        try:
                            date_str = date_match.group(1)
                            file_date = datetime.strptime(date_str, '%Y%m%d')
                            sort_key = file_date.timestamp()
                        except:
                            sort_key = creation_time
                    else:
                        sort_key = creation_time
                    
                    file_groups[pattern].append({
                        'filename': filename,
                        'sort_key': sort_key
                    })
                    break
        
        print(f"📊 {description} 상태:")
        for pattern, files in file_groups.items():
            files.sort(key=lambda x: x['sort_key'], reverse=True)
            print(f"  {pattern}: {len(files)}개")
            for i, file_info in enumerate(files):
                date_str = datetime.fromtimestamp(file_info['sort_key']).strftime('%Y-%m-%d')
                status = "✅ 보존" if i < 3 else "🗑️ 삭제 대상"
                print(f"    {file_info['filename']} ({date_str}) - {status}")
            print()
            
    except Exception as e:
        print(f"❌ {description} 상태 확인 중 오류 발생: {str(e)}")


def get_medical_news_status():
    """
    의료 뉴스 파일 상태 확인
    """
    patterns = ['medical_top_trending_news_', 'medical_recent_news_']
    _get_file_status_by_patterns(patterns, "의료 뉴스 파일")


def get_newsstand_status():
    """
    뉴스스탠드 파일 상태 확인
    """
    patterns = ['newsstand_iframe_']
    _get_file_status_by_patterns(patterns, "뉴스스탠드 파일")


def get_all_status():
    """
    모든 파일 상태 확인
    """
    print("📊 전체 파일 상태 확인")
    print("=" * 50)
    get_medical_news_status()
    get_newsstand_status()


if __name__ == "__main__":
    print("🧹 크롤러 결과 파일 정리 도구")
    print("=" * 50)
    
    # 현재 상태 확인
    print("1️⃣ 현재 파일 상태 확인:")
    get_all_status()
    
    print("\n2️⃣ 파일 정리 실행:")
    clear_all_files()