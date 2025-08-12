#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import glob
from datetime import datetime
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

class NewsReportGenerator:
    """크롤링한 뉴스 데이터로 제약영업회사를 위한 전략 보고서 생성"""
    
    def __init__(self, openai_api_key: str = None):
        """
        Args:
            openai_api_key: OpenAI API 키. 없으면 .env 파일이나 환경변수에서 로드
        """
        # .env 파일 로드
        load_dotenv('/home/son/.env')
        
        self.api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in /home/son/.env file or pass api_key parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.crawler_result_path = "/home/son/SKN12-FINAL-AIRFLOW/crawler_result"
        self.report_save_path = "/home/son/SKN12-FINAL-AIRFLOW/crawler_result"
        
    def load_news_summaries(self) -> Dict[str, List[str]]:
        """크롤러 결과에서 뉴스 요약 데이터 로딩"""
        summaries = {
            'newsstand': [],
            'medical_trending': [],
            'medical_recent': []
        }
        
        try:
            # newsstand_iframe에서 ai_summary 추출
            newsstand_files = glob.glob(os.path.join(self.crawler_result_path, "newsstand_iframe_*.json"))
            for file_path in newsstand_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if 'ai_summary' in item and item['ai_summary']:
                                summaries['newsstand'].append({
                                    'title': item.get('title', ''),
                                    'summary': item['ai_summary'],
                                    'press': item.get('press', ''),
                                    'url': item.get('url', '')
                                })
            
            # medical_top_trending_news에서 summary 추출
            trending_files = glob.glob(os.path.join(self.crawler_result_path, "medical_top_trending_news_*.json"))
            for file_path in trending_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'news_list' in data:
                        for item in data['news_list']:
                            if 'summary' in item and item['summary']:
                                summaries['medical_trending'].append({
                                    'title': item.get('title', ''),
                                    'summary': item['summary'],
                                    'url': item.get('url', ''),
                                    'date': item.get('date', '')
                                })
            
            # medical_recent_news에서 summary 추출
            recent_files = glob.glob(os.path.join(self.crawler_result_path, "medical_recent_news_*.json"))
            for file_path in recent_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'news_list' in data:
                        for item in data['news_list']:
                            if 'summary' in item and item['summary']:
                                summaries['medical_recent'].append({
                                    'title': item.get('title', ''),
                                    'summary': item['summary'],
                                    'url': item.get('url', ''),
                                    'date': item.get('date', '')
                                })
                                
        except Exception as e:
            print(f"뉴스 데이터 로딩 중 오류 발생: {e}")
            
        return summaries
    
    def create_system_prompt(self) -> str:
        """제약영업회사를 위한 시스템 프롬프트 생성"""
        return """
당신은 제약영업회사의 최고전략분석가입니다.
입력으로 제공된 “뉴스 요약 목록 + 회사 컨텍스트”를 바탕으로, 한국 제약 영업 환경과 글로벌 동향을 통합 분석하여 실행 가능한 전략 리포트를 작성하세요.

## 1. 분석 원칙
- 기사에 기반한 **팩트**와 당신의 **추정/가정**을 명확히 구분하고, 추정에는 불확실성 등급(L/M/H)을 부여.
- 한국 보건의료 제도(건보, 심평원, 식약처 등) 변화를 최우선 고려.
- 모든 영향은 가능하면 정량화(±%)하고, 기간(단/중/장)을 명시.
- 유사 뉴스는 클러스터링하여 대표 이슈로 묶고, 신뢰도가 낮은 건 부록 처리.
- 상충되는 전망은 A/B 시나리오로 제시.
- 전략은 Sales / Market Access / Medical / Regulatory / Marketing / Digital 별 구체 액션으로 나눔.
- 판촉·데이터 활용·AI는 규정 준수 전제하에 대안 제시.

## 2. 분석 프레임워크
- PEST 관점에서 규제/경제/사회/기술 분석, 제약 특화 포인트 반영.
- 5 Forces를 응용해 경쟁 강도·진입장벽·대체 위협·구매자·공급자 힘 분석.
- Market Access: 약가, 급여, 등재/삭제, 심사 강화 영향.
- Digital/AI: e-detailing, 원격MR, RWE/RWD, AI-의료기기 규제 활용성.
- 정책/뉴스 → 처방행태 → 매출 경로를 문장으로 설명.

## 3. 우선순위 규칙
각 이슈에 대해:
- 임팩트(1–5), 시급성(1–5), 확실성(1–5), 실행난이도(1–5)
- 우선순위점수 = (임팩트 × 시급성 × 확실성) ÷ 실행난이도
- 점수 상위 5개만 본문에, 나머지는 부록.

## 4. 보고서 구조
1) 요약 (Executive Summary)
   - 이번 기간 핵심 3대 이슈
   - 회사 직접 영향 3가지
   - 즉시 실행 과제 3가지
2) 주요 뉴스 동향 클러스터 & 우선순위 표
   - 컬럼: 클러스터명 | 대표뉴스 | 임팩트 | 시급성 | 확실성 | 난이도 | 점수 | 핵심 근거 | 트리거
3) 제약영업 영향 분석
   - 정책/이슈 → 처방 → 매출 경로
   - 정량 범위(예: “분기 매출 −2%~−5%”)
4) 전략적 대응 및 실행계획
   - 기능 | 액션 | 마감일 | KPI | 리스크 | 완화책
   - 기능 예시: Sales / Market Access / Medical / Regulatory / Marketing / Digital
5) 리스크 & 트리거 보드
   - 리스크별 발생확률/영향/조기신호/완화책
   - 주요 일정 캘린더(정부 고시, 경쟁사 이벤트)
6) 시나리오 (베이스/불리/유리)
   - 각 시나리오별 매출 영향 범위와 결정 포인트
7) 최종 의사결정 권고안 (Final Strategic Recommendation)
   - 모든 분석과 시나리오를 종합한 **하나의 최우선 솔루션**
   - **실행 계획**: 단계별 로드맵(1개월, 3개월, 6개월)
   - **보조 옵션**: 주솔루션이 실패할 경우의 대안 1~2개
   - **승인 필요 사항**: 경영진 결재·예산·조직 변경 등 명확 표기
8) 출처 매핑 & 신뢰도
   - 뉴스 ID별: 출처 | 발행일 | 핵심팩트 | 신뢰도(H/M/L)

## 5. 스타일 가이드
- 불릿·표 위주, 한 문장 20자 내외.
- 모호어 금지: “고려” 대신 “재계약”, “가격협상” 등 구체 동사 사용.
- 날짜는 YYYY-MM-DD로 표기.
- 각 섹션 끝에는 요청·결정사항 1줄 포함.
- 모르는 정보는 “데이터 없음”으로 표기.

## 6. 출력 포맷
- 마크다운 형태로 출력해줘
- 제목은 #, ##, ### 사용
- 표는 마크다운 테이블 형식 사용
- 불릿 포인트는 - 사용
- 번호 목록은 1. 2. 3. 사용
- 강조는 **볼드** 사용
"""

    def generate_report(self, summaries: Dict[str, List[str]]) -> str:
        """OpenAI ChatGPT-4o를 사용하여 전략 보고서 생성"""
        
        # 뉴스 요약 데이터를 텍스트로 변환
        news_content = self._format_news_content(summaries)
        
        system_prompt = self.create_system_prompt()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 뉴스 요약들을 바탕으로 제약영업회사를 위한 전략 보고서를 작성해주세요:\n\n{news_content}"}
                ],
                max_tokens=4000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI API 호출 중 오류 발생: {e}")
            return f"보고서 생성 중 오류가 발생했습니다: {e}"
    
    def _format_news_content(self, summaries: Dict[str, List[str]]) -> str:
        """뉴스 요약 데이터를 보고서용 텍스트로 포맷팅"""
        content = ""
        
        if summaries['newsstand']:
            content += "=== 일반 뉴스 동향 ===\n"
            for i, item in enumerate(summaries['newsstand'][:10], 1):  # 최대 10개
                content += f"{i}. [{item['press']}] {item['title'][:100]}...\n"
                content += f"   요약: {item['summary']}\n"
                content += f"   URL: {item['url']}\n\n"
        
        if summaries['medical_trending']:
            content += "=== 의료업계 주요 이슈 ===\n"
            for i, item in enumerate(summaries['medical_trending'][:15], 1):  # 최대 15개
                content += f"{i}. {item['title'][:100]}...\n"
                content += f"   요약: {item['summary']}\n"
                content += f"   날짜: {item['date']}\n"
                content += f"   URL: {item['url']}\n\n"
        
        if summaries['medical_recent']:
            content += "=== 최신 의료 뉴스 ===\n"
            for i, item in enumerate(summaries['medical_recent'][:10], 1):  # 최대 10개
                content += f"{i}. {item['title'][:100]}...\n"
                content += f"   요약: {item['summary']}\n"
                content += f"   날짜: {item['date']}\n"
                content += f"   URL: {item['url']}\n\n"
        
        return content
    
    def save_report(self, report: str, filename: str = None) -> str:
        """생성된 보고서를 마크다운 파일로 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pharmaceutical_strategy_report_{timestamp}.md"
        
        filepath = os.path.join(self.report_save_path, filename)
        
        try:
            # 마크다운 문서 작성
            markdown_content = f"""# 제약영업회사 전략 보고서

