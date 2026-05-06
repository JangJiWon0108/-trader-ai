"""
한국투자증권(KIS) REST API 연동: 토큰·잔고·주문·예약·체결 조회 등.

`app.api.routes.balance` 및 스케줄러에서 호출된다. 토큰은 메모리·Supabase 와
1분당 갱신 제한을 함께 사용한다.
"""

# ─── 모듈 임포트 ───
import json
import time
from datetime import datetime, timedelta
from threading import Lock

import pytz
import requests

from app.core.config import settings
from app.db.supabase import supabase
from app.services.auth_service import parse_expiration_date
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── 상수 정의 (토큰 캐시) ───

_token_cache = {
    "access_token": None,
    "expires_at": None
}
_last_refresh_time = 0  # 마지막 토큰 갱신 시간
_refresh_lock = Lock()

# ─── 공개 API ───


def get_access_token():
    """한국투자증권 API 접근 토큰 발급 또는 캐시된 토큰 반환"""
    global _token_cache, _last_refresh_time
    
    # 현재 시간
    now = datetime.now(pytz.UTC)
    
    # 메모리에 캐시된 토큰이 있고 유효하면 그것을 사용
    if _token_cache["access_token"] and _token_cache["expires_at"] and now < _token_cache["expires_at"]:
        logger.info("메모리에 캐시된 토큰 사용")
        return _token_cache["access_token"]
    
    # 1분 제한 체크 및 락 획득
    current_time = time.time()
    if current_time - _last_refresh_time < 60:
        time_to_wait = 60 - (current_time - _last_refresh_time)
        logger.info(f"1분 제한으로 {time_to_wait:.1f}초 대기")
        time.sleep(time_to_wait)
    
    with _refresh_lock:  # 동시성 방지
        # 락 획득 후 다시 캐시 확인
        if _token_cache["access_token"] and _token_cache["expires_at"] and now < _token_cache["expires_at"]:
            logger.info("락 내에서 캐시된 토큰 사용")
            return _token_cache["access_token"]
        
        try:
            # 테이블에서 토큰 레코드 조회
            response = supabase.table("access_tokens").select("*").order("created_at", desc=True).limit(1).execute()
            
            if response.data:
                token_data = response.data[0]
                
                # 이 부분을 수정 - auth_service의 parse_expiration_date 함수 사용
                expiration_time = parse_expiration_date(token_data["expiration_time"])
                
                if now < expiration_time:  # 토큰이 아직 유효한 경우
                    logger.info(f"기존 토큰 사용 - 만료까지 남은 시간: {(expiration_time - now)}")
                    _token_cache["access_token"] = token_data["access_token"]
                    _token_cache["expires_at"] = expiration_time
                    _last_refresh_time = current_time
                    return token_data["access_token"]
                
                logger.info("토큰 만료됨, 갱신 필요")
                # 토큰이 만료된 경우 갱신
                token = refresh_token_with_retry(token_data["id"])
                _token_cache["access_token"] = token
                _token_cache["expires_at"] = now + timedelta(days=1)
                _last_refresh_time = current_time
                return token
            else:
                logger.info("토큰 레코드 없음, 새로 생성")
                token = refresh_token_with_retry()
                _token_cache["access_token"] = token
                _token_cache["expires_at"] = now + timedelta(days=1)
                _last_refresh_time = current_time
                return token
                
        except Exception as e:
            logger.info(f"토큰 조회 오류: {str(e)}")
            if _token_cache["access_token"]:
                logger.info("DB 조회 오류 - 메모리에 캐시된 토큰 사용")
                return _token_cache["access_token"]
            raise Exception(f"토큰 발급 실패: {str(e)}")

