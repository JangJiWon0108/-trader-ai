"""
FastAPI 애플리케이션 진입점.

CORS·API 라우터 등록, lifespan 에서 경제 데이터 1회 갱신·텔레그램 알림·
매수·매도·경제 지표 스케줄러를 기동한다. 종료 시 스케줄러만 정리한다.
"""

# ─── 모듈 임포트 ───
from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alarm.notify import notify_telegram_economic_update
from app.api.api import api_router
from app.core.config import settings
from app.services.economic_service import update_economic_data_in_background
from app.utils.scheduler import (
    start_economic_data_scheduler,
    start_scheduler,
    start_sell_scheduler,
    stop_economic_data_scheduler,
    stop_scheduler,
    stop_sell_scheduler,
)

logger = logging.getLogger(__name__)

# ─── lifespan ───


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 앱 기동 시 1회
    await startup()
    yield
    # Shutdown: 스케줄러 정리
    stop_scheduler()
    stop_sell_scheduler()
    stop_economic_data_scheduler()


# ─── 앱 인스턴스 ───

app = FastAPI(title="주식 분석 및 추천 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def read_root():
    return {"message": "주식 분석 및 추천 API에 오신 것을 환영합니다"}


# ─── 기동 로직 ───


async def startup():
    """서비스 기동 시 경제 데이터 1회 수집 후 스케줄러 시작."""
    logger.info("서비스 시작 시 경제 데이터 수집 즉시 실행")
    try:
        result = await update_economic_data_in_background()
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        logger.exception("초기 경제 데이터 수집 예외: %s", e)

    notify_payload = result if isinstance(result, dict) else {}
    notify_telegram_economic_update(notify_payload, source="서버시작")

    if isinstance(result, dict) and result.get("success"):
        logger.info("초기 경제 데이터 수집 완료")
    else:
        logger.warning("초기 경제 데이터 수집 실패 또는 스킵: %s", result)

    start_economic_data_scheduler()
    start_scheduler()
    start_sell_scheduler()
    logger.info("경제 데이터 스케줄러 시작 (KST %s)", settings.SCHEDULE_ECONOMIC_UPDATE_TIME)
    logger.info("주식 자동매매 스케줄러 시작")
    logger.info("주식 자동매도 스케줄러 시작")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
