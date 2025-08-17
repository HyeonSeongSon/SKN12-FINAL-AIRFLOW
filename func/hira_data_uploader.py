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
    
    print("[DEBUG] get_upload_host() 함수 시작")
    
    # 먼저 fastapi-app 컨테이너명으로 시도 (Docker 네트워크 내에서)
    try:
        print("[DEBUG] fastapi-app 호스트 해석 시도...")
        host_ip = socket.gethostbyname('fastapi-app')
        print(f"[DEBUG] fastapi-app IP: {host_ip}")
        print("[DEBUG] fastapi-app:8000 직접 사용 (네트워크 연결됨)")
        return 'http://fastapi-app:8000'
    except socket.gaierror as e:
        print(f"[DEBUG] fastapi-app 호스트 해석 실패: {e}")
    
    # 다음으로 host.docker.internal 시도
    try:
        print("[DEBUG] host.docker.internal 호스트 해석 시도...")
        host_ip = socket.gethostbyname('host.docker.internal')
        print(f"[DEBUG] host.docker.internal IP: {host_ip}")
        
        # host.docker.internal이 해석되면 연결 테스트
        print("[DEBUG] host.docker.internal:8010/health 연결 테스트...")
        test_response = requests.get('http://host.docker.internal:8010/health', timeout=5)
        print(f"[DEBUG] host.docker.internal 응답 코드: {test_response.status_code}")
        
        if test_response.status_code in [200, 405]:
            print("[DEBUG] host.docker.internal 연결 성공!")
            return 'http://host.docker.internal:8010'
    except socket.gaierror as e:
        print(f"[DEBUG] host.docker.internal 호스트 해석 실패: {e}")
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] host.docker.internal 연결 실패: {e}")
    
    # 기본값으로 localhost 사용
    print("[DEBUG] 기본값 localhost:8010 사용")
    return 'http://localhost:8010'

def upload_latest_hira_file():
    """
    crawler_result 디렉토리에서 hira_data가 포함된 가장 최신의 Excel 파일을 찾아서
    localhost:8010/data/upload/insurance-criteria 엔드포인트로 업로드하는 함수
    """
    # hira_data 파일 검색 패턴
    search_pattern = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result/*hira_data*.xlsx'
    
    # crawler_result 디렉토리에서 hira_data Excel 파일들 찾기
    excel_files = glob.glob(search_pattern)
    
    if not excel_files:
        print("hira_data Excel 파일을 찾을 수 없습니다.")
        return False
    
    # 파일들을 생성 시간 기준으로 정렬하여 가장 최신 파일 찾기
    excel_files.sort(key=os.path.getctime)
    latest_file = excel_files[-1]
    
    file_name = os.path.basename(latest_file)
    print(f"[HIRA_DATA] 업로드할 최신 파일: {file_name}")
    
    # 파일 크기 확인
    file_size = os.path.getsize(latest_file)
    print(f"파일 크기: {file_size:,} bytes")
    
    # API 엔드포인트 URL (호스트 자동 감지)
    base_url = get_upload_host()
    upload_url = f"{base_url}/data/upload/insurance-criteria"
    
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
            
            print(f"[HIRA_DATA] 파일 업로드 시작: {upload_url}")
            response = requests.post(upload_url, files=files, headers=headers, timeout=300)
            
            if response.status_code == 200:
                print(f"[HIRA_DATA] 파일 업로드 성공!")
                print(f"응답: {response.text}")
                return True
            else:
                print(f"[HIRA_DATA] 파일 업로드 실패. 상태 코드: {response.status_code}")
                print(f"응답: {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        print(f"연결 오류: {base_url} 서버에 연결할 수 없습니다.")
        print("서버가 실행 중인지 확인하세요.")
        return False
    except requests.exceptions.Timeout:
        print("타임아웃 오류: 파일 업로드에 시간이 너무 오래 걸립니다.")
        return False
    except Exception as e:
        print(f"업로드 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    print("HIRA 데이터 파일 업로드를 시작합니다.")
    success = upload_latest_hira_file()
    
    if success:
        print("[HIRA_DATA] 업로드 완료!")
    else:
        print("[HIRA_DATA] 업로드 실패!")