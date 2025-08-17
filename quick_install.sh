#!/bin/bash

# 간단한 openpyxl 설치 스크립트

echo "🚀 Airflow 컨테이너에 openpyxl 설치 중..."

# 주요 컨테이너들에 openpyxl 설치
containers=("son-airflow-worker-1" "son-airflow-scheduler-1")

for container in "${containers[@]}"; do
    if docker ps --format "table {{.Names}}" | grep -q "$container"; then
        echo "📦 $container에 openpyxl 설치..."
        docker exec -u airflow "$container" python -m pip install openpyxl==3.1.2 --quiet
        echo "✅ $container 완료"
    else
        echo "❌ $container 찾을 수 없음"
    fi
done

echo "🎉 설치 완료!"

# 확인
echo "📋 설치 확인:"
docker exec -u airflow son-airflow-worker-1 python -c "
try:
    import openpyxl
    print(f'✅ openpyxl {openpyxl.__version__} 설치됨')
except ImportError:
    print('❌ openpyxl 설치되지 않음')
"