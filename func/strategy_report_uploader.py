#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
전략 보고서 업로드 모듈
/data/upload/news-strategy-report 엔드포인트에 MD 파일과 뉴스 제목 리스트 업로드
"""

import os
import glob
import re
import requests
from typing import List
import logging

def extract_news_titles_from_md(md_file_path: str) -> List[str]:
    """
    MD 파일의 '8) 출처 매핑 & 신뢰도' 섹션에서 기사제목 컬럼의 뉴스 제목만 추출
    
    Args:
        md_file_path: MD 파일 경로
        
    Returns:
        List[str]: 추출된 뉴스 제목 리스트
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # "8) 출처 매핑 & 신뢰도" 또는 "8. 출처 매핑 & 신뢰도" 섹션 찾기
        patterns = [
            r'## 8\) 출처 매핑 & 신뢰도(.*?)(?=\n##|\*\*결정|$)',
            r'## 8\. 출처 매핑 & 신뢰도(.*?)(?=\n##|\*\*결정|$)'
        ]
        
        match = None
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                break
        
        if not match:
            logging.warning("출처 매핑 & 신뢰도 섹션을 찾을 수 없습니다.")
            return []
        
        section_content = match.group(1)
        logging.info(f"섹션 내용 미리보기: {section_content[:200]}...")
        
        # 새로운 테이블 형식에서 기사제목 컬럼 추출
        # | 뉴스 ID | 출처 | 기사제목 | 발행일 | 핵심팩트 | 신뢰도 |
        news_titles = []
        
        # 정규식으로 테이블 행에서 기사제목 추출
        table_pattern = r'\|\s*\d+\s*\|\s*[^|]+\s*\|\s*([^|]+?)\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*[^|]+\s*\|\s*[HMhm]\s*\|'
        matches = re.findall(table_pattern, section_content)
        
        for match in matches:
            title = match.strip()
            # 기사제목이 유효한지 확인 (한글 포함, 5자 이상, 헤더가 아님)
            if (len(title) > 5 and 
                re.search(r'[가-힣]', title) and 
                title not in ['기사제목', '뉴스 ID', '출처', '발행일', '핵심팩트', '신뢰도']):
                news_titles.append(title)
                logging.info(f"기사제목에서 추출: {title}")
        
        logging.info(f"최종 추출된 뉴스 제목 {len(news_titles)}개: {news_titles}")
        return news_titles
        
    except Exception as e:
        logging.error(f"뉴스 제목 추출 중 오류: {e}")
        return []

def get_upload_host() -> str:
    """업로드 호스트 주소 결정"""
    try:
        # 1. Docker 환경에서 fastapi-app 컨테이너 시도
        host = 'http://fastapi-app:8000'
        response = requests.get(f"{host}/health", timeout=5)
        if response.status_code == 200:
            logging.info(f"✅ Docker 컨테이너 연결 성공: {host}")
            return host
    except:
        pass
    
    try:
        # 2. host.docker.internal 시도
        host = 'http://host.docker.internal:8010'
        response = requests.get(f"{host}/health", timeout=5)
        if response.status_code == 200:
            logging.info(f"✅ host.docker.internal 연결 성공: {host}")
            return host
    except:
        pass
    
    # 3. 기본값으로 localhost 사용
    host = 'http://localhost:8010'
    logging.info(f"🔄 기본 호스트 사용: {host}")
    return host

def upload_strategy_report(file_path: str, news_titles: List[str]) -> bool:
    """
    전략 보고서 파일과 뉴스 제목 리스트를 업로드
    
    Args:
        file_path: 업로드할 MD 파일 경로
        news_titles: 뉴스 제목 리스트
        
    Returns:
        bool: 업로드 성공 여부
    """
    try:
        # 파일 존재 확인
        if not os.path.exists(file_path):
            logging.error(f"파일이 존재하지 않습니다: {file_path}")
            return False
        
        # 파일 크기 확인
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logging.error(f"파일이 비어있습니다: {file_path}")
            return False
        
        logging.info(f"📤 전략 보고서 업로드 시작: {file_path} ({file_size} bytes)")
        logging.info(f"📰 뉴스 제목 {len(news_titles)}개 포함")
        
        # 업로드 호스트 결정
        host = get_upload_host()
        upload_url = f"{host}/data/upload/news-strategy-report"
        
        # ACCESS_TOKEN 확인
        access_token = os.getenv('ACCESS_TOKEN')
        if not access_token:
            logging.error("ACCESS_TOKEN 환경변수가 설정되지 않았습니다.")
            return False
        
        # 헤더 설정
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # 파일과 뉴스 제목 데이터 준비
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'text/markdown')
            }
            
            import json
            data = {
                'news_titles': json.dumps(news_titles, ensure_ascii=False)  # JSON 문자열로 변환
            }
            
            # POST 요청 실행
            logging.info(f"🌐 업로드 요청: {upload_url}")
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
        
        # 응답 처리
        if response.status_code == 200:
            logging.info("✅ 전략 보고서 업로드 성공")
            try:
                result = response.json()
                logging.info(f"📋 서버 응답: {result}")
            except:
                logging.info(f"📋 서버 응답: {response.text}")
            return True
        else:
            logging.error(f"❌ 업로드 실패 (상태코드: {response.status_code})")
            logging.error(f"응답: {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"❌ 업로드 중 오류 발생: {e}")
        return False

def upload_latest_strategy_report() -> bool:
    """
    가장 최근에 생성된 전략 보고서 파일을 업로드
    
    Returns:
        bool: 업로드 성공 여부
    """
    try:
        result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
        
        # pharmaceutical_strategy_report_*.md 파일 검색
        pattern = os.path.join(result_dir, 'pharmaceutical_strategy_report_*.md')
        report_files = glob.glob(pattern)
        
        if not report_files:
            logging.warning("업로드할 전략 보고서 파일이 없습니다.")
            return False
        
        # 가장 최근 파일 선택 (생성 시간 기준)
        latest_file = max(report_files, key=os.path.getctime)
        logging.info(f"📄 업로드 대상 파일: {latest_file}")
        
        # MD 파일에서 뉴스 제목 추출
        news_titles = extract_news_titles_from_md(latest_file)
        
        if not news_titles:
            logging.warning("뉴스 제목을 추출할 수 없습니다. 빈 리스트로 업로드합니다.")
        
        # 업로드 실행
        return upload_strategy_report(latest_file, news_titles)
        
    except Exception as e:
        logging.error(f"❌ 최신 전략 보고서 업로드 중 오류: {e}")
        return False

if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)
    
    print("🚀 전략 보고서 업로드 테스트 시작")
    success = upload_latest_strategy_report()
    
    if success:
        print("✅ 업로드 성공")
    else:
        print("❌ 업로드 실패")