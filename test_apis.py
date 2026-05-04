"""
외부 API 연결 테스트 스크립트
테스트 대상:
  1. Supabase DB
  2. KIS 모의투자 (토큰 발급 + 해외잔고 + 국내잔고)
  3. KIS 실전투자 (토큰 발급 + 해외잔고 + 국내잔고)
  4. FRED API (경제지표 1개)
  5. Yahoo Finance (종가 1개)
  6. Alpha Vantage NEWS_SENTIMENT (1 ticker)
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

PASS = "✅ PASS"
FAIL = "❌ FAIL"

def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)

def ok(msg):
    print(f"  {PASS}  {msg}")

def fail(msg):
    print(f"  {FAIL}  {msg}")

# ──────────────────────────────────────────────────
# 1. Supabase
# ──────────────────────────────────────────────────
def test_supabase():
    section("1. Supabase DB")
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        client = create_client(url, key)
        res = client.table("access_tokens").select("id").limit(1).execute()
        ok(f"연결 성공 | access_tokens 행 수: {len(res.data)}")
    except Exception as e:
        fail(f"Supabase 오류: {e}")

# ──────────────────────────────────────────────────
# 2. KIS 토큰 발급 (공통)
# ──────────────────────────────────────────────────
def get_kis_token(base_url, appkey, appsecret, label):
    url = f"{base_url}/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": appkey, "appsecret": appsecret}
    res = requests.post(url, json=body, timeout=15)
    data = res.json()
    if "access_token" in data:
        ok(f"[{label}] 토큰 발급 성공 | 만료: {data.get('access_token_token_expired', 'N/A')}")
        return data["access_token"]
    else:
        fail(f"[{label}] 토큰 발급 실패: {data}")
        return None

def get_kis_overseas_balance(base_url, token, appkey, appsecret, cano, acnt_cd, tr_id, label, exchange="NASD"):
    url = f"{base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": appkey,
        "appsecret": appsecret,
        "tr_id": tr_id,
    }
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "OVRS_EXCG_CD": exchange, "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "", "CTX_AREA_NK200": "",
    }
    res = requests.get(url, headers=headers, params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        holdings = data.get("output1", [])
        ok(f"[{label}] {exchange} 해외잔고 조회 성공 | 보유종목: {len(holdings)}개")
    else:
        fail(f"[{label}] {exchange} 해외잔고 조회 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")

def get_kis_domestic_balance(base_url, token, appkey, appsecret, cano, acnt_cd, tr_id, label):
    url = f"{base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": appkey,
        "appsecret": appsecret,
        "tr_id": tr_id,
    }
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
        "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    res = requests.get(url, headers=headers, params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        holdings = data.get("output1", [])
        ok(f"[{label}] 국내잔고 조회 성공 | 보유종목: {len(holdings)}개")
    else:
        fail(f"[{label}] 국내잔고 조회 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")

def test_kis_mock():
    section("2. KIS 모의투자")
    base = os.getenv("KIS_MOCK_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    appkey = os.getenv("KIS_MOCK_APPKEY", "")
    appsecret = os.getenv("KIS_MOCK_APPSECRET", "")
    cano = os.getenv("KIS_MOCK_CANO", "")
    acnt_cd = os.getenv("KIS_MOCK_ACNT_PRDT_CD", "01")

    if not appkey:
        fail("KIS_MOCK_APPKEY 없음"); return

    token = get_kis_token(base, appkey, appsecret, "모의")
    if not token:
        return

    for ex in ["NASD", "NYSE", "AMEX"]:
        try:
            get_kis_overseas_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3012R", "모의", ex)
        except Exception as e:
            fail(f"[모의] {ex} 해외잔고 예외: {e}")

    try:
        get_kis_domestic_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTTC8434R", "모의")
    except Exception as e:
        fail(f"[모의] 국내잔고 예외: {e}")

def test_kis_real():
    section("3. KIS 실전투자")
    base = os.getenv("KIS_REAL_BASE_URL", "https://openapi.koreainvestment.com:9443")
    appkey = os.getenv("KIS_REAL_APPKEY", "")
    appsecret = os.getenv("KIS_REAL_APPSECRET", "")
    cano = os.getenv("KIS_REAL_CANO", "")
    acnt_cd = os.getenv("KIS_REAL_ACNT_PRDT_CD", "01")

    if not appkey:
        fail("KIS_REAL_APPKEY 없음"); return

    token = get_kis_token(base, appkey, appsecret, "실전")
    if not token:
        return

    for ex in ["NASD", "NYSE", "AMEX"]:
        try:
            get_kis_overseas_balance(base, token, appkey, appsecret, cano, acnt_cd, "TTTS3012R", "실전", ex)
        except Exception as e:
            fail(f"[실전] {ex} 해외잔고 예외: {e}")

    try:
        get_kis_domestic_balance(base, token, appkey, appsecret, cano, acnt_cd, "TTTC8434R", "실전")
    except Exception as e:
        fail(f"[실전] 국내잔고 예외: {e}")

# ──────────────────────────────────────────────────
# 4. FRED API
# ──────────────────────────────────────────────────
def test_fred():
    section("4. FRED API (경제지표)")
    api_key = os.getenv("FRED_API_KEY", "")
    if not api_key:
        fail("FRED_API_KEY 없음"); return

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "DGS10",
        "api_key": api_key,
        "file_type": "json",
        "observation_start": (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "observation_end": datetime.today().strftime("%Y-%m-%d"),
        "limit": 5,
    }
    try:
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        obs = data.get("observations", [])
        if obs:
            latest = obs[-1]
            ok(f"DGS10 (10년 국채) 최근값: {latest['value']} ({latest['date']})")
        else:
            fail(f"데이터 없음: {data}")
    except Exception as e:
        fail(f"FRED 예외: {e}")

# ──────────────────────────────────────────────────
# 5. Yahoo Finance (direct HTTP)
# ──────────────────────────────────────────────────
def test_yahoo():
    section("5. Yahoo Finance")
    symbol = "AAPL"
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=7)

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": int(start_dt.timestamp()),
        "period2": int(end_dt.timestamp()),
        "interval": "1d",
        "includePrePost": "false",
    }
    try:
        res = sess.get(url, params=params, timeout=15)
        result = res.json().get("chart", {}).get("result", [None])[0]
        if result:
            closes = result["indicators"]["quote"][0].get("close", [])
            closes = [c for c in closes if c is not None]
            ok(f"AAPL 최근 종가: {closes[-1]:.2f} USD (최근 {len(closes)}일)")
        else:
            fail(f"Yahoo Finance 데이터 없음: {res.text[:200]}")
    except Exception as e:
        fail(f"Yahoo Finance 예외: {e}")

# ──────────────────────────────────────────────────
# 6. Alpha Vantage NEWS_SENTIMENT
# ──────────────────────────────────────────────────
def test_alpha_vantage():
    section("6. Alpha Vantage NEWS_SENTIMENT")
    keys = {
        "MAIN": os.getenv("ALPHA_VANTAGE_API_KEY_MAIN", ""),
        "SUB_1": os.getenv("ALPHA_VANTAGE_API_KEY_SUB_1", ""),
        "SUB_2": os.getenv("ALPHA_VANTAGE_API_KEY_SUB_2", ""),
    }
    base_url = "https://www.alphavantage.co/query"
    time_from = (datetime.now() - timedelta(days=3)).strftime("%Y%m%dT0000")

    for label, api_key in keys.items():
        if not api_key:
            fail(f"[{label}] 키 없음"); continue
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": "NVDA",
            "time_from": time_from,
            "limit": 5,
            "apikey": api_key,
        }
        try:
            res = requests.get(base_url, params=params, timeout=20)
            data = res.json()
            if "feed" in data:
                count = len(data["feed"])
                ok(f"[{label}] NVDA 뉴스 기사 수: {count} (키: {api_key[:8]}...)")
            elif "Note" in data or "Information" in data:
                msg = data.get("Note") or data.get("Information", "")
                fail(f"[{label}] 속도 제한 또는 무효 키: {msg[:80]}")
            else:
                fail(f"[{label}] 예상 외 응답: {str(data)[:150]}")
        except Exception as e:
            fail(f"[{label}] Alpha Vantage 예외: {e}")

# ──────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'#'*50}")
    print(f"  외부 API 테스트  ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print(f"{'#'*50}")

    test_supabase()
    test_kis_mock()
    test_kis_real()
    test_fred()
    test_yahoo()
    test_alpha_vantage()

    print(f"\n{'='*50}")
    print("  테스트 완료")
    print(f"{'='*50}\n")
