"""
주식 예측·티커 조회 API.

Supabase `stock_analysis_results` 에서 예측 목록·티커별 최신 행을 반환한다.
"""

# ─── 모듈 임포트 ───
from typing import List

from fastapi import APIRouter, HTTPException

from app.db.supabase import supabase
from app.schemas.stock import StockPrediction

router = APIRouter()

# ─── 상수 정의 ───

TICKER_TO_STOCK = {
    "AAPL": "애플",
    "MSFT": "마이크로소프트",
    "AMZN": "아마존",
    "GOOGL": "구글 A",
    "GOOG": "구글 C",
    "META": "메타",
    "TSLA": "테슬라",
    "NVDA": "엔비디아",
    "COST": "코스트코",
    "NFLX": "넷플릭스",
    "PYPL": "페이팔",
    "INTC": "인텔",
    "CSCO": "시스코",
    "CMCSA": "컴캐스트",
    "PEP": "펩시코",
    "AMGN": "암젠",
    "HON": "허니웰 인터내셔널",
    "SBUX": "스타벅스",
    "MDLZ": "몬델리즈",
    "MU": "마이크론",
    "AVGO": "브로드컴",
    "ADBE": "어도비",
    "TXN": "텍사스 인스트루먼트",
    "AMD": "AMD",
    "AMAT": "어플라이드 머티리얼즈",
    "SPY": "S&P 500 ETF",
    "QQQ": "QQQ ETF",
}

# ─── 엔드포인트 핸들러 ───


@router.get("/predictions", summary="주식 예측 결과 조회", response_model=List[StockPrediction])
def read_predictions():
    try:
        response = (
            supabase.table("stock_analysis_results")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        if not response.data:
            return []
        seen = {}
        for row in response.data:
            stock = row["Stock"]
            if stock not in seen:
                seen[stock] = row
        predictions = [
            StockPrediction(
                stock=row["Stock"],
                last_price=row["Last Actual Price"],
                predicted_price=row["Predicted Future Price"],
                rise_probability=row["Rise Probability (%)"],
                recommendation=row["Recommendation"],
                analysis=row.get("Analysis"),
            )
            for row in seen.values()
        ]
        return predictions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"예측 결과 조회 중 오류 발생: {str(e)}")


@router.get("/{ticker}", summary="특정 주식 정보 조회")
def read_stock_info(ticker: str):
    try:
        stock_name = TICKER_TO_STOCK.get(ticker.upper())
        if not stock_name:
            raise HTTPException(status_code=404, detail=f"지원하지 않는 티커: {ticker}")
        response = (
            supabase.table("stock_analysis_results")
            .select("*")
            .eq("Stock", stock_name)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail=f"{ticker} 분석 데이터를 찾을 수 없습니다.")
        return response.data[0]
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주식 정보 조회 중 오류 발생: {str(e)}")
