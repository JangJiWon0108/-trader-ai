"""
경제·주가 일일 배치: Supabase `economic_and_stock_data` 갱신.

루트 `stock.collect_economic_data` 로 구간 수집 후, 어제까지 행만 DB에 반영한다.
스케줄·앱 기동 시 `update_economic_data_in_background` 가 호출된다.
"""

# ─── 모듈 임포트 ───
import logging
import traceback
from datetime import datetime, timedelta

import pandas as pd

from app.core.config import settings
from app.db.supabase import supabase
from stock import collect_economic_data

logger = logging.getLogger(__name__)

# ─── 헬퍼 함수 ───


def get_last_updated_date():
    """
    데이터베이스에서 마지막으로 수집된 날짜를 조회합니다.
    """
    try:
        response = (
            supabase.table("economic_and_stock_data")
            .select("날짜")
            .order("날짜", desc=True)
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            last_date = datetime.fromisoformat(response.data[0]["날짜"].replace("Z", "+00:00"))
            next_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info(
                "마지막 수집 날짜: %s, 다음 수집 시작일: %s",
                last_date.strftime("%Y-%m-%d"),
                next_date,
            )
            return next_date
        logger.info("기존 데이터 없음 — 기본 시작 날짜(2006-01-01)")
        return "2006-01-01"
    except Exception as e:
        logger.warning("마지막 수집 날짜 조회 오류: %s", e, exc_info=True)
        return "2006-01-01"


def get_existing_data_with_nulls():
    """
    NULL 값이 있는 기존 데이터를 조회합니다.
    """
    try:
        query = "SELECT * FROM economic_and_stock_data WHERE jsonb_object_keys(data::jsonb) @> '{null}'::jsonb"
        response = supabase.table("economic_and_stock_data").select("*").execute(query)

        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            logger.info("NULL 값이 포함된 레코드 %s개 발견", len(df))
            return df
        logger.info("NULL 값이 포함된 레코드 없음")
        return pd.DataFrame()
    except Exception as e:
        logger.warning("NULL 값 데이터 조회 오류: %s", e, exc_info=True)
        return pd.DataFrame()


# ─── 상수 정의 ───

stock_columns = [
    "나스닥 종합지수",
    "S&P 500 지수",
    "금 가격",
    "달러 인덱스",
    "나스닥 100",
    "S&P 500 ETF",
    "QQQ ETF",
    "러셀 2000 ETF",
    "다우 존스 ETF",
    "VIX 지수",
    "닛케이 225",
    "상해종합",
    "항셍",
    "영국 FTSE",
    "독일 DAX",
    "프랑스 CAC 40",
    "미국 전체 채권시장 ETF",
    "TIPS ETF",
    "투자등급 회사채 ETF",
    "달러/엔",
    "달러/위안",
    "미국 리츠 ETF",
    "애플",
    "마이크로소프트",
    "아마존",
    "구글 A",
    "구글 C",
    "메타",
    "테슬라",
    "엔비디아",
    "코스트코",
    "넷플릭스",
    "페이팔",
    "인텔",
    "시스코",
    "컴캐스트",
    "펩시코",
    "암젠",
    "허니웰 인터내셔널",
    "스타벅스",
    "몬델리즈",
    "마이크론",
    "브로드컴",
    "어도비",
    "텍사스 인스트루먼트",
    "AMD",
    "어플라이드 머티리얼즈",
]

economic_columns = [
    "10년 기대 인플레이션율",
    "장단기 금리차",
    "기준금리",
    "미시간대 소비자 심리지수",
    "실업률",
    "2년 만기 미국 국채 수익률",
    "10년 만기 미국 국채 수익률",
    "금융스트레스지수",
    "개인 소비 지출",
    "소비자 물가지수",
    "5년 변동금리 모기지",
    "미국 달러 환율",
    "통화 공급량 M2",
    "가계 부채 비율",
    "GDP 성장률",
]

# ─── 공개 API ───


async def update_economic_data_in_background():
    """
    백그라운드에서 경제 지표 데이터를 업데이트
    """
    try:
        logger.info("경제 지표 및 주가 데이터 업데이트 작업 시작")

        start_date = get_last_updated_date()

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        collection_end_date = today
        storage_end_date = yesterday

        if start_date > storage_end_date:
            logger.info(
                "수집 시작일(%s)이 저장 종료일(%s)보다 큼 — 수집할 데이터 없음",
                start_date,
                storage_end_date,
            )
            return {
                "success": True,
                "message": "수집할 데이터 없음 (시작일이 저장 종료일보다 큼)",
                "total_records": 0,
                "updated_records": 0,
                "date_range": {
                    "start_date": start_date,
                    "storage_end_date": storage_end_date,
                    "collection_end_date": collection_end_date,
                },
                "saved_rows": [],
            }

        previous_date = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_data_response = supabase.table("economic_and_stock_data").select("*").eq("날짜", previous_date).execute()
        previous_data = prev_data_response.data[0] if prev_data_response.data else {}

        new_data = collect_economic_data(start_date=start_date, end_date=collection_end_date)

        logger.info("=== 수집된 데이터 확인 ===")
        for date_idx in new_data.index:
            date_str = date_idx.strftime("%Y-%m-%d") if isinstance(date_idx, pd.Timestamp) else date_idx
            logger.info("날짜: %s", date_str)
            for stock in stock_columns[:5]:
                if stock in new_data.columns:
                    logger.info("  %s: %s", stock, new_data.loc[date_idx, stock])

        if new_data is None or new_data.empty:
            logger.info("수집할 새 데이터 없음")
            return {
                "success": True,
                "message": "수집할 새 데이터가 없음",
                "total_records": 0,
                "updated_records": 0,
                "date_range": {
                    "start_date": start_date,
                    "storage_end_date": storage_end_date,
                    "collection_end_date": collection_end_date,
                },
                "saved_rows": [],
            }

        all_dates = pd.date_range(start=start_date, end=storage_end_date)
        saved_count = 0

        for date in all_dates:
            date_str = date.strftime("%Y-%m-%d")

            if date in new_data.index:
                row = new_data.loc[date]
                logger.info("== %s 데이터 있음 (저장 대상) ==", date_str)
                for stock in stock_columns[:5]:
                    if stock in row.index:
                        logger.info("  원본 %s: %s", stock, row[stock])
            else:
                logger.info("== %s 데이터 없음, 이전 데이터 사용 (저장 대상) ==", date_str)
                row = pd.Series(dtype="object")

            check = supabase.table("economic_and_stock_data").select("*").eq("날짜", date_str).execute()

            data_dict = {}
            for col_name, value in row.items():
                if not pd.isna(value):
                    data_dict[col_name] = value

            for col_name, value in previous_data.items():
                if col_name != "날짜" and col_name not in data_dict and value is not None:
                    data_dict[col_name] = value

            if check.data and len(check.data) > 0:
                existing_data = check.data[0]
                update_dict = {}

                for col_name, value in data_dict.items():
                    if col_name not in existing_data or existing_data[col_name] is None:
                        update_dict[col_name] = value

                if update_dict:
                    supabase.table("economic_and_stock_data").update(update_dict).eq("날짜", date_str).execute()
            else:
                insert_dict = {"날짜": date_str}
                insert_dict.update(data_dict)
                supabase.table("economic_and_stock_data").insert(insert_dict).execute()

            if data_dict:
                previous_data = {"날짜": date_str}
                previous_data.update(data_dict)

            for stock in stock_columns[:5]:
                if stock in data_dict:
                    logger.info("  저장 전 %s: %s", stock, data_dict[stock])

            saved_count += 1

        if datetime.now().date() in new_data.index:
            logger.info("== %s 데이터는 수집했지만 저장하지 않음 ==", today)

        total_records = len(all_dates)
        logger.info("총 %s개 날짜 중 %s개 처리", total_records, saved_count)

        rows_resp = (
            supabase.table("economic_and_stock_data")
            .select("*")
            .gte("날짜", start_date)
            .lte("날짜", storage_end_date)
            .order("날짜", desc=False)
            .execute()
        )
        saved_rows = list(rows_resp.data or [])

        return {
            "success": True,
            "message": "경제 데이터 업데이트 완료",
            "total_records": total_records,
            "updated_records": saved_count,
            "date_range": {
                "start_date": start_date,
                "storage_end_date": storage_end_date,
                "collection_end_date": collection_end_date,
            },
            "saved_rows": saved_rows,
        }
    except Exception as e:
        logger.exception("경제 데이터 업데이트 실패: %s", e)
        tb = traceback.format_exc()
        return {"success": False, "error": str(e), "traceback": tb}


logger.info("economic_service 로드 — Supabase URL: %s", settings.SUPABASE_URL)
