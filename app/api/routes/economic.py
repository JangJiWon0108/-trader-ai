"""
경제·주가 데이터 API.

Supabase `economic_and_stock_data` 조회, 백그라운드 갱신 트리거,
Yahoo Finance 기반 거래량 CSV 수집(`/collect-volume`)을 제공한다.
"""

# ─── 모듈 임포트 ───
import asyncio
import logging
import os
import traceback
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.schemas.stock import UpdateResponse
from app.utils.scheduler import run_economic_data_update_now

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── 헬퍼 함수 ───


def _parse_iso_date(label: str, value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    s = value.strip()
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{label}는 YYYY-MM-DD 형식이어야 합니다: {value}")
    return s


# ─── 엔드포인트 핸들러 ───


@router.get("/history", summary="날짜별 경제·주식 데이터 (페이지)")
def get_economic_history(
    date_from: str | None = Query(None, description="시작일 YYYY-MM-DD (미입력 시 제한 없음)"),
    date_to: str | None = Query(None, description="종료일 YYYY-MM-DD (미입력 시 제한 없음)"),
    page: int = Query(1, ge=1, description="1부터 시작"),
    page_size: int = Query(15, ge=1, le=100),
):
    """economic_and_stock_data 테이블을 날짜 기준 내림차순으로 페이지 조회합니다."""
    from app.db.supabase import supabase

    df = _parse_iso_date("date_from", date_from)
    dt = _parse_iso_date("date_to", date_to)
    if df and dt and df > dt:
        raise HTTPException(status_code=422, detail="date_from은 date_to보다 늦을 수 없습니다.")

    try:
        q = supabase.table("economic_and_stock_data").select("*", count="exact")
        if df:
            q = q.gte("날짜", df)
        if dt:
            q = q.lte("날짜", dt)
        offset = (page - 1) * page_size
        resp = q.order("날짜", desc=True).range(offset, offset + page_size - 1).execute()
        total = resp.count if resp.count is not None else 0
        items: list[dict[str, Any]] = []
        for row in resp.data or []:
            r = dict(row)
            d = r.pop("날짜", None)
            items.append({"date": d, "data": r})
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest", summary="최신 경제 지표 조회")
def get_latest_economic_data():
    """Supabase economic_and_stock_data 테이블에서 최신 행 반환"""
    from app.db.supabase import supabase

    try:
        resp = (
            supabase.table("economic_and_stock_data")
            .select("*")
            .order("날짜", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return {"date": None, "data": {}}
        row = resp.data[0]
        date = row.pop("날짜", None)
        return {"date": date, "data": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update", summary="경제 및 주식 데이터 업데이트", response_model=UpdateResponse)
async def update_economic_data(
    background_tasks: BackgroundTasks,
):
    """
    경제 및 주식 데이터를 Supabase에 저장합니다.
    이 작업은 백그라운드에서 실행되어 API 응답을 블로킹하지 않습니다.

    DB에서 마지막 수집 날짜를 자동으로 찾아 그 다음 날부터 수집합니다.
    기존 데이터의 NULL 값은 새 데이터로 자동 업데이트됩니다.
    """
    try:
        background_tasks.add_task(run_economic_data_update_now)

        return {
            "success": True,
            "message": "경제 데이터 업데이트가 백그라운드에서 시작되었습니다.",
            "total_records": 0,
            "updated_records": 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터 업데이트 중 오류 발생: {str(e)}")


@router.post("/collect-volume", summary="주식 거래량 데이터 수집", response_model=UpdateResponse)
async def collect_volume_data(
    background_tasks: BackgroundTasks,
    lookback_days: int = 200,
):
    """
    주요 종목 거래량을 Yahoo Finance에서 받아 `volume.csv`로 저장합니다.
    (trader-ai-real `/economic/collect-volume` 과 동일 목적)
    """
    try:
        background_tasks.add_task(collect_stock_volume_data, lookback_days)
        return {
            "success": True,
            "message": f"주식 거래량 데이터 수집이 백그라운드에서 시작되었습니다. (최대 {lookback_days}일치)",
            "total_records": 0,
            "updated_records": 0,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"거래량 데이터 수집 중 오류 발생: {str(e)}",
        )


async def collect_stock_volume_data(lookback_days: int = 200):
    stock_to_ticker = {
        "애플": "AAPL",
        "마이크로소프트": "MSFT",
        "아마존": "AMZN",
        "구글 A": "GOOGL",
        "구글 C": "GOOG",
        "메타": "META",
        "테슬라": "TSLA",
        "엔비디아": "NVDA",
        "코스트코": "COST",
        "넷플릭스": "NFLX",
        "페이팔": "PYPL",
        "인텔": "INTC",
        "시스코": "CSCO",
        "컴캐스트": "CMCSA",
        "펩시코": "PEP",
        "암젠": "AMGN",
        "허니웰 인터내셔널": "HON",
        "스타벅스": "SBUX",
        "몬델리즈": "MDLZ",
        "마이크론": "MU",
        "브로드컴": "AVGO",
        "어도비": "ADBE",
        "텍사스 인스트루먼트": "TXN",
        "AMD": "AMD",
        "어플라이드 머티리얼즈": "AMAT",
        "S&P 500 ETF": "SPY",
        "QQQ ETF": "QQQ",
    }

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        logger.info("거래량 데이터 수집 시작: %s ~ %s", start_date, end_date)

        result_df = pd.DataFrame()

        for stock_name, ticker in stock_to_ticker.items():
            try:
                logger.info("%s (%s) 데이터 수집 중", stock_name, ticker)
                df = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    auto_adjust=True,
                    progress=False,
                )
                if not df.empty:
                    volume_data = df[["Volume"]].copy()
                    volume_data.columns = [stock_name]
                    if result_df.empty:
                        result_df = volume_data
                    else:
                        result_df = pd.merge(
                            result_df,
                            volume_data,
                            left_index=True,
                            right_index=True,
                            how="outer",
                        )
                    logger.info("  - %s: %s일치 데이터 수집 완료", stock_name, len(df))
                else:
                    logger.info("  - %s: 데이터 없음", stock_name)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning("  - %s 데이터 수집 중 오류: %s", stock_name, e, exc_info=True)
                continue

        if not result_df.empty:
            result_df.index.name = "날짜"
            result_df.reset_index(inplace=True)
            result_df["날짜"] = result_df["날짜"].dt.strftime("%Y-%m-%d")
            file_path = os.path.join(os.getcwd(), "volume.csv")
            result_df.to_csv(file_path, index=False, encoding="utf-8-sig")
            logger.info("총 %s일치 거래량 데이터 저장: %s", len(result_df), file_path)
        else:
            logger.info("수집된 데이터 없음")
    except Exception as e:
        logger.error("거래량 데이터 수집 작업 중 오류: %s\n%s", e, traceback.format_exc())
