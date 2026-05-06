# db:schema

이 프로젝트의 DB 테이블 스키마 정의 레퍼런스.

DB 관련 작업 시 이 파일을 기준으로 컬럼명/타입을 참조할 것.

---

---

## economic_and_stock_data

```sql
CREATE TABLE economic_and_stock_data (
    "날짜" DATE PRIMARY KEY,
    "10년 기대 인플레이션율" NUMERIC,
    "장단기 금리차" NUMERIC,
    "기준금리" NUMERIC,
    "미시간대 소비자 심리지수" NUMERIC,
    "실업률" NUMERIC,
    "2년 만기 미국 국채 수익률" NUMERIC,
    "10년 만기 미국 국채 수익률" NUMERIC,
    "금융스트레스지수" NUMERIC,
    "개인 소비 지출" NUMERIC,
    "소비자 물가지수" NUMERIC,
    "5년 변동금리 모기지" NUMERIC,
    "미국 달러 환율" NUMERIC,
    "통화 공급량 M2" NUMERIC,
    "가계 부채 비율" NUMERIC,
    "GDP 성장률" NUMERIC,
    "나스닥 종합지수" NUMERIC,
    "S&P 500 지수" NUMERIC,
    "금 가격" NUMERIC,
    "달러 인덱스" NUMERIC,
    "나스닥 100" NUMERIC,
    "S&P 500 ETF" NUMERIC,
    "QQQ ETF" NUMERIC,
    "러셀 2000 ETF" NUMERIC,
    "다우 존스 ETF" NUMERIC,
    "VIX 지수" NUMERIC,
    "닛케이 225" NUMERIC,
    "상해종합" NUMERIC,
    "항셍" NUMERIC,
    "영국 FTSE" NUMERIC,
    "독일 DAX" NUMERIC,
    "프랑스 CAC 40" NUMERIC,
    "미국 전체 채권시장 ETF" NUMERIC,
    "TIPS ETF" NUMERIC,
    "투자등급 회사채 ETF" NUMERIC,
    "달러/엔" NUMERIC,
    "달러/위안" NUMERIC,
    "미국 리츠 ETF" NUMERIC,
    "애플" NUMERIC,
    "마이크로소프트" NUMERIC,
    "아마존" NUMERIC,
    "구글 A" NUMERIC,
    "구글 C" NUMERIC,
    "메타" NUMERIC,
    "테슬라" NUMERIC,
    "엔비디아" NUMERIC,
    "코스트코" NUMERIC,
    "넷플릭스" NUMERIC,
    "페이팔" NUMERIC,
    "인텔" NUMERIC,
    "시스코" NUMERIC,
    "컴캐스트" NUMERIC,
    "펩시코" NUMERIC,
    "암젠" NUMERIC,
    "허니웰 인터내셔널" NUMERIC,
    "스타벅스" NUMERIC,
    "몬델리즈" NUMERIC,
    "마이크론" NUMERIC,
    "브로드컴" NUMERIC,
    "어도비" NUMERIC,
    "텍사스 인스트루먼트" NUMERIC,
    "AMD" NUMERIC,
    "어플라이드 머티리얼즈" NUMERIC
);
```

---

## access_tokens

```sql
CREATE TABLE access_tokens (
    id SERIAL PRIMARY KEY,
    access_token TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expiration_time TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_access_tokens_expiration ON access_tokens(expiration_time);
CREATE INDEX idx_access_tokens_created_at ON access_tokens(created_at);

COMMENT ON TABLE access_tokens IS '한국투자증권 API 접근 토큰 정보';
COMMENT ON COLUMN access_tokens.access_token IS 'API 접근을 위한 JWT 토큰';
COMMENT ON COLUMN access_tokens.expiration_time IS '토큰 만료 시간';
COMMENT ON COLUMN access_tokens.is_active IS '토큰 활성 상태';
```

---

## predicted_stocks

