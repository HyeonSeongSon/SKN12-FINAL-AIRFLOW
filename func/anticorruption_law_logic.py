#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import glob
import subprocess
from datetime import datetime
from typing import List, Dict, Optional

# 상수 정의
FILE_PATTERN = "anticorruption_law_*.json"
REQUIRED_FIELDS = ['크롤링_시간', '법명', '시행_법률_정보']

def _get_directory(directory: Optional[str] = None) -> str:
    """디렉토리 경로를 반환하는 헬퍼 함수"""
    if directory:
        return directory
    else:
        # crawler_result 디렉토리를 기본으로 사용 - Docker 볼륨 마운트된 경로 사용
        result_dir = '/home/son/SKN12-FINAL-AIRFLOW/crawler_result'
        os.makedirs(result_dir, exist_ok=True)
        
        return result_dir if os.path.exists(result_dir) else os.path.dirname(os.path.abspath(__file__))

def _find_json_files(directory: str) -> List[str]:
    """anticorruption_law_로 시작하는 JSON 파일들을 찾는 함수"""
    pattern = os.path.join(directory, FILE_PATTERN)
    return glob.glob(pattern)

def _load_file_info(json_files: List[str]) -> List[Dict]:
    """파일들의 크롤링 시간 정보를 로드하는 함수"""
    file_info = []
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            crawling_time = data.get('크롤링_시간')
            if crawling_time:
                try:
                    dt = datetime.fromisoformat(crawling_time)
                    file_info.append({
                        'path': file_path,
                        'crawling_time': dt,
                        'crawling_time_str': crawling_time
                    })
                except ValueError as e:
                    print(f"시간 변환 오류 - {os.path.basename(file_path)}: {e}")
            else:
                print(f"크롤링_시간 필드 없음 - {os.path.basename(file_path)}")
                
        except Exception as e:
            print(f"파일 읽기 오류 - {os.path.basename(file_path)}: {e}")
    
    return file_info

def _create_no_action_result(message: str, files: List[str]) -> Dict:
    """작업하지 않을 때의 결과를 생성하는 함수"""
    return {
        "status": "no_action",
        "message": message,
        "deleted_files": [],
        "kept_files": files
    }

def check_law_info_changes(directory: Optional[str] = None) -> bool:
    """
    anticorruption_law_ JSON 파일들의 '법명'과 '시행_법률_정보' 필드를 비교
    
    Args:
        directory: 검색할 디렉토리 경로
    
    Returns:
        bool: 차이가 있으면 True, 없으면 False
    """
    directory = _get_directory(directory)
    json_files = _find_json_files(directory)
    
    if len(json_files) < 2:
        print(f"비교할 파일이 충분하지 않습니다. (파일 수: {len(json_files)})")
        return False
    
    # 각 파일의 법명, 시행_법률_정보 수집
    law_info_list = []
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            law_info_list.append({
                'file': os.path.basename(file_path),
                'law_name': data.get('법명', ''),
                'enforcement_info': data.get('시행_법률_정보', '')
            })
            
        except Exception as e:
            print(f"파일 읽기 오류 - {os.path.basename(file_path)}: {e}")
    
    if len(law_info_list) < 2:
        print("유효한 파일이 2개 미만입니다.")
        return False
    
    # 첫 번째 파일을 기준으로 비교
    base_info = law_info_list[0]
    print(f"기준 파일: {base_info['file']}")
    print(f"기준 법명: {base_info['law_name']}")
    print(f"기준 시행정보: {base_info['enforcement_info']}\n")
    
    has_differences = False
    
    for current_info in law_info_list[1:]:
        law_name_diff = current_info['law_name'] != base_info['law_name']
        enforcement_diff = current_info['enforcement_info'] != base_info['enforcement_info']
        
        if law_name_diff or enforcement_diff:
            has_differences = True
            print(f"차이점 발견 - {current_info['file']}:")
            
            if law_name_diff:
                print(f"  법명 차이:")
                print(f"    기준: {base_info['law_name']}")
                print(f"    현재: {current_info['law_name']}")
            
            if enforcement_diff:
                print(f"  시행정보 차이:")
                print(f"    기준: {base_info['enforcement_info']}")
                print(f"    현재: {current_info['enforcement_info']}")
            print()
        else:
            print(f"차이 없음 - {current_info['file']}")
    
    return has_differences

