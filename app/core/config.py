from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List, Optional, Union, Literal, get_type_hints
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "주식 분석 API"
    PROJECT_DESCRIPTION: str = "해외주식 잔고 조회 및 주식 예측 API"
    PROJECT_VERSION: str = "1.0.0"
    
    # DEBUG 설정 추가
    DEBUG: bool = Field(default=False, description="디버그 모드 활성화 여부")
    
    CORS_ORIGINS: List[str] = ["*"]
    
    SUPABASE_URL: str = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # 추론(run_inference 등): model_meta.json·keras·스케일러가 있는 디렉터리
    # 프로젝트 루트 기준 상대경로 또는 절대경로 (예: predict_model/model/v2_260510)
    PREDICT_MODEL_DIR: str = Field(
        default="predict_model/model/v1_260504",
        description="Transformer 추론 모델 디렉터리",
    )
    
    # 한국투자증권 — 모의투자 전용 (.env 의 KIS_MOCK_* 만 사용)
    KIS_MOCK_BASE_URL: str = Field(
        default="https://openapivts.koreainvestment.com:29443",
        description="모의투자 API 베이스 URL",
    )
    KIS_MOCK_APPKEY: str = Field(default="", description="모의투자 앱키")
    KIS_MOCK_APPSECRET: str = Field(default="", description="모의투자 앱시크릿")
    KIS_MOCK_CANO: str = Field(default="", description="모의 계좌번호 앞 8자리")
    KIS_MOCK_ACNT_PRDT_CD: str = Field(default="01", description="모의 계좌상품코드 뒤 2자리")

    # 한국투자증권 — 실전투자 전용 (.env 의 KIS_REAL_* 만 사용)
    KIS_REAL_BASE_URL: str = Field(
        default="https://openapi.koreainvestment.com:9443",
        description="실전투자 API 베이스 URL",
    )
    KIS_REAL_APPKEY: str = Field(default="", description="실전 앱키")
    KIS_REAL_APPSECRET: str = Field(default="", description="실전 앱시크릿")
    KIS_REAL_CANO: str = Field(default="", description="실전 계좌번호 앞 8자리")
    KIS_REAL_ACNT_PRDT_CD: str = Field(default="01", description="실전 계좌상품코드 뒤 2자리")

    KIS_USE_MOCK: bool = Field(default=True, description="true면 모의 블록, false면 실전 블록")

    SCHEDULE_AUTO_BUY_TIME: str = Field(default="00:00", description="자동 매수 실행 시간 (HH:MM, KST)")
    SCHEDULE_AUTO_SELL_INTERVAL_MIN: int = Field(default=1, description="자동 매도 체크 주기 (분)")
    SCHEDULE_ECONOMIC_UPDATE_TIME: str = Field(default="06:10", description="경제 데이터 수집 시간 (HH:MM, KST)")
    SCHEDULE_AFTER_ECONOMIC_RUN_INFERENCE: bool = Field(
        default=True,
        description="매일 경제·주가 DB 갱신(스케줄) 직후, 신규 저장 행이 있으면 저장 모델로 추론·predicted_stocks 등 갱신",
    )

    FRED_API_KEY: str = Field(default="", description="FRED API 키")

    ALPHA_VANTAGE_API_KEY_MAIN: str = os.getenv("ALPHA_VANTAGE_API_KEY_MAIN", "")
    ALPHA_VANTAGE_API_KEY_SUB_1: str = os.getenv("ALPHA_VANTAGE_API_KEY_SUB_1", "")
    ALPHA_VANTAGE_API_KEY_SUB_2: str = os.getenv("ALPHA_VANTAGE_API_KEY_SUB_2", "")
    # real 레포 호환: 단일 키만 있을 때 (위 세 변수가 비어 있으면 사용)
    ALPHA_VANTAGE_API_KEY: str = Field(default="", description="Alpha Vantage 단일 API 키")

    @property
    def KIS_APPKEY(self) -> str:
        return self.KIS_MOCK_APPKEY if self.KIS_USE_MOCK else self.KIS_REAL_APPKEY

    @property
    def KIS_APPSECRET(self) -> str:
        return self.KIS_MOCK_APPSECRET if self.KIS_USE_MOCK else self.KIS_REAL_APPSECRET

    @property
    def KIS_CANO(self) -> str:
        return self.KIS_MOCK_CANO if self.KIS_USE_MOCK else self.KIS_REAL_CANO

    @property
    def KIS_ACNT_PRDT_CD(self) -> str:
        return self.KIS_MOCK_ACNT_PRDT_CD if self.KIS_USE_MOCK else self.KIS_REAL_ACNT_PRDT_CD

    @property
    def kis_base_url(self) -> str:
        """KIS_USE_MOCK 에 따라 모의 또는 실전 베이스 URL"""
        return self.KIS_MOCK_BASE_URL if self.KIS_USE_MOCK else self.KIS_REAL_BASE_URL

    @property
    def predict_model_path(self) -> Path:
        """PREDICT_MODEL_DIR 를 프로젝트 루트 기준으로 해석 (절대경로 그대로 사용)."""
        root = Path(__file__).resolve().parents[2]
        raw = (self.PREDICT_MODEL_DIR or "").strip()
        if not raw:
            return (root / "predict_model" / "model" / "v1_260504").resolve()
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (root / p).resolve()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

# 싱글톤 설정 객체 생성
settings = Settings()