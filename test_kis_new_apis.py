"""
신규 계좌 (50187301) 기반 KIS API 테스트
테스트 대상 (해외주식 위주):
  1. 토큰 발급 (모의/실전)
  2. 해외주식 잔고 조회 (TTTS3012R / VTTS3012R) — 기존 검증
  3. 해외주식 체결기준잔고 (CTRP6504R / VTRP6504R) — inquire-present-balance
  4. 외화예수금 조회 (TTTC2101R) — foreign-margin (USD 잔고 직접 확인)
  5. 해외주식 기간별손익 (TTTS3039R) — inquire-period-profit
  6. 해외주식 기간거래내역 (TTTS3018R) — inquire-period-trans
  7. 해외주식 결제기준잔고 (CTRP6010R) — inquire-paymt-stdr-balance
"""

import os, sys, json, time
import requests
from datetime import datetime, timedelta

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def ok(msg): print(f"  {PASS}  {msg}")
def fail(msg): print(f"  {FAIL}  {msg}")
def info(msg): print(f"  {INFO}  {msg}")

def dump(label, data, keys=None):
    if keys:
        subset = {k: data.get(k) for k in keys if k in data}
        info(f"{label}: {json.dumps(subset, ensure_ascii=False)}")
    else:
        info(f"{label}: rt_cd={data.get('rt_cd')} msg1={data.get('msg1','')}")


def get_token(base_url, appkey, appsecret, label):
    url = f"{base_url}/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": appkey, "appsecret": appsecret}
    res = requests.post(url, json=body, timeout=15)
    data = res.json()
    if "access_token" in data:
        ok(f"[{label}] 토큰 발급 성공 | 만료: {data.get('access_token_token_expired','N/A')}")
        return data["access_token"]
    fail(f"[{label}] 토큰 실패: {data}")
    return None


def base_headers(token, appkey, appsecret, tr_id):
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": appkey,
        "appsecret": appsecret,
        "tr_id": tr_id,
    }