def delete_old_files(directory: Optional[str] = None) -> Dict:
    """
    오래된 파일들을 삭제하고 최신 파일 1개만 유지
    
    Args:
        directory: 검색할 디렉토리 경로
    
    Returns:
        dict: 삭제 결과 정보
    """
    directory = _get_directory(directory)
    json_files = _find_json_files(directory)
    
    # 파일이 1개 이하면 삭제하지 않음
    if len(json_files) <= 1:
        return _create_no_action_result(
            f"파일 수({len(json_files)})가 1개 이하이므로 삭제하지 않음",
            json_files
        )
    
    file_info = _load_file_info(json_files)
    
    # 유효한 파일이 1개 이하면 삭제하지 않음
    if len(file_info) <= 1:
        return _create_no_action_result(
            f"유효한 파일 수({len(file_info)})가 1개 이하이므로 삭제하지 않음",
            [info['path'] for info in file_info]
        )
    
    # 크롤링_시간 기준으로 정렬 (최신순)
    file_info.sort(key=lambda x: x['crawling_time'], reverse=True)
    
    # 최신 1개 파일 유지, 나머지 삭제
    files_to_keep = file_info[:1]
    files_to_delete = file_info[1:]
    
    # 파일 삭제 실행
    deleted_files = []
    failed_deletions = []
    
    for file_item in files_to_delete:
        try:
            os.remove(file_item['path'])
            deleted_files.append({
                'path': file_item['path'],
                'crawling_time': file_item['crawling_time_str']
            })
            print(f"삭제됨: {os.path.basename(file_item['path'])} (크롤링시간: {file_item['crawling_time_str']})")
        except Exception as e:
            failed_deletions.append({
                'path': file_item['path'],
                'error': str(e)
            })
            print(f"삭제 실패: {os.path.basename(file_item['path'])} - {e}")
    
    return {
        "status": "success" if not failed_deletions else "partial_success",
        "message": f"{len(deleted_files)}개 파일 삭제 완료, {len(files_to_keep)}개 파일 유지",
        "deleted_files": deleted_files,
        "kept_files": [{'path': info['path'], 'crawling_time': info['crawling_time_str']} for info in files_to_keep],
        "failed_deletions": failed_deletions
    }

def delete_newest_file(directory: Optional[str] = None) -> Dict:
    """
    가장 최신 파일을 삭제하고 이전 파일들을 유지
    
    Args:
        directory: 검색할 디렉토리 경로
    
    Returns:
        dict: 삭제 결과 정보
    """
    directory = _get_directory(directory)
    json_files = _find_json_files(directory)
    
    # 파일이 1개 이하면 삭제하지 않음
    if len(json_files) <= 1:
        return _create_no_action_result(
            f"파일 수({len(json_files)})가 1개 이하이므로 삭제하지 않음",
            json_files
        )
    
    file_info = _load_file_info(json_files)
    
    # 유효한 파일이 1개 이하면 삭제하지 않음
    if len(file_info) <= 1:
        return _create_no_action_result(
            f"유효한 파일 수({len(file_info)})가 1개 이하이므로 삭제하지 않음",
            [info['path'] for info in file_info]
        )
    
    # 크롤링_시간 기준으로 정렬 (최신순)
    file_info.sort(key=lambda x: x['crawling_time'], reverse=True)
    
    # 가장 최신 파일을 삭제할 파일로, 나머지를 유지할 파일로 설정
    newest_file = file_info[0]
    files_to_keep = file_info[1:]
    
    # 최신 파일 삭제 실행
    try:
        os.remove(newest_file['path'])
        deleted_files = [{
            'path': newest_file['path'],
            'crawling_time': newest_file['crawling_time_str']
        }]
        print(f"최신 파일 삭제됨: {os.path.basename(newest_file['path'])} (크롤링시간: {newest_file['crawling_time_str']})")
        
        return {
            "status": "success",
            "message": f"최신 파일 1개 삭제 완료, {len(files_to_keep)}개 파일 유지",
            "deleted_files": deleted_files,
            "kept_files": [{'path': info['path'], 'crawling_time': info['crawling_time_str']} for info in files_to_keep],
            "failed_deletions": []
        }
    except Exception as e:
        print(f"최신 파일 삭제 실패: {os.path.basename(newest_file['path'])} - {e}")
        return {
            "status": "failed",
            "message": "최신 파일 삭제 실패",
            "deleted_files": [],
            "kept_files": [{'path': info['path'], 'crawling_time': info['crawling_time_str']} for info in file_info],
            "failed_deletions": [{'path': newest_file['path'], 'error': str(e)}]
        }

