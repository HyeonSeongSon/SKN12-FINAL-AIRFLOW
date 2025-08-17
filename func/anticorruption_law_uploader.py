import os
import glob
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def get_upload_host():
    """
    Docker 컨테이너 환경에서 호스트에 접근하기 위한 적절한 URL을 반환
    """
    import socket
    
    # 먼저 fastapi-app 컨테이너명으로 시도 (Docker 네트워크 내에서)
    try:
        socket.gethostbyname('fastapi-app')
        print("[DEBUG] fastapi-app 호스트 해석 성공, fastapi-app:8000 사용")
        return 'http://fastapi-app:8000'
    except socket.gaierror:
        pass
    
    # 다음으로 host.docker.internal 시도
    try:
        socket.gethostbyname('host.docker.internal')
        # host.docker.internal이 해석되면 연결 테스트
        test_response = requests.get('http://host.docker.internal:8010/health', timeout=5)
        if test_response.status_code in [200, 405]:
            return 'http://host.docker.internal:8010'
    except (socket.gaierror, requests.exceptions.RequestException):
        pass
    
    # 기본값으로 localhost 사용
    return 'http://localhost:8010'

def upload_latest_anticorruption_file():
    """
    crawler_result 디렉터리에서 anticorruption_law_가 포함된 가장 최신의 Excel 파일을 찾아서
    localhost:8010/data/upload/laws 엔드포인트로 업로드하는 함수
    """
    # anticorruption_law_processed 파일 검색 패턴
    search_pattern = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result/*anticorruption_law_processed*.xlsx'
    
    # crawler_result 디렉터리에서 anticorruption_law Excel 파일들 찾기
    excel_files = glob.glob(search_pattern)
    
    if not excel_files:
        print("anticorruption_law_processed Excel 파일을 찾을 수 없습니다.")
        return False
    
    # 파일들을 생성 시간 기준으로 정렬하여 가장 최신 파일 찾기
    excel_files.sort(key=os.path.getctime)
    latest_file = excel_files[-1]
    
    file_name = os.path.basename(latest_file)
    print(f"[ANTICORRUPTION_LAW] 업로드할 최신 파일: {file_name}")
    
    # 파일 크기 확인
    file_size = os.path.getsize(latest_file)
    print(f"파일 크기: {file_size:,} bytes")
    
    # API 엔드포인트 URL (호스트 자동 감지)
    base_url = get_upload_host()
    upload_url = f"{base_url}/data/upload/laws"
    
    # 환경변수에서 ACCESS_TOKEN 가져오기 (없으면 None)
    access_token = os.getenv('ACCESS_TOKEN')
    
    # 헤더 설정
    headers = {}
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'
        print("인증 토큰을 사용하여 업로드합니다.")
    else:
        print("경고: ACCESS_TOKEN이 설정되지 않았습니다. .env 파일에 ACCESS_TOKEN을 추가하세요.")
    
    try:
        # 파일을 multipart/form-data로 업로드
        with open(latest_file, 'rb') as file:
            files = {
                'file': (file_name, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            print(f"[ANTICORRUPTION_LAW] 파일 업로드 시작: {upload_url}")
            response = requests.post(upload_url, files=files, headers=headers, timeout=300)
            
            if response.status_code == 200:
                print(f"[ANTICORRUPTION_LAW] 파일 업로드 성공!")
                print(f"응답: {response.text}")
                return True
            else:
                print(f"[ANTICORRUPTION_LAW] 파일 업로드 실패. 상태 코드: {response.status_code}")
                print(f"응답: {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        print("연결 오류: localhost:8010 서버에 연결할 수 없습니다.")
        print("서버가 실행 중인지 확인하세요.")
        return False
    except requests.exceptions.Timeout:
        print("타임아웃 오류: 파일 업로드에 시간이 너무 오래 걸립니다.")
        return False
    except Exception as e:
        print(f"업로드 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    print("부패방지법 데이터 파일 업로드를 시작합니다.")
    success = upload_latest_anticorruption_file()
    
    if success:
        print("[ANTICORRUPTION_LAW] 업로드 완료!")
    else:
        print("[ANTICORRUPTION_LAW] 업로드 실패!")