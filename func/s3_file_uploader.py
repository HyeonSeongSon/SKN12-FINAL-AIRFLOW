#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
범용 S3 파일 업로드 FastAPI 서버
사용자가 웹 인터페이스를 통해 모든 종류의 파일을 AWS S3에 업로드할 수 있습니다.
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import os
from datetime import datetime
import mimetypes
import uvicorn

# AWS S3 설정
REGION = "us-east-2"
BUCKET = "skn12-final-1team"
KEY_ARN = "arn:aws:kms:us-east-2:634531197710:key/09d97dfe-bb3c-4fa2-acdc-ab941139933d"

app = FastAPI(
    title="Universal S3 File Uploader",
    description="모든 파일을 S3에 업로드할 수 있는 범용 웹 서버",
    version="1.0.0"
)

@app.get("/", response_class=HTMLResponse)
async def home():
    """메인 업로드 페이지"""
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📤 Universal S3 File Uploader</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 40px;
            max-width: 600px;
            width: 100%;
            text-align: center;
            animation: fadeIn 0.8s ease-in;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        
        .upload-area {
            border: 3px dashed #4CAF50;
            border-radius: 15px;
            padding: 40px 20px;
            margin: 30px 0;
            background: linear-gradient(145deg, #f9f9f9, #e8e8e8);
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
        }
        
        .upload-area:hover,
        .upload-area.dragover {
            border-color: #45a049;
            background: linear-gradient(145deg, #f0f8f0, #e0f0e0);
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.2);
        }
        
        .upload-icon {
            font-size: 4em;
            color: #4CAF50;
            margin-bottom: 20px;
            display: block;
        }
        
        .upload-text {
            font-size: 1.2em;
            color: #333;
            margin-bottom: 10px;
        }
        
        .upload-hint {
            color: #666;
            font-size: 0.9em;
        }
        
        #fileInput {
            display: none;
        }
        
        .file-info {
            background: linear-gradient(145deg, #fff3cd, #ffeaa7);
            border: 1px solid #ffeaa7;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            display: none;
            text-align: left;
        }
        
        .upload-btn {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 25px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(76, 175, 80, 0.3);
            margin: 20px 10px;
        }
        
        .upload-btn:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(76, 175, 80, 0.4);
        }
        
        .upload-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .clear-btn {
            background: linear-gradient(45deg, #f44336, #d32f2f);
            box-shadow: 0 5px 15px rgba(244, 67, 54, 0.3);
        }
        
        .clear-btn:hover {
            box-shadow: 0 8px 20px rgba(244, 67, 54, 0.4);
        }
        
        .progress {
            width: 100%;
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0;
            display: none;
        }
        
        .progress-bar {
            height: 100%;
            background: linear-gradient(45deg, #4CAF50, #45a049);
            width: 0%;
            transition: width 0.3s ease;
            animation: shimmer 2s infinite linear;
        }
        
        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
        
        .result {
            margin-top: 30px;
            padding: 20px;
            border-radius: 15px;
            display: none;
            animation: slideIn 0.5s ease-in;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        
        .success {
            background: linear-gradient(145deg, #d4edda, #c3e6cb);
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .error {
            background: linear-gradient(145deg, #f8d7da, #f5c6cb);
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 30px 0;
        }
        
        .info-card {
            background: linear-gradient(145deg, #e3f2fd, #bbdefb);
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #2196F3;
        }
        
        .info-title {
            font-weight: bold;
            color: #1976D2;
            margin-bottom: 5px;
        }
        
        .info-value {
            color: #333;
            font-size: 0.9em;
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 20px;
                margin: 10px;
            }
            
            .info-grid {
                grid-template-columns: 1fr;
            }
            
            h1 {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📤 Universal S3 Uploader</h1>
        <p class="subtitle">모든 종류의 파일을 AWS S3에 안전하게 업로드하세요</p>
        
        <div class="info-grid">
            <div class="info-card">
                <div class="info-title">🎯 대상 버킷</div>
                <div class="info-value">skn12-final-1team</div>
            </div>
            <div class="info-card">
                <div class="info-title">🌐 리전</div>
                <div class="info-value">us-east-2</div>
            </div>
            <div class="info-card">
                <div class="info-title">🔒 보안</div>
                <div class="info-value">KMS 암호화</div>
            </div>
            <div class="info-card">
                <div class="info-title">📏 최대 크기</div>
                <div class="info-value">100MB</div>
            </div>
        </div>
        
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <span class="upload-icon">📁</span>
            <div class="upload-text">파일을 선택하거나 여기로 드래그하세요</div>
            <div class="upload-hint">지원 파일: 모든 형식 (이미지, 문서, 동영상, 압축파일 등)</div>
        </div>
        
        <input type="file" id="fileInput" accept="*/*">
        
        <div id="fileInfo" class="file-info"></div>
        
        <div id="progress" class="progress">
            <div id="progressBar" class="progress-bar"></div>
        </div>
        
        <div class="button-group">
            <button id="uploadBtn" class="upload-btn" onclick="uploadFile()" disabled>
                🚀 파일 업로드
            </button>
            <button id="clearBtn" class="upload-btn clear-btn" onclick="clearFile()" style="display: none;">
                🗑️ 파일 지우기
            </button>
        </div>
        
        <div id="result" class="result"></div>
    </div>

    <script>
        let selectedFile = null;
        
        // 파일 선택 처리
        document.getElementById('fileInput').addEventListener('change', handleFileSelect);
        
        // 드래그 앤 드롭 처리
        const uploadArea = document.querySelector('.upload-area');
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelection(files[0]);
            }
        });
        
        function handleFileSelect(event) {
            const file = event.target.files[0];
            if (file) {
                handleFileSelection(file);
            }
        }
        
        function handleFileSelection(file) {
            selectedFile = file;
            const fileInfo = document.getElementById('fileInfo');
            const uploadBtn = document.getElementById('uploadBtn');
            const clearBtn = document.getElementById('clearBtn');
            
            const fileSize = (file.size / 1024 / 1024).toFixed(2);
            const maxSize = 100;
            
            let sizeClass = '';
            let sizeIcon = '✅';
            if (fileSize > maxSize) {
                sizeClass = 'color: red; font-weight: bold;';
                sizeIcon = '❌';
            } else if (fileSize > maxSize * 0.8) {
                sizeClass = 'color: orange; font-weight: bold;';
                sizeIcon = '⚠️';
            }
            
            fileInfo.innerHTML = `
                <h3>📄 선택된 파일</h3>
                <div style="margin-top: 15px;">
                    <div><strong>📝 파일명:</strong> ${file.name}</div>
                    <div><strong>📏 크기:</strong> <span style="${sizeClass}">${sizeIcon} ${fileSize} MB</span></div>
                    <div><strong>📋 타입:</strong> ${file.type || '알 수 없음'}</div>
                    <div><strong>🕒 선택 시간:</strong> ${new Date().toLocaleString('ko-KR')}</div>
                </div>
            `;
            
            fileInfo.style.display = 'block';
            uploadBtn.disabled = fileSize > maxSize;
            clearBtn.style.display = 'inline-block';
            
            if (fileSize > maxSize) {
                uploadBtn.textContent = `❌ 파일이 너무 큽니다 (${maxSize}MB 초과)`;
            } else {
                uploadBtn.textContent = '🚀 파일 업로드';
            }
        }
        
        function clearFile() {
            selectedFile = null;
            document.getElementById('fileInput').value = '';
            document.getElementById('fileInfo').style.display = 'none';
            document.getElementById('uploadBtn').disabled = true;
            document.getElementById('uploadBtn').textContent = '🚀 파일 업로드';
            document.getElementById('clearBtn').style.display = 'none';
            document.getElementById('result').style.display = 'none';
            document.getElementById('progress').style.display = 'none';
        }
        
        async function uploadFile() {
            if (!selectedFile) {
                alert('파일을 먼저 선택해주세요!');
                return;
            }
            
            const resultDiv = document.getElementById('result');
            const uploadBtn = document.getElementById('uploadBtn');
            const progress = document.getElementById('progress');
            const progressBar = document.getElementById('progressBar');
            
            uploadBtn.disabled = true;
            uploadBtn.textContent = '⏳ 업로드 중...';
            progress.style.display = 'block';
            resultDiv.style.display = 'none';
            
            const formData = new FormData();
            formData.append('file', selectedFile);
            
            try {
                // 프로그레스 바 애니메이션
                let progressValue = 0;
                const progressInterval = setInterval(() => {
                    progressValue += Math.random() * 15;
                    if (progressValue > 90) progressValue = 90;
                    progressBar.style.width = progressValue + '%';
                }, 150);
                
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                clearInterval(progressInterval);
                progressBar.style.width = '100%';
                
                const data = await response.json();
                
                setTimeout(() => {
                    progress.style.display = 'none';
                    resultDiv.className = 'result ' + (data.success ? 'success' : 'error');
                    resultDiv.innerHTML = data.message;
                    resultDiv.style.display = 'block';
                }, 500);
                
            } catch (error) {
                progress.style.display = 'none';
                resultDiv.className = 'result error';
                resultDiv.innerHTML = `❌ 네트워크 오류: ${error.message}`;
                resultDiv.style.display = 'block';
            } finally {
                uploadBtn.disabled = false;
                uploadBtn.textContent = '🚀 파일 업로드';
            }
        }
    </script>
</body>
</html>
    """

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """사용자가 선택한 파일을 S3에 업로드"""
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    try:
        # 파일 내용 읽기
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "success": False,
                    "message": f"❌ 파일이 너무 큽니다. 최대 {MAX_FILE_SIZE // (1024*1024)}MB까지 업로드 가능합니다."
                }
            )
        
        # boto3 임포트
        import boto3
        
        # S3 클라이언트 생성
        s3 = boto3.client("s3", region_name=REGION)
        
        # 파일 정보 처리
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = file.filename.replace(' ', '_').replace('(', '').replace(')', '')
        s3_key = f"uploads/{timestamp}_{safe_filename}"
        
        # S3 업로드
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=file_content,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=KEY_ARN,
            ContentType=content_type,
            Metadata={
                'original_filename': file.filename,
                'upload_timestamp': timestamp,
                'file_size': str(file_size)
            }
        )
        
        # 결과 반환
        s3_url = f"s3://{BUCKET}/{s3_key}"
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        return {
            "success": True,
            "message": f"""
            <div style="text-align: left;">
                <h3>✅ 업로드 완료!</h3>
                <div style="margin-top: 15px; line-height: 1.6;">
                    <div><strong>📄 파일명:</strong> {file.filename}</div>
                    <div><strong>📏 크기:</strong> {file_size_mb} MB</div>
                    <div><strong>📋 타입:</strong> {content_type}</div>
                    <div><strong>🕒 업로드 시간:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                    <div style="margin-top: 10px;">
                        <strong>☁️ S3 URL:</strong><br>
                        <code style="background: rgba(0,0,0,0.1); padding: 5px; border-radius: 4px; word-break: break-all;">{s3_url}</code>
                    </div>
                    <div style="margin-top: 10px;">
                        <strong>🔑 S3 Key:</strong><br>
                        <code style="background: rgba(0,0,0,0.1); padding: 5px; border-radius: 4px; word-break: break-all;">{s3_key}</code>
                    </div>
                </div>
            </div>
            """
        }
        
    except ImportError:
        return {
            "success": False,
            "message": "❌ boto3 패키지가 설치되지 않았습니다."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ 업로드 실패: {str(e)}"
        }

@app.get("/api/status")
async def get_status():
    """서버 상태 API"""
    try:
        import boto3
        s3 = boto3.client("s3", region_name=REGION)
        
        # S3 연결 테스트
        try:
            s3.head_bucket(Bucket=BUCKET)
            s3_status = "connected"
        except:
            s3_status = "disconnected"
            
        return {
            "service": "Universal S3 File Uploader",
            "version": "1.0.0",
            "status": "running",
            "port": 8005,
            "s3_status": s3_status,
            "target_bucket": BUCKET,
            "region": REGION,
            "max_file_size_mb": 100,
            "timestamp": datetime.now().isoformat()
        }
        
    except ImportError:
        return {
            "service": "Universal S3 File Uploader",
            "status": "error",
            "message": "boto3 not available"
        }

def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("🚀 Universal S3 File Uploader Server")
    print("=" * 80)
    print(f"🌐 Server URL: http://localhost:8005")
    print(f"☁️  Target Bucket: {BUCKET}")
    print(f"🌍 Region: {REGION}")
    print(f"📁 Storage Path: uploads/filename")
    print(f"📏 Max File Size: 100MB")
    print(f"📋 Supported Files: All types")
    print("=" * 80)
    print("💡 Usage: Open web browser and upload any file type")
    print("🔒 Security: Files are encrypted with KMS")
    print("=" * 80)
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8005, log_level="info")
    except Exception as e:
        print(f"❌ Server startup failed: {e}")

if __name__ == "__main__":
    main()