def process_law_files_by_changes(directory: Optional[str] = None) -> Dict:
    """
    법명과 시행_법률_정보 변경 여부에 따라 파일 처리
    - True (변경사항 있음): 오래된 파일들 삭제
    - False (변경사항 없음): 최신 파일 삭제
    
    Args:
        directory: 검색할 디렉토리 경로
    
    Returns:
        dict: 처리 결과 정보
    """
    print("=== 법률 정보 변경 여부 확인 ===")
    has_changes = check_law_info_changes(directory)
    
    print(f"\n변경 여부: {'변경사항 있음' if has_changes else '변경사항 없음'}")
    
    if has_changes:
        print("\n변경사항이 있으므로 오래된 파일들을 삭제합니다...")
        result = delete_old_files(directory)
        result['action'] = "delete_old_files"
        result['reason'] = "법명 또는 시행_법률_정보에 변경사항이 있음"
    else:
        print("\n변경사항이 없으므로 최신 파일을 삭제합니다...")
        result = delete_newest_file(directory)
        result['action'] = "delete_newest_file"
        result['reason'] = "법명과 시행_법률_정보에 변경사항이 없음"
    
    return result

def main():
    """메인 실행 함수"""
    print("anticorruption_law_ JSON 파일 처리를 시작합니다...")
    
    try:
        # 법률 정보 변경 여부에 따른 파일 처리
        result = process_law_files_by_changes()
        
        print(f"\n=== 처리 결과 ===")
        print(f"수행된 작업: {result.get('action', 'N/A')}")
        print(f"처리 이유: {result.get('reason', 'N/A')}")
        print(f"상태: {result['status']}")
        print(f"메시지: {result['message']}")
        
        if result['deleted_files']:
            print(f"\n삭제된 파일 ({len(result['deleted_files'])}개):")
            for file_info in result['deleted_files']:
                print(f"  - {os.path.basename(file_info['path'])} (크롤링시간: {file_info['crawling_time']})")
        
        if result['kept_files']:
            print(f"\n유지된 파일 ({len(result['kept_files'])}개):")
            for file_info in result['kept_files']:
                if isinstance(file_info, dict):
                    print(f"  - {os.path.basename(file_info['path'])} (크롤링시간: {file_info['crawling_time']})")
                else:
                    print(f"  - {os.path.basename(file_info)}")
        
        if result.get('failed_deletions'):
            print(f"\n삭제 실패 파일 ({len(result['failed_deletions'])}개):")
            for fail_info in result['failed_deletions']:
                print(f"  - {os.path.basename(fail_info['path'])}: {fail_info['error']}")
                
    except Exception as e:
        print(f"처리 중 오류 발생: {e}")

if __name__ == "__main__":
    main()