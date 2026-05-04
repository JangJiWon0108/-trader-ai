"""
주식 분석·갱신 API용 Pydantic 모델.

예측 행 표현(StockPrediction)과 배치 갱신 응답(UpdateResponse)만 정의한다.
"""

# ─── 모듈 임포트 ───
from typing import Optional

from pydantic import BaseModel

# ─── 스키마 정의 ───


class StockPrediction(BaseModel):
    stock: str
    last_price: float
    predicted_price: float
    rise_probability: float
    recommendation: str
    analysis: Optional[str] = None


class UpdateResponse(BaseModel):
    success: bool
    message: str
    total_records: int = 0
    updated_records: int = 0