def refresh_token_with_retry(record_id=None, max_retries=3):
    """토큰 갱신을 재시도하며 처리"""
    for attempt in range(max_retries):
        try:
            url = f"{settings.kis_base_url}/oauth2/tokenP"
            data = {
                "grant_type": "client_credentials",
                "appkey": settings.KIS_APPKEY,
                "appsecret": settings.KIS_APPSECRET
            }
            
            response = requests.post(url, json=data)
            response_data = response.json()
            
            if 'access_token' not in response_data:
                raise Exception(f"토큰 발급 실패: {response_data}")
            
            access_token = response_data["access_token"]
            expires_in = response_data.get("expires_in", 86400)  # 기본값 24시간(초)
            now = datetime.now(pytz.UTC)
            expiration_time = now + timedelta(seconds=expires_in)
            
            token_data = {
                "access_token": access_token,
                "expiration_time": expiration_time.isoformat(),
                "is_active": True
            }
            
            # 레코드 ID가 있으면 업데이트, 없으면 새로 생성
            if record_id:
                supabase.table("access_tokens").update(token_data).eq("id", record_id).execute()
                logger.info("토큰 업데이트 완료")
            else:
                supabase.table("access_tokens").insert(token_data).execute()
                logger.info("새 토큰 레코드 생성 완료")
            
            return access_token
            
        except Exception as e:
            logger.info(f"토큰 갱신 오류 (시도 {attempt+1}/{max_retries}): {str(e)}")
            if "EGW00133" in str(e) and attempt < max_retries - 1:
                logger.info("1분 제한 에러 발생, 61초 대기 후 재시도")
                time.sleep(61)  # 1분 이상 대기
            else:
                raise