```sql
CREATE TABLE IF NOT EXISTS predicted_stocks (
    id SERIAL PRIMARY KEY,
    "날짜" DATE NOT NULL,
    "애플_Predicted" NUMERIC,
    "애플_Actual" NUMERIC,
    "마이크로소프트_Predicted" NUMERIC,
    "마이크로소프트_Actual" NUMERIC,
    "아마존_Predicted" NUMERIC,
    "아마존_Actual" NUMERIC,
    "구글 A_Predicted" NUMERIC,
    "구글 A_Actual" NUMERIC,
    "구글 C_Predicted" NUMERIC,
    "구글 C_Actual" NUMERIC,
    "메타_Predicted" NUMERIC,
    "메타_Actual" NUMERIC,
    "테슬라_Predicted" NUMERIC,
    "테슬라_Actual" NUMERIC,
    "엔비디아_Predicted" NUMERIC,
    "엔비디아_Actual" NUMERIC,
    "코스트코_Predicted" NUMERIC,
    "코스트코_Actual" NUMERIC,
    "넷플릭스_Predicted" NUMERIC,
    "넷플릭스_Actual" NUMERIC,
    "페이팔_Predicted" NUMERIC,
    "페이팔_Actual" NUMERIC,
    "인텔_Predicted" NUMERIC,
    "인텔_Actual" NUMERIC,
    "시스코_Predicted" NUMERIC,
    "시스코_Actual" NUMERIC,
    "컴캐스트_Predicted" NUMERIC,
    "컴캐스트_Actual" NUMERIC,
    "펩시코_Predicted" NUMERIC,
    "펩시코_Actual" NUMERIC,
    "암젠_Predicted" NUMERIC,
    "암젠_Actual" NUMERIC,
    "허니웰 인터내셔널_Predicted" NUMERIC,
    "허니웰 인터내셔널_Actual" NUMERIC,
    "스타벅스_Predicted" NUMERIC,
    "스타벅스_Actual" NUMERIC,
    "몬델리즈_Predicted" NUMERIC,
    "몬델리즈_Actual" NUMERIC,
    "마이크론_Predicted" NUMERIC,
    "마이크론_Actual" NUMERIC,
    "브로드컴_Predicted" NUMERIC,
    "브로드컴_Actual" NUMERIC,
    "어도비_Predicted" NUMERIC,
    "어도비_Actual" NUMERIC,
    "텍사스 인스트루먼트_Predicted" NUMERIC,
    "텍사스 인스트루먼트_Actual" NUMERIC,
    "AMD_Predicted" NUMERIC,
    "AMD_Actual" NUMERIC,
    "어플라이드 머티리얼즈_Predicted" NUMERIC,
    "어플라이드 머티리얼즈_Actual" NUMERIC,
    "S&P 500 ETF_Predicted" NUMERIC,
    "S&P 500 ETF_Actual" NUMERIC,
    "QQQ ETF_Predicted" NUMERIC,
    "QQQ ETF_Actual" NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_prediction_date UNIQUE ("날짜")
);

CREATE INDEX IF NOT EXISTS idx_predicted_stocks_date ON predicted_stocks ("날짜");
```

---

## stock_analysis_results

```sql
CREATE TABLE IF NOT EXISTS stock_analysis_results (
    id SERIAL PRIMARY KEY,
    "Stock" TEXT NOT NULL,
    "MAE" NUMERIC,
    "MSE" NUMERIC,
    "RMSE" NUMERIC,
    "MAPE (%)" NUMERIC,
    "Accuracy (%)" NUMERIC,
    "Last Actual Price" NUMERIC,
    "Predicted Future Price" NUMERIC,
    "Predicted Rise" BOOLEAN,
    "Rise Probability (%)" NUMERIC,
    "Recommendation" TEXT,
    "Analysis" TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_analysis_stock ON stock_analysis_results ("Stock");
CREATE INDEX IF NOT EXISTS idx_stock_analysis_recommendation ON stock_analysis_results ("Recommendation");
CREATE INDEX IF NOT EXISTS idx_stock_analysis_rise_probability ON stock_analysis_results ("Rise Probability (%)");
```

---

## ticker_sentiment_analysis

```sql
CREATE TABLE ticker_sentiment_analysis (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    average_sentiment_score FLOAT NOT NULL,
    article_count INTEGER NOT NULL,
    calculation_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## stock_recommendations

```sql
CREATE TABLE stock_recommendations (
    "날짜" DATE,
    "종목" VARCHAR(50),
    "SMA20" NUMERIC,
    "SMA50" NUMERIC,
    "골든_크로스" BOOLEAN,
    "RSI" NUMERIC,
    "MACD" NUMERIC,
    "Signal" NUMERIC,
    "MACD_매수_신호" BOOLEAN,
    "추천_여부" BOOLEAN,
    PRIMARY KEY ("날짜", "종목")
);
```

