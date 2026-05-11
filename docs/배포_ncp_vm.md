# NCP VM 배포 가이드 (uv 직접 실행)

Google Cloud Run 배포는 그대로 유지하면서, NCP VM에 uv로 직접 실행하는 가이드입니다.

---

## 서버 접속 정보

| 항목 | 값 |
|------|-----|
| 공인 IP | `101.79.20.188` |
| SSH 포트 | `50022` |
| OS | Ubuntu 24.04.1 LTS |
| CPU | 4코어 (AMD EPYC 9454P) |
| RAM | 15Gi |
| 디스크 | 20G (사용 3.7G / 여유 16G) |
| 계정 | `jwjang` |
| 비밀번호 | `jwjang` |

```bash
ssh jwjang@101.79.20.188 -p 50022
```

---

- 배포 경로: `/home/jwjang/work/trader-ai/`

## 포트 구성 (고유 포트)

| 서비스 | 포트 |
|--------|------|
| Backend API | **51225** |
| ML Service | **51226** |
| Frontend (Caddy) | **51227** |

---

## 1. VM 접속 전 확인 사항

VM은 별도로 제공받습니다. 접속 전 VM 담당자에게 아래 항목을 요청하세요.

- OS: **Ubuntu 24.04.1 LTS**
- 인바운드 포트 오픈: `51225`, `51226`, `51227`, `50022`
- VM 공인 IP 주소: `101.79.20.188`

```bash
ssh jwjang@101.79.20.188 -p 50022
```

---

## 2. VM 환경 설치

```bash
# [유저 로컬] uv 설치 (Python 3.13 자동 다운로드 포함)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # 또는 재접속

# [유저 로컬] Caddy 바이너리 설치 (sudo 불필요)
curl -L "https://caddyserver.com/api/download?os=linux&arch=amd64" -o ~/.local/bin/caddy
chmod +x ~/.local/bin/caddy

# 부팅 시 유저 서비스 자동 시작 활성화
loginctl enable-linger jwjang
```

---

## 3. 소스 배포 (로컬에서 실행)

VM에 필요한 파일만 전송합니다. 아래 항목은 제외합니다.

| 제외 항목 | 이유 |
|-----------|------|
| `.gcloud/`, `deploy/`, `k8s/` | GCP/Cloud Run 전용 |
| `Dockerfile`, `Dockerfile.ml`, `ml/` | Docker 전용 |
| `.dockerignore` | Docker 전용 |
| `frontend/` | 별도 빌드 후 dist만 전송 (6단계 참고) |
| `predict_model/train/` | 학습 노트북 — 추론에 불필요 |
| `documents/` | KIS API HTML 레퍼런스 문서 |
| `나스닥 100 (NDX).csv` | 학습용 데이터 |
| `test_apis.py` | 로컬 테스트 전용 |
| `.git/`, `.venv/`, `__pycache__/` | git 이력 / 가상환경 / 캐시 |
| `.claude/`, `.code-review-graph/` | 개발 도구 전용 |
| `log/`, `stock_scheduler.log`, `.cache/` | 로컬 로그/캐시 |

```bash
rsync -avz --progress \
  --exclude='.gcloud/' \
  --exclude='deploy/' \
  --exclude='k8s/' \
  --exclude='Dockerfile' \
  --exclude='Dockerfile.ml' \
  --exclude='ml/' \
  --exclude='.dockerignore' \
  --exclude='frontend/' \
  --exclude='predict_model/train/' \
  --exclude='documents/' \
  --exclude='나스닥 100 (NDX).csv' \
  --exclude='test_apis.py' \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.claude/' \
  --exclude='.code-review-graph/' \
  --exclude='log/' \
  --exclude='stock_scheduler.log' \
  --exclude='.cache/' \
  --exclude='.DS_Store' \
  -e "ssh -p 50022" \
  /Users/n-jwjang/jjw/work/trader-ai/ \
  jwjang@101.79.20.188:/home/jwjang/work/trader-ai/
```

---

## 4. 의존성 설치 (VM에서)

```bash
cd ~/work/trader-ai

# Backend + ML 의존성 (하나의 venv 공유)
uv sync --frozen --no-dev --group ml
```

---

## 5. systemd 서비스 등록

### 5-1. Backend (포트 51225)

```bash
sudo cat > /etc/systemd/system/trader-ai-backend.service << 'EOF'
[Unit]
Description=Trader AI Backend
After=network.target

[Service]
User=jwjang
WorkingDirectory=/home/jwjang/work/trader-ai
EnvironmentFile=/home/jwjang/work/trader-ai/.env
ExecStart=/home/jwjang/work/trader-ai/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 51225
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 5-2. ML Service (포트 51226)

```bash
sudo cat > /etc/systemd/system/trader-ai-ml.service << 'EOF'
[Unit]
Description=Trader AI ML Service
After=network.target