def get_domestic_balance():
    """국내주식 잔고 조회"""
    # 토큰 가져오기
    access_token = get_access_token()
    
    url = f"{settings.kis_base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    tr_id = "TTTC8434R" if not settings.KIS_USE_MOCK else "VTTC8434R"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": settings.KIS_APPKEY,
        "appsecret": settings.KIS_APPSECRET,
        "tr_id": tr_id,
    }
    
    params = {
        "CANO": settings.KIS_CANO,
        "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            result = response.json()
            
            # API 응답에 오류가 있고, 재시도 가능한 경우
            if 'rt_cd' in result and result['rt_cd'] != '0' and attempt < max_retries - 1:
                logger.info(f"API 오류: {result['msg_cd']} - {result.get('msg1', '알 수 없는 오류')}. 토큰 갱신 후 재시도...")
                # 토큰 강제 갱신 후 재시도
                access_token = get_access_token()
                headers["authorization"] = f"Bearer {access_token}"
                time.sleep(1)  # 재시도 전 1초 대기
                continue
            
            return result
            
        except Exception as e:
            logger.info(f"잔고 조회 중 오류 발생 (시도 {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 재시도 전 1초 대기
            else:
                raise

def get_overseas_balance(ovrs_excg_cd="NASD"):
    """해외주식 잔고 조회
    
    Args:
        ovrs_excg_cd (str, optional): 거래소 코드. Defaults to "NASD".
            NASD: 나스닥, NYSE: 뉴욕, AMEX: 아멕스
    """
    # 토큰 가져오기
    access_token = get_access_token()
    
    url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
    
    tr_id = "TTTS3012R" if not settings.KIS_USE_MOCK else "VTTS3012R"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": settings.KIS_APPKEY,
        "appsecret": settings.KIS_APPSECRET,
        "tr_id": tr_id,
    }
    
    params = {
        "CANO": settings.KIS_CANO,
        "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
        "OVRS_EXCG_CD": ovrs_excg_cd,  # 매개변수로 받은 거래소 코드 사용
        "TR_CRCY_CD": "USD",     # 통화코드 USD
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": ""
    }
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            result = response.json()
            
            # API 응답에 오류가 있고, 재시도 가능한 경우
            if 'rt_cd' in result and result['rt_cd'] != '0' and attempt < max_retries - 1:
                logger.info(f"API 오류: {result['msg_cd']} - {result.get('msg1', '알 수 없는 오류')}. 토큰 갱신 후 재시도...")
                # 토큰 강제 갱신 후 재시도
                access_token = get_access_token()
                headers["authorization"] = f"Bearer {access_token}"
                time.sleep(1)
                continue
            
            return result
            
        except Exception as e:
            logger.info(f"잔고 조회 중 오류 발생 (시도 {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 재시도 전 1초 대기
            else:
                raise

def get_all_overseas_balances():
    """모든 거래소의 해외주식 잔고 조회"""
    # 주요 거래소 목록
    exchanges = ["NASD", "NYSE", "AMEX"]
    all_holdings = []
    
    for exchange in exchanges:
        try:
            result = get_overseas_balance(exchange)
            
            if result.get("rt_cd") == "0" and "output1" in result:
                holdings = result.get("output1", [])
                if holdings:
                    all_holdings.extend(holdings)
            else:
                logger.info(f"{exchange} 거래소 잔고 조회 실패: {result.get('msg1', '알 수 없는 오류')}")
                
            # API 요청 간 지연 (KIS 초당 1건 제한)
            time.sleep(1.1)
            
        except Exception as e:
            logger.info(f"{exchange} 거래소 잔고 조회 중 오류: {str(e)}")
    
    # 동일 종목이 NASD/NYSE/AMEX 각 조회에 중복 포함되는 경우 제거 (첫 조회 순서 유지)
    seen_pdno = set()
    deduped_holdings = []
    for h in all_holdings:
        pdno = (h.get("ovrs_pdno") or "").strip()
        if pdno:
            if pdno in seen_pdno:
                continue
            seen_pdno.add(pdno)
        deduped_holdings.append(h)

    # 통합된 잔고 정보 반환
    if deduped_holdings:
        return {
            "rt_cd": "0",
            "msg_cd": "00000",
            "msg1": "모든 거래소 잔고 조회 완료",
            "output1": deduped_holdings,
            "output2": {}  # 합산 정보는 필요시 계산
        }
    else:
        return {
            "rt_cd": "0",
            "msg_cd": "00000",
            "msg1": "보유 종목이 없습니다.",
            "output1": deduped_holdings,
            "output2": {}
        }

# 추가: 해외주식 예약주문 접수
def overseas_order_resv(order_data):
    """해외주식 예약주문 접수"""
    try:
        access_token = get_access_token()
        url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/order-resv"
        
        is_mock = settings.KIS_USE_MOCK
        
        # 매수/매도 여부 및 거래소에 따라 TR_ID 결정
        is_buy = order_data.get("is_buy", True)
        ovrs_excg_cd = order_data.get("OVRS_EXCG_CD", "")
        
        if ovrs_excg_cd in ["NASD", "NYSE", "AMEX"]:  # 미국 주식
            if is_buy:
                tr_id = "VTTT3014U" if is_mock else "TTTT3014U"  # 미국 매수 예약
            else:
                tr_id = "VTTT3016U" if is_mock else "TTTT3016U"  # 미국 매도 예약
        else:  # 기타 거래소
            tr_id = "VTTS3013U" if is_mock else "TTTS3013U"  # 중국/홍콩/일본/베트남 예약
            
            # 중국/홍콩/일본/베트남의 경우 매수/매도 구분 코드 추가
            if not is_buy:
                order_data["SLL_BUY_DVSN_CD"] = "01"  # 매도
            else:
                order_data["SLL_BUY_DVSN_CD"] = "02"  # 매수
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": tr_id
        }
        
        # 필수 파라미터를 포함한 요청 데이터 준비
        request_body = order_data.copy()
        if "is_buy" in request_body:
            del request_body["is_buy"]  # API 요청에는 필요 없는 필드 제거
            
        # 필수 파라미터 설정
        request_body["RVSE_CNCL_DVSN_CD"] = "00"  # 정정취소구분코드 (00: 주문시 필수)
        
        response = requests.post(url, headers=headers, json=request_body)
        result = response.json()
        
        return result
    except Exception as e:
        logger.info(f"예약주문 접수 중 오류 발생: {str(e)}")
        raise

def inquire_psamount(params):
    """해외주식 매수가능금액 조회"""
    try:
        access_token = get_access_token()
        url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/inquire-psamount"
        tr_id = "TTTS3007R" if not settings.KIS_USE_MOCK else "VTTS3007R"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": tr_id,
        }
        
        # 기존 파라미터 유지
        base_params = {
            "CANO": params.get("CANO"),
            "ACNT_PRDT_CD": params.get("ACNT_PRDT_CD"),
            "OVRS_EXCG_CD": params.get("OVRS_EXCG_CD"),
            "OVRS_ORD_UNPR": params.get("OVRS_ORD_UNPR"),
            "ITEM_CD": params.get("ITEM_CD"),
            
            # 추가 필수 파라미터
            "AFHR_FLPR_YN": "N",  # 장후플래그여부
            "OFL_YN": "N",        # 오프라인여부
            "INQR_DVSN": "02",    # 조회구분 (02: 상세조회)
            "UNPR_DVSN": "01",    # 단가구분 (01: 기본값)
            "FUND_STTL_ICLD_YN": "N",  # 펀드결제포함여부
            "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액자동상환여부
            "PRCS_DVSN": "00",    # 처리구분 
            "CTX_AREA_FK100": "", # 연속조회검색조건100
            "CTX_AREA_NK100": ""  # 연속조회키100
        }
        
        response = requests.get(url, headers=headers, params=base_params)
        result = response.json()
        
        return result
    except Exception as e:
        logger.info(f"매수가능금액 조회 중 오류 발생: {str(e)}")
        raise

