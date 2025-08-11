#!/bin/bash

# Universal S3 File Uploader 서버 시작 스크립트

echo "==============================================="
echo "🚀 Universal S3 File Uploader 서버 시작"
echo "==============================================="

# 작업 디렉토리 이동
cd "$(dirname "$0")"

# .env 파일 로드
if [ -f "/home/son/.env" ]; then
    echo "📋 .env 파일에서 AWS 환경변수 로드 중..."
    export $(cat /home/son/.env | grep -E "^AWS_" | xargs)
    echo "✅ AWS 환경변수 로드 완료"
else
    echo "❌ .env 파일을 찾을 수 없습니다: /home/son/.env"
    exit 1
fi

# 기존 프로세스 종료
echo "🛑 기존 S3 업로드 서버 프로세스 종료 중..."
pkill -f s3_file_uploader.py
pkill -f upload_post_s3_to_s3.py
sleep 2

# AWS 자격증명 확인
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "❌ AWS 자격증명이 설정되지 않았습니다!"
    echo ""
    echo "다음과 같이 /home/son/.env 파일에 AWS 자격증명을 추가하세요:"
    echo "AWS_ACCESS_KEY_ID=your-access-key-id"
    echo "AWS_SECRET_ACCESS_KEY=your-secret-access-key"
    echo "AWS_DEFAULT_REGION=us-east-2"
    echo ""
    exit 1
fi

# 환경변수 확인 출력
echo "✅ AWS 자격증명 확인됨:"
echo "   🔑 AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:8}***"
echo "   🔐 AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:0:8}***"
echo "   🌍 AWS_DEFAULT_REGION: ${AWS_DEFAULT_REGION:-us-east-2}"
echo ""

# 필요한 패키지 확인
echo "📦 필요한 패키지 확인 중..."
python3 -c "import fastapi, uvicorn, boto3" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ 모든 필요한 패키지가 설치되어 있습니다"
else
    echo "❌ 필요한 패키지가 부족합니다. 다음 패키지들을 설치해주세요:"
    echo "   pip3 install fastapi uvicorn boto3 python-multipart"
    exit 1
fi

echo ""
echo "🚀 S3 File Uploader 서버 시작 중..."
echo "   📍 포트: 8005"
echo "   🌐 주소: http://localhost:8005"
echo "   ☁️ 버킷: skn12-final-1team"
echo "   🌍 리전: us-east-2"
echo "   📏 최대 파일 크기: 100MB"
echo ""

# 서버 실행 방법 선택
if [ "$1" = "--foreground" ] || [ "$1" = "-f" ]; then
    echo "🔍 포어그라운드 모드로 실행 (Ctrl+C로 종료)"
    python3 s3_file_uploader.py
else
    echo "🔙 백그라운드 모드로 실행"
    nohup python3 s3_file_uploader.py > s3_uploader.log 2>&1 &
    SERVER_PID=$!
    
    echo "📍 서버 PID: $SERVER_PID"
    echo "📋 로그 파일: s3_uploader.log"
    
    # 서버 시작 확인 (5초 대기)
    echo "⏳ 서버 시작 확인 중..."
    sleep 5
    
    if ps -p $SERVER_PID > /dev/null; then
        echo "✅ 서버가 성공적으로 시작되었습니다!"
        
        # 서버 상태 확인
        STATUS_RESPONSE=$(curl -s http://localhost:8005/api/status 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo "✅ 서버 응답 정상"
            echo "🔧 S3 연결 상태: $(echo "$STATUS_RESPONSE" | grep -o '"s3_status":"[^"]*"' | cut -d'"' -f4)"
        else
            echo "⚠️  서버는 실행 중이지만 응답 확인에 실패했습니다"
            echo "   잠시 후 다시 시도해보세요"
        fi
        
        echo ""
        echo "==============================================="
        echo "🎉 S3 파일 업로드 서버 준비 완료!"
        echo "==============================================="
        echo "🌐 웹 브라우저에서 http://localhost:8005 접속"
        echo "📤 모든 종류의 파일을 드래그하여 업로드 가능"
        echo "🔒 파일은 KMS 암호화되어 S3에 저장됩니다"
        echo ""
        echo "💡 명령어:"
        echo "   서버 종료: pkill -f s3_file_uploader"
        echo "   로그 보기: tail -f s3_uploader.log"
        echo "   상태 확인: curl http://localhost:8005/api/status"
        echo "==============================================="
        
    else
        echo "❌ 서버 시작에 실패했습니다"
        echo "📋 로그를 확인해보세요: cat s3_uploader.log"
        exit 1
    fi
fi