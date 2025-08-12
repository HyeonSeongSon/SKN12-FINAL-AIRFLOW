#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
제약영업회사 뉴스 전략 보고서 생성기 사용 예제
"""

import os
from dotenv import load_dotenv
from news_report_generator import NewsReportGenerator

def example_basic_usage():
    """기본 사용 예제"""
    print("=== 기본 사용 예제 ===")
    
    # .env 파일에서 API 키 자동 로드됨
    
    try:
        # 보고서 생성기 초기화
        generator = NewsReportGenerator()
        
        # 전체 프로세스 실행
        result_path = generator.generate_and_save_report()
        print(f"✅ 보고서 생성 완료: {result_path}")
        
    except ValueError as e:
        print(f"❌ API 키 설정 오류: {e}")
        print("/home/son/.env 파일에 OPENAI_API_KEY를 설정하거나 직접 API 키를 전달해주세요.")
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")


def example_step_by_step():
    """단계별 실행 예제"""
    print("\n=== 단계별 실행 예제 ===")
    
    try:
        # API 키와 함께 초기화
        generator = NewsReportGenerator()
        
        # 1단계: 뉴스 데이터 로딩
        print("1단계: 뉴스 데이터 로딩...")
        summaries = generator.load_news_summaries()
        
        total_news = sum(len(items) for items in summaries.values())
        print(f"로딩된 뉴스: {total_news}개")
        
        # 2단계: 보고서 생성
        print("\n2단계: 전략 보고서 생성...")
        report = generator.generate_report(summaries)
        print("보고서 생성 완료")
        
        # 3단계: 보고서 저장
        print("\n3단계: 보고서 저장...")
        filepath = generator.save_report(report, "custom_report.md")
        print(f"✅ 보고서 저장 완료: {filepath}")
        
        # 보고서 일부 미리보기
        print("\n=== 보고서 미리보기 ===")
        print(report[:500] + "...")
        
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")


def example_custom_api_key():
    """커스텀 API 키 사용 예제"""
    print("\n=== 커스텀 API 키 사용 예제 ===")
    
    # 실제 사용시에는 보안을 위해 환경변수나 설정 파일 사용 권장
    api_key = "your-openai-api-key-here"
    
    try:
        # API 키를 직접 전달
        generator = NewsReportGenerator(openai_api_key=api_key)
        result_path = generator.generate_and_save_report()
        print(f"✅ 커스텀 API 키로 보고서 생성 완료: {result_path}")
        
    except ValueError as e:
        print(f"❌ API 키 오류: {e}")
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")


def check_environment():
    """환경 설정 확인"""
    print("\n=== 환경 설정 확인 ===")
    
    # .env 파일 로드
    load_dotenv('/home/son/.env')
    
    # OpenAI API 키 확인
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        print("✅ OPENAI_API_KEY 설정됨 (from .env file)")
        print(f"   키 앞부분: {api_key[:10]}...")
    else:
        print("❌ OPENAI_API_KEY가 설정되지 않음")
        print("   /home/son/.env 파일에 다음과 같이 추가하세요:")
        print("   OPENAI_API_KEY=your-api-key-here")
    
    # 크롤러 결과 디렉토리 확인
    crawler_path = "/home/son/SKN12-FINAL-AIRFLOW/crawler_result"
    if os.path.exists(crawler_path):
        files = os.listdir(crawler_path)
        print(f"✅ 크롤러 결과 디렉토리 존재: {len(files)}개 파일")
    else:
        print("❌ 크롤러 결과 디렉토리가 존재하지 않음")
    
    # crawler_result 디렉토리 확인 (보고서 저장 위치)
    save_path = "/home/son/SKN12-FINAL-AIRFLOW/crawler_result"
    if os.path.exists(save_path):
        print("✅ crawler_result 디렉토리 존재 (보고서 저장 위치)")
    else:
        print("❌ crawler_result 디렉토리가 존재하지 않음")
        try:
            os.makedirs(save_path)
            print("✅ crawler_result 디렉토리 생성 완료")
        except Exception as e:
            print(f"❌ crawler_result 디렉토리 생성 실패: {e}")


if __name__ == "__main__":
    print("🔍 제약영업회사 뉴스 전략 보고서 생성기 예제")
    print("=" * 50)
    
    # 환경 확인
    check_environment()
    
    # 기본 사용 예제
    example_basic_usage()
    
    # 단계별 실행 예제 (주석 처리 - 필요시 활성화)
    # example_step_by_step()
    
    # 커스텀 API 키 예제 (주석 처리 - 필요시 활성화)
    # example_custom_api_key()
    
    print("\n" + "=" * 50)
    print("예제 실행 완료!")