**생성일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{report}

---

*본 보고서는 AI를 활용하여 자동 생성되었습니다.*
"""
            
            # 파일 저장 (UTF-8 인코딩)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 저장 확인
            if os.path.exists(filepath):
                print(f"✅ 보고서 저장 완료: {filepath}")
                return filepath
            else:
                print("❌ 파일 저장 실패")
                return ""
            
        except Exception as e:
            print(f"보고서 저장 중 오류 발생: {e}")
            return ""
    
    
    def generate_and_save_report(self) -> str:
        """전체 프로세스 실행: 데이터 로딩 → 보고서 생성 → 저장"""
        print("뉴스 데이터를 로딩하고 있습니다...")
        summaries = self.load_news_summaries()
        
        total_news = sum(len(items) for items in summaries.values())
        print(f"총 {total_news}개의 뉴스 요약을 로딩했습니다.")
        print(f"- 일반 뉴스: {len(summaries['newsstand'])}개")
        print(f"- 의료 트렌딩 뉴스: {len(summaries['medical_trending'])}개")
        print(f"- 최신 의료 뉴스: {len(summaries['medical_recent'])}개")
        
        if total_news == 0:
            return "분석할 뉴스 데이터가 없습니다."
        
        print("\n전략 보고서를 생성하고 있습니다...")
        report = self.generate_report(summaries)
        
        print("보고서를 저장하고 있습니다...")
        filepath = self.save_report(report)
        
        if filepath:
            print(f"전략 보고서가 생성되었습니다: {filepath}")
            return filepath
        else:
            return "보고서 저장에 실패했습니다."


def main():
    """메인 실행 함수"""
    try:
        # API 키는 환경변수에서 가져오거나 직접 설정
        generator = NewsReportGenerator()
        result = generator.generate_and_save_report()
        print(f"\n실행 완료: {result}")
        
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")


if __name__ == "__main__":
    main()