# 추가: 해외주식 현재체결가 조회
def get_current_price(params):
    """해외주식 현재체결가 조회"""
    try:
        access_token = get_access_token()
        url = f"{settings.kis_base_url}/uapi/overseas-price/v1/quotations/price"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": "HHDFS00000300",
        }
        
        response = requests.get(url, headers=headers, params=params)
        result = response.json()
        
        return result
    except Exception as e:
        logger.info(f"현재체결가 조회 중 오류 발생: {str(e)}")
        raise

def get_overseas_nccs(params):
    """해외주식 미체결내역 조회"""
    try:
        access_token = get_access_token()
        
        if settings.KIS_USE_MOCK:
            url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/inquire-order"
            tr_id = "VTTS3035R"
        else:
            url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/inquire-nccs"
            tr_id = "TTTS3018R"
            
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": tr_id,
        }
        
        response = requests.get(url, headers=headers, params=params)
        result = response.json()
        
        if settings.KIS_USE_MOCK and 'output' in result and isinstance(result['output'], list):
            result['output'] = [item for item in result['output'] if int(item.get('nccs_qty', 0)) > 0]
        
        return result
    except Exception as e:
        logger.info(f"미체결내역 조회 중 오류 발생: {str(e)}")
        raise

def _normalize_order_inquiry_output(result: dict) -> dict:
    """inquire-order 응답 output 을 항상 list[dict] 로 맞춘다."""
    out = result.get("output")
    if out is None:
        result["output"] = []
    elif isinstance(out, dict):
        result["output"] = [out]
    elif not isinstance(out, list):
        result["output"] = []
    return result


