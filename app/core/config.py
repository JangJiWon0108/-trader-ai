"""
애플리케이션 설정 (Pydantic Settings).

.env 로드 후 KIS·Supabase·스케줄·매매 임계값·텔레그램·Gemini 등 런타임 상수를 한곳에서 제공한다.
`settings` 싱글톤이 라우트·서비스에서 임포트된다.
"""

# ─── 모듈 임포트 ───
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# ─── 설정 로드 ───

load_dotenv()


# ─── 스키마 정의 ───


class Settings(BaseSettings):
    PROJECT_NAME: str = "주식 분석 API"
    PROJECT_DESCRIPTION: str = "해외주식 잔고 조회 및 주식 예측 API"
    PROJECT_VERSION: str = "1.0.0"

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
    SCHEDULER_MINUTE_LOG_TO_SUPABASE: bool = Field(
        default=False,
        description="True일 때만 auto_sell 분 요약을 Supabase scheduler_minute_logs 에 저장(테이블·RLS 준비 후 켜기)",
    )

    # ── 매수/매도 주문 기본값 ──────────────────────────────────────────────────
    TRADING_BUY_QUANTITY: int = Field(default=1, description="종목당 1회 매수 수량 (주)")
    TRADING_MAX_POSITIONS: int = Field(default=10, description="최대 동시 보유 종목 수")
    TRADING_ORDER_TYPE: str = Field(default="00", description="주문 유형 (00: 지정가, 01: 시장가)")

    # ── 기술적 지표 파라미터 ──────────────────────────────────────────────────
    TECH_LOOKBACK_DAYS: int = Field(default=180, description="기술적 지표 계산에 사용할 과거 데이터 기간 (일)")
    TECH_SMA_SHORT: int = Field(default=20, description="단기 이동평균 기간 (골든크로스 기준)")
    TECH_SMA_LONG: int = Field(default=50, description="장기 이동평균 기간 (골든크로스 기준)")
    TECH_RSI_PERIOD: int = Field(default=14, description="RSI 계산 기간")
    TECH_MACD_SHORT: int = Field(default=12, description="MACD 단기 EMA 기간")
    TECH_MACD_LONG: int = Field(default=26, description="MACD 장기 EMA 기간")
    TECH_MACD_SIGNAL: int = Field(default=9, description="MACD 시그널 EMA 기간")

    # ── 매수 조건 임계값 ──────────────────────────────────────────────────────
    BUY_MODEL_ACCURACY_MIN: float = Field(default=80.0, description="매수 허용 최소 모델 정확도 (%)")
    BUY_RISE_PROB_MIN: float = Field(default=3.0, description="매수 허용 최소 상승 확률 (%)")
    BUY_RSI_MAX: float = Field(default=50.0, description="매수 허용 RSI 상한 (이 값 미만일 때 매수 신호)")
    BUY_SENTIMENT_MIN: float = Field(default=0.15, description="매수 허용 최소 감성 점수")
    BUY_TECH_MIN_WITH_SENTIMENT: int = Field(default=2, description="감성 조건 충족 시 필요한 최소 기술지표 매수 신호 수")
    BUY_TECH_MIN_WITHOUT_SENTIMENT: int = Field(default=3, description="감성 데이터 없을 때 필요한 최소 기술지표 매수 신호 수")
    BUY_SCORE_WEIGHT_RISE_PROB: float = Field(default=0.3, description="종합점수 가중치 — 상승확률")
    BUY_SCORE_WEIGHT_TECH: float = Field(default=0.4, description="종합점수 가중치 — 기술지표")
    BUY_SCORE_WEIGHT_SENTIMENT: float = Field(default=0.3, description="종합점수 가중치 — 감성점수")
    BUY_SCORE_WEIGHT_GOLDEN_CROSS: float = Field(default=1.5, description="기술지표 점수 내 골든크로스 가중치")
    BUY_SCORE_WEIGHT_RSI: float = Field(default=1.0, description="기술지표 점수 내 RSI 가중치")
    BUY_SCORE_WEIGHT_MACD: float = Field(default=1.0, description="기술지표 점수 내 MACD 가중치")

    # ── 매도 조건 임계값 ──────────────────────────────────────────────────────
    SELL_TAKE_PROFIT_PCT: float = Field(default=5.0, description="익절 기준 수익률 (%)")
    SELL_STOP_LOSS_PCT: float = Field(default=-7.0, description="손절 기준 수익률 (%, 음수)")
    SELL_RSI_OVERBOUGHT: float = Field(default=70.0, description="과매수 판단 RSI 기준 (이 값 초과 시 매도 신호)")
    SELL_SENTIMENT_MAX: float = Field(default=-0.15, description="부정 감성 판단 기준 (이 값 미만 시 매도 신호)")
    SELL_TECH_MIN_WITH_SENTIMENT: int = Field(default=2, description="부정 감성 충족 시 필요한 최소 기술지표 매도 신호 수")
    SELL_TECH_MIN_WITHOUT_SENTIMENT: int = Field(default=3, description="감성 데이터 없을 때 필요한 최소 기술지표 매도 신호 수")

    # ── 뉴스 감성 분석 파라미터 ───────────────────────────────────────────────
    SENTIMENT_RELEVANCE_THRESHOLD: float = Field(default=0.2, description="뉴스 기사 관련성 최소 점수 (이 값 미만 기사 제외)")
    SENTIMENT_LOOKBACK_DAYS: int = Field(default=3, description="뉴스 감성 분석 대상 기간 (일)")

    # ── 텔레그램 알림 (alarm/telegram.py) ─────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="텔레그램 봇 HTTP API 토큰")
    TELEGRAM_CHAT_ID: str = Field(
        default="",
        description="알림 수신 chat_id (봇에게 /start 후 getUpdates 등으로 확인)",
    )

    # ── Gemini LLM (루트 llm 패키지) ─────────────────────────────────────────
    GEMINI_MODEL_ID: str = Field(
        default="gemini-2.5-flash",
        description="Generative Language API generateContent 모델 ID",
    )
    GEMINI_API_KEY: str = Field(default="", description="Google AI / Gemini API 키 (쿼리 파라미터 key)")

    SCHEDULE_EOD_LLM_REPORT_ENABLED: bool = Field(
        default=True,
        description="Gemini 일일 마감 리포트를 텔레그램으로 보낼지 여부",
    )
    SCHEDULE_EOD_LLM_REPORT_TIME_KST: str = Field(
        default="07:00",
        description="일일 LLM 리포트 실행 시각 (KST HH:MM, SCHEDULE_AUTO_BUY_TIME 과 동일한 schedule 로컬 기준)",
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


settings = Settings()
