# ML 추론 전용 — Cloud Run Service (trader-ai-ml)
# 빌드: 레포 루트에서  docker build -f ml/Dockerfile -t ... .
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Seoul

# 이미지 내 기본 모델 경로 (Cloud Run env 로 덮어쓸 수 있음)
ENV PREDICT_MODEL_DIR=predict_model/model/v4_260505_최근30일_validation

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo "Asia/Seoul" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN python -m pip install --no-cache-dir uv \
    && UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --no-dev \
    && rm -rf /tmp/uv-cache /root/.cache/uv

COPY . .

EXPOSE 8080

# Cloud Run 은 PORT 주입 — 미설정 시 8080
CMD ["/bin/sh", "-c", "exec /app/.venv/bin/python -m uvicorn ml_service.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