[Service]
User=jwjang
WorkingDirectory=/home/jwjang/work/trader-ai
EnvironmentFile=/home/jwjang/work/trader-ai/.env
ExecStart=/home/jwjang/work/trader-ai/.venv/bin/uvicorn ml_service.main:app --host 0.0.0.0 --port 51226
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 5-3. Caddy Frontend (포트 51227)

```bash
# Caddyfile 생성
cat > ~/work/trader-ai/Caddyfile << 'EOF'
:51227 {
    root * /home/jwjang/work/trader-ai-frontend
    try_files {path} /index.html
    file_server
}
EOF

# systemd 유저 서비스 등록 (sudo 불필요)
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/trader-ai-caddy.service << 'EOF'
[Unit]
Description=Trader AI Frontend (Caddy)
After=network.target

[Service]
ExecStart=/home/jwjang/.local/bin/caddy run --config /home/jwjang/work/trader-ai/Caddyfile
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
```

### 5-4. 서비스 활성화 및 시작

```bash
# Backend / ML — systemd system (sudo 필요)
sudo systemctl daemon-reload
sudo systemctl enable trader-ai-backend trader-ai-ml
sudo systemctl start trader-ai-backend trader-ai-ml

# Caddy — systemd user (sudo 불필요)
systemctl --user daemon-reload
systemctl --user enable trader-ai-caddy
systemctl --user start trader-ai-caddy
```

---

## 6. Frontend 빌드 및 nginx 설정

### 6-1. 빌드 (로컬에서)

```bash
cd /Users/n-jwjang/jjw/work/trader-ai/frontend
VITE_API_BASE=http://101.79.20.188:51225 npm run build

rsync -avz --progress \
  -e "ssh -p 50022" \
  dist/ \
  jwjang@101.79.20.188:/home/jwjang/work/trader-ai-frontend/
```

### 6-2. Caddy 재시작 (VM에서)

```bash
systemctl --user restart trader-ai-caddy
```

---

## 7. 접속 확인

| 서비스 | URL |
|--------|-----|
| Frontend | `http://101.79.20.188:51227` |
| Backend API Docs | `http://101.79.20.188:51225/docs` |
| ML Service Health | `http://101.79.20.188:51226/health` |

---

## 8. 운영 명령어

```bash
# 상태 확인
sudo systemctl status trader-ai-backend trader-ai-ml
systemctl --user status trader-ai-caddy

# 로그 확인
journalctl -u trader-ai-backend -f
journalctl -u trader-ai-ml -f
journalctl --user -u trader-ai-caddy -f

# 재시작
sudo systemctl restart trader-ai-backend
sudo systemctl restart trader-ai-ml
systemctl --user restart trader-ai-caddy

# 코드 업데이트 후 재배포 (로컬에서)
rsync -avz --progress \
  --exclude='.gcloud/' \
  --exclude='deploy/' \
  --exclude='k8s/' \
  --exclude='Dockerfile' \
  --exclude='Dockerfile.ml' \
  --exclude='ml/' \
  --exclude='.dockerignore' \
  --exclude='frontend/' \
  --exclude='predict_model/train/' \
  --exclude='documents/' \
  --exclude='나스닥 100 (NDX).csv' \
  --exclude='test_apis.py' \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.claude/' \
  --exclude='.code-review-graph/' \
  --exclude='log/' \
  --exclude='stock_scheduler.log' \
  --exclude='.cache/' \
  --exclude='.DS_Store' \
  -e "ssh -p 50022" \
  /Users/n-jwjang/jjw/work/trader-ai/ \
  jwjang@101.79.20.188:/home/jwjang/work/trader-ai/

# VM에서 의존성 업데이트 후 재시작
cd ~/work/trader-ai && uv sync --frozen --no-dev --group ml
sudo systemctl restart trader-ai-backend trader-ai-ml
```

---

## 9. Cloud Run vs NCP VM 차이점

| 항목 | Google Cloud Run | NCP VM |
|------|-----------------|--------|
| 실행 방식 | Docker 컨테이너 | uv + uvicorn 직접 |
| ML_SERVICE_URL | Cloud Run URL | `http://127.0.0.1:51226` |
| 프로세스 관리 | Cloud Run 자동 | systemd |
| Frontend | Cloud Run 컨테이너 | Caddy (유저 로컬) |