# ── 2. 해외주식 잔고 (기존) ─────────────────────────────────
def test_overseas_balance(base, token, appkey, appsecret, cano, acnt_cd, tr_id, label, exchange="NASD"):
    url = f"{base}/uapi/overseas-stock/v1/trading/inquire-balance"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "OVRS_EXCG_CD": exchange, "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "", "CTX_AREA_NK200": "",
    }
    res = requests.get(url, headers=base_headers(token, appkey, appsecret, tr_id), params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        holdings = data.get("output1", [])
        o2 = data.get("output2", {})
        usd_cash = o2.get("frcr_dncl_amt_2", o2.get("frcr_pchs_amt1", "?"))
        ok(f"[{label}] {exchange} 해외잔고 | 보유: {len(holdings)}종목 | output2.usd잔고유사: {usd_cash}")
        for h in holdings[:3]:
            info(f"  {h.get('ovrs_pdno')} {h.get('ovrs_item_name')} 수량={h.get('cblc_qty')} 평단={h.get('pchs_avg_pric')}")
    else:
        fail(f"[{label}] {exchange} 해외잔고 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")
        info(f"  raw: {json.dumps(data, ensure_ascii=False)[:300]}")


# ── 3. 해외주식 체결기준잔고 (inquire-present-balance) ────────
def test_present_balance(base, token, appkey, appsecret, cano, acnt_cd, tr_id, label):
    url = f"{base}/uapi/overseas-stock/v1/trading/inquire-present-balance"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "WCRC_FRCR_DVSN_CD": "02",  # 02: 외화
        "NATN_CD": "000",            # 000: 전체
        "TR_MKET_CD": "00",
        "INQR_DVSN_CD": "00",
    }
    res = requests.get(url, headers=base_headers(token, appkey, appsecret, tr_id), params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        o1 = data.get("output1", [])
        o2 = data.get("output2", {})
        ok(f"[{label}] 체결기준잔고 | output1: {len(o1)}건")
        for h in o1[:3]:
            info(f"  {h.get('pdno','?')} {h.get('prdt_name','?')} qty={h.get('cblc_qty13','?')}")
        if o2:
            info(f"  output2 keys: {list(o2.keys())[:8]}")
    else:
        fail(f"[{label}] 체결기준잔고 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")
        info(f"  raw: {json.dumps(data, ensure_ascii=False)[:400]}")


# ── 4. 외화예수금 조회 (foreign-margin) ──────────────────────
def test_foreign_margin(base, token, appkey, appsecret, cano, acnt_cd, tr_id, label):
    url = f"{base}/uapi/overseas-stock/v1/trading/foreign-margin"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
    }
    res = requests.get(url, headers=base_headers(token, appkey, appsecret, tr_id), params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        output = data.get("output", data.get("output1", []))
        if isinstance(output, list):
            ok(f"[{label}] 외화예수금 | {len(output)}통화")
            for row in output:
                crcy = row.get("crcy_cd", row.get("natn_name", "?"))
                amt = row.get("frcr_dncl_amt1", row.get("frcr_evlu_amt", "?"))
                info(f"  통화={crcy} 예수금={amt}")
        else:
            ok(f"[{label}] 외화예수금 output: {json.dumps(output, ensure_ascii=False)[:300]}")
    else:
        fail(f"[{label}] 외화예수금 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")
        info(f"  raw: {json.dumps(data, ensure_ascii=False)[:400]}")


# ── 5. 해외주식 기간별손익 (inquire-period-profit) ────────────
def test_period_profit(base, token, appkey, appsecret, cano, acnt_cd, tr_id, label):
    url = f"{base}/uapi/overseas-stock/v1/trading/inquire-period-profit"
    today = datetime.today()
    start = (today - timedelta(days=30)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "OVRS_EXCG_CD": "NASD",
        "NATN_CD": "840",
        "CRCY_CD": "USD",
        "PDNO": "",
        "SLL_BUY_DVSN_CD": "00",
        "ERLM_STRT_DT": start,
        "ERLM_END_DT": end,
        "CTX_AREA_FK200": "", "CTX_AREA_NK200": "",
    }
    res = requests.get(url, headers=base_headers(token, appkey, appsecret, tr_id), params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        o1 = data.get("output1", [])
        ok(f"[{label}] 기간손익 | {len(o1)}건 ({start}~{end})")
        for row in o1[:3]:
            info(f"  {row.get('pdno','?')} 실현손익={row.get('rlzt_pfls','?')}")
    else:
        fail(f"[{label}] 기간손익 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")
        info(f"  raw: {json.dumps(data, ensure_ascii=False)[:400]}")


# ── 6. 해외주식 기간거래내역 (inquire-period-trans) ───────────
def test_period_trans(base, token, appkey, appsecret, cano, acnt_cd, tr_id, label):
    url = f"{base}/uapi/overseas-stock/v1/trading/inquire-period-trans"
    today = datetime.today()
    start = (today - timedelta(days=30)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "OVRS_EXCG_CD": "NASD",
        "PDNO": "",
        "ORD_STRT_DT": start,
        "ORD_END_DT": end,
        "SLL_BUY_DVSN_CD": "00",
        "CCLD_NCCS_DVSN": "00",
        "OVRS_ORD_UNPR_DVSN": "0",
        "SORT_SQN": "DS",
        "CTX_AREA_NK200": "", "CTX_AREA_FK200": "",
    }
    res = requests.get(url, headers=base_headers(token, appkey, appsecret, tr_id), params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        o1 = data.get("output1", [])
        ok(f"[{label}] 기간거래내역 | {len(o1)}건 ({start}~{end})")
        for row in o1[:3]:
            info(f"  {row.get('ord_dt','?')} {row.get('pdno','?')} {row.get('sll_buy_dvsn_cd_name','?')} qty={row.get('ft_ccld_qty','?')}")
    else:
        fail(f"[{label}] 기간거래내역 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")
        info(f"  raw: {json.dumps(data, ensure_ascii=False)[:400]}")


# ── 7. 결제기준잔고 (inquire-paymt-stdr-balance) ─────────────
def test_paymt_stdr_balance(base, token, appkey, appsecret, cano, acnt_cd, tr_id, label):
    url = f"{base}/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance"
    today = datetime.today().strftime("%Y%m%d")
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "BASS_DT": today,
        "WCRC_FRCR_DVSN_CD": "02",
        "INQR_DVSN_CD": "00",
    }
    res = requests.get(url, headers=base_headers(token, appkey, appsecret, tr_id), params=params, timeout=15)
    data = res.json()
    if data.get("rt_cd") == "0":
        o1 = data.get("output1", [])
        ok(f"[{label}] 결제기준잔고 | {len(o1)}건")
        for row in o1[:3]:
            info(f"  {row.get('pdno','?')} qty={row.get('cblc_qty13','?')} 평단={row.get('avg_unpr3','?')}")
    else:
        fail(f"[{label}] 결제기준잔고 실패: {data.get('msg1','?')} ({data.get('msg_cd','?')})")
        info(f"  raw: {json.dumps(data, ensure_ascii=False)[:400]}")


# ── 실행 ──────────────────────────────────────────────────────
def run_mock():
    section("[ 모의투자 ]")
    base = os.getenv("KIS_MOCK_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    appkey = os.getenv("KIS_MOCK_APPKEY", "")
    appsecret = os.getenv("KIS_MOCK_APPSECRET", "")
    cano = os.getenv("KIS_MOCK_CANO", "")
    acnt_cd = os.getenv("KIS_MOCK_ACNT_PRDT_CD", "01")

    token = get_token(base, appkey, appsecret, "모의")
    if not token:
        return

    for ex in ["NASD", "NYSE", "AMEX"]:
        test_overseas_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3012R", "모의", ex)
        time.sleep(1)

    time.sleep(1)
    test_present_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTRP6504R", "모의")
    time.sleep(1)
    # TTTC2101R은 실전 전용 — 모의 건너뜀
    info("외화예수금(TTTC2101R): 실전 전용 TR, 모의 건너뜀")
    time.sleep(1)
    test_period_profit(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3039R", "모의")
    time.sleep(1)
    test_period_trans(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3018R", "모의")
    time.sleep(1)
    test_paymt_stdr_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTRP6010R", "모의")


def run_real():
    section("[ 실전투자 ]")
    base = os.getenv("KIS_REAL_BASE_URL", "https://openapi.koreainvestment.com:9443")
    appkey = os.getenv("KIS_REAL_APPKEY", "")
    appsecret = os.getenv("KIS_REAL_APPSECRET", "")
    cano = os.getenv("KIS_REAL_CANO", "")
    acnt_cd = os.getenv("KIS_REAL_ACNT_PRDT_CD", "01")

    token = get_token(base, appkey, appsecret, "실전")
    if not token:
        return

    for ex in ["NASD", "NYSE", "AMEX"]:
        test_overseas_balance(base, token, appkey, appsecret, cano, acnt_cd, "TTTS3012R", "실전", ex)

    test_present_balance(base, token, appkey, appsecret, cano, acnt_cd, "CTRP6504R", "실전")
    test_foreign_margin(base, token, appkey, appsecret, cano, acnt_cd, "TTTC2101R", "실전")
    test_period_profit(base, token, appkey, appsecret, cano, acnt_cd, "TTTS3039R", "실전")
    test_period_trans(base, token, appkey, appsecret, cano, acnt_cd, "TTTS3018R", "실전")
    test_paymt_stdr_balance(base, token, appkey, appsecret, cano, acnt_cd, "CTRP6010R", "실전")


if __name__ == "__main__":
    # 토큰 1회만 발급 후 전달 (분당 1회 제한 우회)
    base = os.getenv("KIS_MOCK_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    appkey = os.getenv("KIS_MOCK_APPKEY", "")
    appsecret = os.getenv("KIS_MOCK_APPSECRET", "")
    cano = os.getenv("KIS_MOCK_CANO", "")
    acnt_cd = os.getenv("KIS_MOCK_ACNT_PRDT_CD", "01")

    section("[ 모의투자 — 신규 계좌 API 테스트 ]")
    token = get_token(base, appkey, appsecret, "모의")
    if not token:
        sys.exit(1)

    for ex in ["NASD", "NYSE", "AMEX"]:
        test_overseas_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3012R", "모의", ex)
        time.sleep(1)

    time.sleep(1)
    test_present_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTRP6504R", "모의")
    time.sleep(1)
    info("외화예수금(TTTC2101R): 실전 전용 TR, 모의 건너뜀")
    time.sleep(1)
    test_period_profit(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3039R", "모의")
    time.sleep(1)
    test_period_trans(base, token, appkey, appsecret, cano, acnt_cd, "VTTS3018R", "모의")
    time.sleep(1)
    test_paymt_stdr_balance(base, token, appkey, appsecret, cano, acnt_cd, "VTRP6010R", "모의")
