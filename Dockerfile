FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    HF_HUB_ENABLE_HF_TRANSFER=1

WORKDIR /app

# PyMuPDF/transformers 최소 시스템 deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# torch는 CPU 전용 휠로 먼저 깔아두고
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.1

# 나머지 파이썬 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스
COPY . .

# Gunicorn로 Flask 앱 실행 (Cloud Run은 $PORT를 주입)
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 0 app:flask_app