def get_overseas_order_detail(params, *, only_unfilled_pending: bool = False):
    """해외주식 주문·체결 조회 (VTTS3035R / TTTS3035R).

    only_unfilled_pending=True 이면 미체결 잔량(nccs_qty)이 있는 행만 남긴다 (미체결 화면용).
    False 이면 필터 없이 정규화된 리스트를 반환한다 (체결 피드·당일 손익 집계용).
    """
    try:
        access_token = get_access_token()
        
        url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/inquire-order"
        tr_id = "VTTS3035R" if settings.KIS_USE_MOCK else "TTTS3035R"
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": tr_id,
        }
        
        logger.info(f"API 요청: {url}")
        logger.info(f"파라미터: {params}")
        
        response = requests.get(url, headers=headers, params=params)
        
        logger.info(f"API 응답 상태 코드: {response.status_code}")
        logger.info(f"API 응답 본문: {response.text[:200] if response.text else '비어있음'}")
        
        if response.status_code == 404:
            return {
                "rt_cd": "0",
                "msg_cd": "NODATA",
                "msg1": "해당 API를 사용할 수 없습니다.",
                "output": []
            }
        
        if not response.text:
            return {
                "rt_cd": "0",
                "msg_cd": "NODATA",
                "msg1": "응답 데이터가 없습니다.",
                "output": []
            }
        
        try:
            result = response.json()
            result = _normalize_order_inquiry_output(result)
            if only_unfilled_pending and isinstance(result.get("output"), list):
                def _nq(item):
                    try:
                        return int(float(str(item.get("nccs_qty", "0") or "0")))
                    except (TypeError, ValueError):
                        return 0
                result["output"] = [item for item in result["output"] if _nq(item) > 0]
            return result
        except ValueError:
            return {
                "rt_cd": "0",
                "msg_cd": "PARSEERR",
                "msg1": "응답 파싱 오류",
                "output": []
            }
    except Exception as e:
        logger.info(f"주문체결내역 조회 중 오류 발생: {str(e)}")
        return {
            "rt_cd": "0", 
            "msg_cd": "ERROR",
            "msg1": f"API 호출 오류: {str(e)}",
            "output": []
        }


def fetch_overseas_orders_for_period(ord_strt_dt: str, ord_end_dt: str, ovrs_excg_cd: str | None) -> dict:
    """해외주식 주문·체결 조회 (공식 ORD_STRT_DT / ORD_END_DT 파라미터)."""
    is_mock = settings.KIS_USE_MOCK
    ovrs = "" if is_mock else (ovrs_excg_cd or "NASD")
    params = {
        "CANO": settings.KIS_CANO,
        "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
        "PDNO": "" if is_mock else "%",
        "ORD_STRT_DT": ord_strt_dt,
        "ORD_END_DT": ord_end_dt,
        "SLL_BUY_DVSN": "00",
        "CCLD_NCCS_DVSN": "00" if is_mock else "01",
        "OVRS_EXCG_CD": ovrs,
        "SORT_SQN": "AS",
        "ORD_DT": "",
        "ORD_GNO_BRNO": "00000",
        "ODNO": "",
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }
    return get_overseas_order_detail(params, only_unfilled_pending=False)


