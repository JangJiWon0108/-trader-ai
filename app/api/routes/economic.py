from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from app.schemas.stock import UpdateResponse
from app.utils.scheduler import run_economic_data_update_now
from datetime import datetime, timedelta
import asyncio
import os

import pandas as pd
import yfinance as yf

router = APIRouter()

@router.get("/latest", summary="최신 경제 지표 조회")
def get_latest_economic_data():
    """Supabase economic_and_stock_data 테이블에서 최신 행 반환"""
    from app.db.supabase import supabase
    try:
        resp = supabase.table("economic_and_stock_data") \
            .select("*") \
            .order("날짜", desc=True) \
            .limit(1) \
            .execute()
        if not resp.data:
            return {"date": None, "data": {}}
        row = resp.data[0]
        date = row.pop("날짜", None)
        return {"date": date, "data": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update", summary="경제 및 주식 데이터 업데이트", response_model=UpdateResponse)
async def update_economic_data(
    background_tasks: BackgroundTasks
):
    """
    경제 및 주식 데이터를 Supabase에 저장합니다.
    이 작업은 백그라운드에서 실행되어 API 응답을 블로킹하지 않습니다.
    
    DB에서 마지막 수집 날짜를 자동으로 찾아 그 다음 날부터 수집합니다.
    기존 데이터의 NULL 값은 새 데이터로 자동 업데이트됩니다.
    """
    try:
        # 백그라운드 작업으로 경제 데이터 업데이트 실행
        background_tasks.add_task(run_economic_data_update_now)
        
        return {
            "success": True,
            "message": "경제 데이터 업데이트가 백그라운드에서 시작되었습니다.",
            "total_records": 0,
            "updated_records": 0
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
            status_code=500, detail=f"거래량 데이터 수집 중 오류 발생: {str(e)}"
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
        print(f"거래량 데이터 수집 시작: {start_date} ~ {end_date}")

        result_df = pd.DataFrame()

        for stock_name, ticker in stock_to_ticker.items():
            try:
                print(f"{stock_name} ({ticker}) 데이터 수집 중...")
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
                    print(f"  - {stock_name}: {len(df)}일치 데이터 수집 완료")
                else:
                    print(f"  - {stock_name}: 데이터가 없습니다.")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  - {stock_name} 데이터 수집 중 오류: {str(e)}")
                continue

        if not result_df.empty:
            result_df.index.name = "날짜"
            result_df.reset_index(inplace=True)
            result_df["날짜"] = result_df["날짜"].dt.strftime("%Y-%m-%d")
            file_path = os.path.join(os.getcwd(), "volume.csv")
            result_df.to_csv(file_path, index=False, encoding="utf-8-sig")
            print(f"총 {len(result_df)}일치의 거래량 데이터를 {file_path}에 저장했습니다.")
        else:
            print("수집된 데이터가 없습니다.")
    except Exception as e:
        print(f"거래량 데이터 수집 작업 중 오류: {e}")
        import traceback

        print(traceback.format_exc())