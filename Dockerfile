FROM apache/airflow:3.0.3

USER root

# Chrome 설치를 위한 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Chrome 설치
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# ChromeDriver 설치 (Chrome 138 버전으로 다운그레이드)
RUN wget -q "https://storage.googleapis.com/chrome-for-testing-public/138.0.6961.98/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver* \
    && chromedriver --version

# requirements.txt 파일 복사
COPY requirements.txt /tmp/requirements.txt

# airflow 사용자로 전환 후 패키지 설치
USER airflow
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1