def get_merged_overseas_filled_orders(days: int = 30) -> list[dict]:
    """최근 days 일간 체결(또는 모의: 전체 후 ft_ccld_qty 필터) 주문 행을 거래소별로 합친다."""
    end = datetime.now()
    start = end - timedelta(days=max(1, days))
    end_s = end.strftime("%Y%m%d")
    start_s = start.strftime("%Y%m%d")
    merged: list[dict] = []
    seen: set[tuple] = set()

    if settings.KIS_USE_MOCK:
        res = fetch_overseas_orders_for_period(start_s, end_s, "")
        if res.get("rt_cd") == "0" and isinstance(res.get("output"), list):
            merged.extend(res["output"])
    else:
        for ex in ("NASD", "NYSE", "AMEX"):
            res = fetch_overseas_orders_for_period(start_s, end_s, ex)
            if res.get("rt_cd") == "0" and isinstance(res.get("output"), list):
                merged.extend(res["output"])
            time.sleep(0.25)

    filled: list[dict] = []
    for item in merged:
        try:
            ccld = float(str(item.get("ft_ccld_qty", "0") or "0"))
        except (TypeError, ValueError):
            ccld = 0.0
        if ccld <= 0:
            continue
        key = (
            str(item.get("odno", "")),
            str(item.get("ord_dt", "")),
            str(item.get("pdno", "")),
            str(item.get("sll_buy_dvsn_cd", "")),
            str(item.get("ft_ccld_qty", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        filled.append(item)
    return filled

def get_overseas_order_resv_list(params):
    """해외주식 예약주문 조회"""
    try:
        if settings.KIS_USE_MOCK:
            # 모의투자에서는 지원되지 않으므로 안내 메시지 반환
            return {
                "rt_cd": "0",
                "msg_cd": "MOCK_UNSUPPORTED",
                "msg1": "모의투자 환경에서는 해외주식 예약주문조회 API를 지원하지 않습니다.",
                "output": []
            }
        
        # 실전투자 환경에서 API 호출
        access_token = get_access_token()
        
        # 거래소 코드에 따라 TR_ID 결정
        ovrs_excg_cd = params.get("OVRS_EXCG_CD", "")
        if ovrs_excg_cd in ["NASD", "NYSE", "AMEX"] or not ovrs_excg_cd:
            # 미국 주식
            tr_id = "TTTT3039R"
        else:
            # 아시아 주식 (일본, 중국, 홍콩, 베트남)
            tr_id = "TTTS3014R"
            
        url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/order-resv-list"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": tr_id,
        }
        
        # 디버깅 정보
        logger.info(f"예약주문조회 API 요청: {url}")
        logger.info(f"파라미터: {params}")
        
        response = requests.get(url, headers=headers, params=params)
        
        # 응답 확인
        logger.info(f"API 응답 상태 코드: {response.status_code}")
        
        if response.status_code != 200:
            return {
                "rt_cd": "1",
                "msg_cd": f"HTTP_{response.status_code}",
                "msg1": f"API 호출 실패: HTTP {response.status_code}",
                "output": []
            }
        
        if not response.text:
            return {
                "rt_cd": "0",
                "msg_cd": "NODATA",
                "msg1": "응답 데이터가 없습니다.",
                "output": []
            }
        
        try:
            result = response.json()
            return result
        except ValueError:
            return {
                "rt_cd": "1",
                "msg_cd": "PARSEERR",
                "msg1": "응답 파싱 오류",
                "output": []
            }
    except Exception as e:
        logger.info(f"예약주문조회 중 오류 발생: {str(e)}")
        return {
            "rt_cd": "1", 
            "msg_cd": "ERROR",
            "msg1": f"API 호출 오류: {str(e)}",
            "output": []
        }

def order_overseas_stock(order_data):
    """해외주식 주문 실행"""
    try:
        # 토큰 가져오기
        access_token = get_access_token()
        
        # 기본 계좌정보 설정
        if "CANO" not in order_data or not order_data["CANO"]:
            order_data["CANO"] = settings.KIS_CANO
        if "ACNT_PRDT_CD" not in order_data or not order_data["ACNT_PRDT_CD"]:
            order_data["ACNT_PRDT_CD"] = settings.KIS_ACNT_PRDT_CD
            
        is_mock = settings.KIS_USE_MOCK
        
        # 매수/매도 여부 확인
        is_buy = order_data.get("is_buy", True)
        
        # 거래소 코드에 따라 tr_id 결정
        ovrs_excg_cd = order_data.get("OVRS_EXCG_CD", "")
        
        # tr_id 결정 (매수/매도 및 거래소에 따라 다름)
        if ovrs_excg_cd in ["NASD", "NYSE", "AMEX"]:
            # 미국 주식
            if is_buy:
                tr_id = "VTTT1002U" if is_mock else "TTTT1002U"  # 미국 매수
            else:
                tr_id = "VTTT1001U" if is_mock else "TTTT1006U"  # 미국 매도
        elif ovrs_excg_cd == "TKSE":
            # 일본 주식
            if is_buy:
                tr_id = "VTTS0308U" if is_mock else "TTTS0308U"  # 일본 매수
            else:
                tr_id = "VTTS0307U" if is_mock else "TTTS0307U"  # 일본 매도
        elif ovrs_excg_cd == "SHAA":
            # 상해 주식
            if is_buy:
                tr_id = "VTTS0202U" if is_mock else "TTTS0202U"  # 상해 매수
            else:
                tr_id = "VTTS1005U" if is_mock else "TTTS1005U"  # 상해 매도
        elif ovrs_excg_cd == "SEHK":
            # 홍콩 주식
            if is_buy:
                tr_id = "VTTS1002U" if is_mock else "TTTS1002U"  # 홍콩 매수
            else:
                tr_id = "VTTS1001U" if is_mock else "TTTS1001U"  # 홍콩 매도
        elif ovrs_excg_cd == "SZAA":
            # 심천 주식
            if is_buy:
                tr_id = "VTTS0305U" if is_mock else "TTTS0305U"  # 심천 매수
            else:
                tr_id = "VTTS0304U" if is_mock else "TTTS0304U"  # 심천 매도
        elif ovrs_excg_cd in ["HASE", "VNSE"]:
            # 베트남 주식
            if is_buy:
                tr_id = "VTTS0311U" if is_mock else "TTTS0311U"  # 베트남 매수
            else:
                tr_id = "VTTS0310U" if is_mock else "TTTS0310U"  # 베트남 매도
        else:
            return {
                "rt_cd": "1",
                "msg_cd": "INVALID_EXCHANGE",
                "msg1": f"지원되지 않는 거래소 코드: {ovrs_excg_cd}",
                "output": {}
            }
        
        # API 요청 URL 및 헤더 설정
        url = f"{settings.kis_base_url}/uapi/overseas-stock/v1/trading/order"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": tr_id
        }
        
        # 필수 파라미터 준비 (요청 본문에서 is_buy 제거)
        request_body = order_data.copy()
        if "is_buy" in request_body:
            del request_body["is_buy"]
        
        # 기본 값 설정
        if "ORD_SVR_DVSN_CD" not in request_body:
            request_body["ORD_SVR_DVSN_CD"] = "0"
        
        # 주문구분 설정 (기본값: 지정가)
        if "ORD_DVSN" not in request_body:
            request_body["ORD_DVSN"] = "00"  # 지정가
        
        # 디버깅 정보 출력
        logger.info(f"해외주식 주문 API 요청: {url}")
        logger.info(f"헤더: {headers}")
        logger.info(f"요청 본문: {request_body}")
        
        # API 호출
        response = requests.post(url, headers=headers, json=request_body)
        
        # 응답 확인
        logger.info(f"API 응답 상태 코드: {response.status_code}")
        logger.info(f"API 응답 본문: {response.text[:200] if response.text else '비어있음'}")
        
        # 응답 처리: 모의투자 등에서 HTTP 500과 함께 KIS 표준 JSON(rt_cd 포함)이 오는 경우가 있어 본문을 우선 해석한다.
        if response.text:
            try:
                result = response.json()
                if isinstance(result, dict) and "rt_cd" in result:
                    return result
            except ValueError:
                pass

        if response.status_code != 200:
            return {
                "rt_cd": "1",
                "msg_cd": f"HTTP_{response.status_code}",
                "msg1": f"API 호출 실패: HTTP {response.status_code}",
                "output": {},
            }

        if not response.text:
            return {
                "rt_cd": "1",
                "msg_cd": "EMPTY",
                "msg1": "응답 본문이 비어 있습니다.",
                "output": {},
            }

        try:
            result = response.json()
            # 주문 내역을 DB에 저장 (옵션)
            # save_order_history(request_body, result)
            return result
        except ValueError:
            return {
                "rt_cd": "1",
                "msg_cd": "PARSEERR",
                "msg1": "응답 파싱 오류",
                "output": {},
            }
    except Exception as e:
        logger.exception("해외주식 주문 실패: %s", e)
        return {
            "rt_cd": "1", 
            "msg_cd": "ERROR",
            "msg1": f"API 호출 오류: {str(e)}",
            "output": {}
        }

def create_conditional_orders(params):
    """
    특정 가격에 도달했을 때 자동으로 실행되는 조건부 주문 설정
    손절매(stop loss)와 이익실현(take profit) 주문을 동시에 설정
    """
    try:
        # 1. 해외주식 잔고 조회
        balance_result = get_overseas_balance()
        
        if balance_result.get("rt_cd") != "0":
            return {
                "rt_cd": "1",
                "msg_cd": "BALANCE_ERROR",
                "msg1": f"잔고 조회 실패: {balance_result.get('msg1', '알 수 없는 오류')}",
                "output": {}
            }
        
        # 2. 종목 정보 찾기
        pdno = params.get("pdno")
        ovrs_excg_cd = params.get("ovrs_excg_cd")
        
        holdings = balance_result.get("output1", [])
        target_holding = None
        
        for holding in holdings:
            if holding.get("ovrs_pdno") == pdno:
                target_holding = holding
                break
        
        if not target_holding:
            return {
                "rt_cd": "1",
                "msg_cd": "NO_HOLDING",
                "msg1": f"해당 종목({pdno})을 보유하고 있지 않습니다.",
                "output": {}
            }
        
        # 3. 기준 가격, 손절매 가격, 이익실현 가격 계산
        base_price = params.get("base_price")
        if not base_price:
            # 매수 평균단가를 기준 가격으로 사용
            base_price = float(target_holding.get("pchs_avg_pric", "0"))
            
        if base_price <= 0:
            return {
                "rt_cd": "1",
                "msg_cd": "INVALID_PRICE",
                "msg1": "유효하지 않은 기준 가격입니다.",
                "output": {}
            }
        
        # 손절매, Profit Taking 퍼센트 설정
        stop_loss_percent = params.get("stop_loss_percent", -5.0)
        take_profit_percent = params.get("take_profit_percent", 5.0)
        
        # 가격 계산
        stop_loss_price = round(base_price * (1 + stop_loss_percent/100), 2)
        take_profit_price = round(base_price * (1 + take_profit_percent/100), 2)
        
        # 주문 수량 설정 (params에 quantity가 없으면 전체 보유 수량 사용)
        quantity = params.get("quantity", target_holding.get("ord_psbl_qty", "0"))
        
        # 4. 손절매 및 이익실현 주문 생성
        order_results = []
        
        # 손절매 주문 생성 (마이너스이면 실행)
        if stop_loss_percent < 0:
            stop_loss_order = {
                "CANO": settings.KIS_CANO,
                "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
                "PDNO": pdno,
                "OVRS_EXCG_CD": ovrs_excg_cd,
                "FT_ORD_QTY": quantity,
                "FT_ORD_UNPR3": str(stop_loss_price),
                "is_buy": False,  # 매도
                "ORD_DVSN": "00"  # 지정가
            }
            
            stop_loss_result = overseas_order_resv(stop_loss_order)
            stop_loss_result["order_type"] = "stop_loss"
            order_results.append(stop_loss_result)
        
        # 이익실현 주문 생성 (플러스이면 실행)
        if take_profit_percent > 0:
            take_profit_order = {
                "CANO": settings.KIS_CANO,
                "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
                "PDNO": pdno,
                "OVRS_EXCG_CD": ovrs_excg_cd,
                "FT_ORD_QTY": quantity,
                "FT_ORD_UNPR3": str(take_profit_price),
                "is_buy": False,  # 매도
                "ORD_DVSN": "00"  # 지정가
            }
            
            take_profit_result = overseas_order_resv(take_profit_order)
            take_profit_result["order_type"] = "take_profit"
            order_results.append(take_profit_result)
        
        # 5. 결과 반환
        success_count = sum(1 for r in order_results if r.get("rt_cd") == "0")
        
        return {
            "rt_cd": "0" if success_count > 0 else "1",
            "msg_cd": "SUCCESS" if success_count == len(order_results) else "PARTIAL_SUCCESS" if success_count > 0 else "FAILED",
            "msg1": f"{success_count}/{len(order_results)} 주문이 성공적으로 처리되었습니다.",
            "base_price": base_price,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "order_results": order_results
        }
        
    except Exception as e:
        logger.exception("조건부 주문 생성 실패: %s", e)
        return {
            "rt_cd": "1",
            "msg_cd": "ERROR",
            "msg1": f"조건부 주문 생성 중 오류 발생: {str(e)}",
            "output": {}
        }
    