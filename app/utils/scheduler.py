"""
매수·매도·경제 데이터·추론·EOD LLM 등 주기 작업 스케줄.

`schedule` + 백그라운드 스레드로 동작하며, `stock_scheduler.log` 에 로깅한다.
"""

# ─── 모듈 임포트 ───
import asyncio
import logging
import threading
import time  # noqa: F401  (일부 잡에서 사용)
import traceback
from datetime import datetime, timedelta

import pytz
import schedule

from alarm.notify import (
    notify_telegram_auto_sell_run,
    notify_telegram_economic_update,
    notify_telegram_inference_failure,
    notify_telegram_inference_success,
    notify_telegram_trading_job_exception,
)
from app.core.config import settings
from app.services.balance_service import get_all_overseas_balances, get_current_price, order_overseas_stock
from app.services.economic_service import update_economic_data_in_background
from app.services.stock_recommendation_service import StockRecommendationService

# ─── 설정 로드 (로깅) ───

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('stock_scheduler.log')
    ]
)
logger = logging.getLogger('stock_scheduler')

# schedule 모듈의 전역 job 큐는 스레드 안전하지 않다. 주식 스케줄러 스레드와 경제 스케줄러 스레드가
# 동시에 run_pending()을 호출하면 동일 잡(예: 매도)이 같은 시각에 두 번 실행될 수 있다.
_schedule_run_lock = threading.Lock()


def _persist_auto_sell_summary(summary: dict | None) -> None:
    """1분 매도 요약을 Supabase scheduler_minute_logs 에 저장 (실패해도 스케줄은 계속)."""
    if not summary:
        return
    if not settings.SCHEDULER_MINUTE_LOG_TO_SUPABASE:
        return
    try:
        from app.services.scheduler_minute_log_service import save_scheduler_minute_log

        save_scheduler_minute_log("auto_sell", summary)
    except Exception:
        logger.warning("auto_sell 분 로그 Supabase 저장 실패", exc_info=True)


def _cancel_jobs_named(job_name: str) -> None:
    """전역 schedule에서 job_func 이름이 job_name 인 잡을 모두 제거한다."""
    for job in list(schedule.jobs):
        fn = job.job_func
        if getattr(fn, "__name__", "") == job_name:
            schedule.cancel_job(job)


class StockScheduler:
    """주식 자동매매 스케줄러 클래스"""
    
    def __init__(self):
        self.recommendation_service = StockRecommendationService()
        self.running = False
        self.sell_running = False
        self.scheduler_thread = None
        self._sell_job = None
        self._sell_lock = threading.Lock()  # 동시 실행 방지
    
    def start(self):
        """매수 스케줄러 시작"""
        if self.running:
            logger.warning("매수 스케줄러가 이미 실행 중입니다.")
            return False
        
        # 한국 시간 기준 SCHEDULE_AUTO_BUY_TIME (KST, HH:MM)에 매수 작업 실행
        schedule.every().day.at(settings.SCHEDULE_AUTO_BUY_TIME).do(self._run_auto_buy)
        
        # 별도 스레드에서 스케줄러 실행
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        logger.info(
            "주식 자동매매 스케줄러가 시작되었습니다. 한국 시간 매일 %s(KST)에 매수 작업이 실행됩니다.",
            settings.SCHEDULE_AUTO_BUY_TIME,
        )
        ensure_eod_llm_report_daily_job_scheduled()
        return True
    
    def stop(self):
        """매수 스케줄러 중지"""
        if not self.running:
            logger.warning("매수 스케줄러가 실행 중이 아닙니다.")
            return False
        
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        # 매수 관련 작업 취소 (sell 스케줄러는 유지)
        buy_jobs = [job for job in schedule.jobs if job.job_func.__name__ == '_run_auto_buy']
        for job in buy_jobs:
            schedule.cancel_job(job)
        
        logger.info("매수 스케줄러가 중지되었습니다.")
        return True
    
    def start_sell_scheduler(self):
        """매도 스케줄러 시작"""
        if self.sell_running:
            logger.warning("매도 스케줄러가 이미 실행 중입니다.")
            return False

        # 기존 매도 잡 전부 제거(_sell_job 유실·리로드 잔여 등으로 동일 잡이 둘 이상 남는 경우 방지)
        if self._sell_job is not None:
            schedule.cancel_job(self._sell_job)
            self._sell_job = None
        _cancel_jobs_named("_run_auto_sell")
        self._sell_job = schedule.every(settings.SCHEDULE_AUTO_SELL_INTERVAL_MIN).minutes.do(self._run_auto_sell)
        
        # 스케줄러 스레드가 없으면 시작
        if not self.running and not self.scheduler_thread:
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
        
        self.sell_running = True
        logger.info("매도 스케줄러가 시작되었습니다. 1분마다 매도 대상을 확인합니다.")
        ensure_eod_llm_report_daily_job_scheduled()
        return True
    
    def stop_sell_scheduler(self):
        """매도 스케줄러 중지"""
        if not self.sell_running:
            logger.warning("매도 스케줄러가 실행 중이 아닙니다.")
            return False
        
        if self._sell_job is not None:
            schedule.cancel_job(self._sell_job)
            self._sell_job = None
        _cancel_jobs_named("_run_auto_sell")

        self.sell_running = False
        
        # 매수, 매도 모두 중지된 경우 스레드 종료
        if not self.running and self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
            self.scheduler_thread = None
            
        logger.info("매도 스케줄러가 중지되었습니다.")
        return True
    
    def _run_scheduler(self):
        """스케줄러 백그라운드 실행 함수"""
        while self.running or self.sell_running:
            with _schedule_run_lock:
                schedule.run_pending()
            time.sleep(1)
    
    def _run_auto_buy(self):
        """자동 매수 실행 함수 - 스케줄링된 시간에 실행됨"""
        try:
            logger.info("자동 매수 작업 시작")
            summary = self._execute_auto_buy()
            logger.info("자동 매수 작업 완료")
            try:
                from app.services.daily_log_service import save_daily_buy_log
                save_daily_buy_log(summary)
            except Exception as de:
                logger.warning("매수 로그 DB 저장 실패: %s", de)
            return True
        except Exception as e:
            logger.error(f"자동 매수 작업 중 오류 발생: {str(e)}", exc_info=True)
            notify_telegram_trading_job_exception("자동 매수", e)
            return False

    def _run_auto_sell(self):
        """자동 매도 실행 함수 - 1분마다 실행됨"""
        if not self._sell_lock.acquire(blocking=False):
            logger.warning("매도 작업이 이미 실행 중입니다. 건너뜁니다.")
            kst = datetime.now(pytz.timezone("Asia/Seoul"))
            ny = datetime.now(pytz.timezone("America/New_York"))
            lock_summary = {
                "job": "auto_sell",
                "status": "skipped_lock",
                "success": True,
                "message": "이전 매도 실행이 아직 끝나지 않아 이번 분은 건너뜀",
                "kst": kst.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "ny_et": ny.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "ny_trading_date": ny.strftime("%Y-%m-%d"),
                "market_hours": None,
                "candidate_count": 0,
                "items": [],
            }
            notify_telegram_auto_sell_run(lock_summary)
            _persist_auto_sell_summary(lock_summary)
            return False
        try:
            logger.info("자동 매도 작업 시작")
            summary = self._execute_auto_sell()
            logger.info("자동 매도 작업 완료")
            # 미국 정규장(뉴욕 평일 9:30~16:00 ET)일 때만 텔레그램 — 장외는 DB만 저장
            if summary.get("market_hours") is True:
                try:
                    summary["telegram_sent"] = notify_telegram_auto_sell_run(summary)
                except Exception as te:
                    summary["telegram_sent"] = False
                    logger.error(
                        "자동 매도 텔레그램 전송 중 예외: %s", te, exc_info=True
                    )
            _persist_auto_sell_summary(summary)
            return True
        except Exception as e:
            logger.error(f"자동 매도 작업 중 오류 발생: {str(e)}", exc_info=True)
            notify_telegram_trading_job_exception("자동 매도", e)
            ny = datetime.now(pytz.timezone("America/New_York"))
            kst = datetime.now(pytz.timezone("Asia/Seoul"))
            _persist_auto_sell_summary(
                {
                    "job": "auto_sell",
                    "status": "worker_exception",
                    "success": False,
                    "error": str(e),
                    "kst": kst.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "ny_et": ny.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "ny_trading_date": ny.strftime("%Y-%m-%d"),
                    "market_hours": None,
                    "candidate_count": 0,
                    "items": [],
                }
            )
            return False
        finally:
            self._sell_lock.release()

    def _execute_auto_sell(self) -> dict:
        """자동 매도 실행 로직. 매 실행 요약 dict 반환 (텔레그램용)."""
        now_in_korea = datetime.now(pytz.timezone("Asia/Seoul"))
        now_in_ny = datetime.now(pytz.timezone("America/New_York"))
        ny_hour = now_in_ny.hour
        ny_minute = now_in_ny.minute
        ny_weekday = now_in_ny.weekday()  # 0=월요일, 6=일요일

        is_weekday = 0 <= ny_weekday <= 4
        is_market_open_time = (
            (ny_hour == 9 and ny_minute >= 30)
            or (10 <= ny_hour < 16)
            or (ny_hour == 16 and ny_minute == 0)
        )
        is_market_hours = is_weekday and is_market_open_time

        summary: dict = {
            "job": "auto_sell",
            "ny_trading_date": now_in_ny.strftime("%Y-%m-%d"),
            "kst": now_in_korea.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "ny_et": now_in_ny.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "market_hours": is_market_hours,
            "items": [],
        }

        if not is_market_hours:
            logger.info(
                f"현재 시간 {now_in_korea.strftime('%Y-%m-%d %H:%M:%S')} (뉴욕: {now_in_ny.strftime('%Y-%m-%d %H:%M:%S')})은 미국 장 시간이 아닙니다. 매도 작업을 건너뜁니다."
            )
            summary["status"] = "skipped_not_market_hours"
            summary["success"] = True
            summary["candidate_count"] = 0
            return summary

        logger.info(
            f"미국 장 시간 확인: {now_in_korea.strftime('%Y-%m-%d %H:%M:%S')} (뉴욕: {now_in_ny.strftime('%Y-%m-%d %H:%M:%S')})"
        )

        sell_candidates_result = self.recommendation_service.get_stocks_to_sell()

        if not sell_candidates_result or not sell_candidates_result.get("sell_candidates"):
            logger.info("매도 대상 종목이 없습니다.")
            summary["status"] = "no_sell_candidates"
            summary["success"] = True
            summary["candidate_count"] = 0
            return summary

        sell_candidates = sell_candidates_result.get("sell_candidates", [])
        summary["candidate_count"] = len(sell_candidates)
        logger.info(f"매도 대상 종목 {len(sell_candidates)}개를 찾았습니다.")

        for candidate in sell_candidates:
            try:
                ticker = candidate["ticker"]
                stock_name = candidate["stock_name"]
                exchange_code = candidate["exchange_code"]
                quantity = candidate["quantity"]

                sell_reasons = candidate.get("sell_reasons", [])
                reasons_str = "; ".join(sell_reasons)
                logger.info(f"{stock_name}({ticker}) 매도 근거: {reasons_str}")

                api_exchange_code = exchange_code
                if exchange_code == "NASD":
                    api_exchange_code = "NAS"
                elif exchange_code == "NYSE":
                    api_exchange_code = "NYS"

                price_params = {
                    "AUTH": "",
                    "EXCD": api_exchange_code,
                    "SYMB": ticker,
                }

                logger.info(
                    f"{stock_name}({ticker}) 현재가 조회 요청. 거래소: {api_exchange_code}, 심볼: {ticker}"
                )
                price_result = get_current_price(price_params)

                if price_result.get("rt_cd") != "0":
                    msg1 = price_result.get("msg1", "알 수 없는 오류")
                    logger.error(f"{stock_name}({ticker}) 현재가 조회 실패: {msg1}")
                    summary["items"].append(
                        {
                            "ticker": ticker,
                            "stock_name": stock_name,
                            "outcome": "price_fetch_failed",
                            "error": msg1,
                            "sell_reasons": sell_reasons,
                        }
                    )
                    if "초당" in str(msg1):
                        time.sleep(3)
                    continue

                last_price = price_result.get("output", {}).get("last", "")
                try:
                    if not last_price or last_price == "":
                        logger.error(
                            f"{stock_name}({ticker}) 현재가가 비어있습니다. 다음 API 호출에서 다시 시도합니다."
                        )
                        summary["items"].append(
                            {
                                "ticker": ticker,
                                "stock_name": stock_name,
                                "outcome": "price_empty",
                                "sell_reasons": sell_reasons,
                            }
                        )
                        time.sleep(2)
                        continue

                    current_price = float(last_price)

                    if current_price <= 0:
                        logger.error(f"{stock_name}({ticker}) 현재가가 유효하지 않습니다: {current_price}")
                        summary["items"].append(
                            {
                                "ticker": ticker,
                                "stock_name": stock_name,
                                "outcome": "invalid_price",
                                "current_price": current_price,
                                "sell_reasons": sell_reasons,
                            }
                        )
                        continue
                except ValueError as ve:
                    logger.error(f"{stock_name}({ticker}) 현재가 변환 오류: {str(ve)}, 값: '{last_price}'")
                    summary["items"].append(
                        {
                            "ticker": ticker,
                            "stock_name": stock_name,
                            "outcome": "price_parse_error",
                            "error": str(ve),
                            "raw_last": str(last_price),
                            "sell_reasons": sell_reasons,
                        }
                    )
                    continue

                order_data = {
                    "CANO": settings.KIS_CANO,
                    "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
                    "OVRS_EXCG_CD": exchange_code,
                    "PDNO": ticker,
                    "ORD_DVSN": "00",
                    "ORD_QTY": str(quantity),
                    "OVRS_ORD_UNPR": str(current_price),
                    "is_buy": False,
                }

                logger.info(f"{stock_name}({ticker}) 매도 주문 실행: 수량 {quantity}주, 가격 ${current_price}")
                order_result = order_overseas_stock(order_data)
                msg1 = order_result.get("msg1", "")
                order_success = order_result.get("rt_cd") == "0"

                try:
                    from app.services.daily_log_service import save_order
                    save_order(
                        side="sell",
                        ticker=ticker,
                        stock_name=stock_name,
                        exchange_code=exchange_code,
                        quantity=quantity,
                        limit_price=current_price,
                        rt_cd=order_result.get("rt_cd"),
                        api_message=msg1,
                        success=order_success,
                        source="auto_sell",
                        payload=order_result,
                        ny_trading_date=now_in_ny.strftime("%Y-%m-%d"),
                    )
                except Exception as oe:
                    logger.warning("order_history 저장 실패: %s", oe)

                if order_success:
                    logger.info(f"{stock_name}({ticker}) 매도 주문 성공: {msg1 or '주문이 접수되었습니다.'}")
                    summary["items"].append(
                        {
                            "ticker": ticker,
                            "stock_name": stock_name,
                            "outcome": "order_success",
                            "quantity": quantity,
                            "limit_price": current_price,
                            "exchange_code": exchange_code,
                            "api_message": msg1,
                            "sell_reasons": sell_reasons,
                        }
                    )
                else:
                    logger.error(f"{stock_name}({ticker}) 매도 주문 실패: {msg1 or '알 수 없는 오류'}")
                    summary["items"].append(
                        {
                            "ticker": ticker,
                            "stock_name": stock_name,
                            "outcome": "order_failed",
                            "quantity": quantity,
                            "limit_price": current_price,
                            "exchange_code": exchange_code,
                            "error": msg1 or "알 수 없는 오류",
                            "sell_reasons": sell_reasons,
                        }
                    )

                time.sleep(2)

            except Exception as e:
                logger.error(
                    f"{candidate['stock_name']}({candidate['ticker']}) 매도 처리 중 오류: {str(e)}",
                    exc_info=True,
                )
                summary["items"].append(
                    {
                        "ticker": candidate.get("ticker"),
                        "stock_name": candidate.get("stock_name"),
                        "outcome": "candidate_exception",
                        "error": str(e),
                    }
                )
                time.sleep(1)

        logger.info("자동 매도 처리가 완료되었습니다.")
        summary["status"] = "completed"
        bad = {"order_failed", "candidate_exception"}
        summary["success"] = not any((it.get("outcome") in bad) for it in summary["items"])
        summary["had_price_or_validation_issue"] = any(
            it.get("outcome")
            in ("price_fetch_failed", "price_empty", "invalid_price", "price_parse_error")
            for it in summary["items"]
        )
        return summary
    
    def _execute_auto_buy(self) -> dict:
        """자동 매수 실행 로직. 실행 요약 dict 반환."""
        now_kst = datetime.now(pytz.timezone("Asia/Seoul"))
        now_ny = datetime.now(pytz.timezone("America/New_York"))
        summary: dict = {
            "job": "auto_buy",
            "ny_trading_date": now_ny.strftime("%Y-%m-%d"),
            "kst": now_kst.isoformat(),
            "candidate_count": 0,
            "ordered_count": 0,
            "items": [],
            "status": "completed",
            "success": True,
            "telegram_sent": False,
        }

        try:
            balance_result = get_all_overseas_balances()
            if balance_result.get("rt_cd") != "0":
                logger.error(f"보유 종목 조회 실패: {balance_result.get('msg1', '알 수 없는 오류')}")
                summary["status"] = "balance_error"
                summary["success"] = False
                return summary

            holdings = balance_result.get("output1", [])
            holding_tickers = {item.get("ovrs_pdno") for item in holdings if item.get("ovrs_pdno")}
            logger.info(f"현재 보유 중인 종목 수: {len(holding_tickers)}")
        except Exception as e:
            logger.error(f"보유 종목 조회 중 오류 발생: {str(e)}", exc_info=True)
            summary["status"] = "balance_exception"
            summary["success"] = False
            return summary

        recommendations = self.recommendation_service.get_combined_recommendations_with_technical_and_sentiment()

        if not recommendations or not recommendations.get("results"):
            logger.info("매수 대상 종목이 없습니다.")
            summary["status"] = "no_candidates"
            return summary

        buy_candidates = recommendations.get("results", [])
        summary["candidate_count"] = len(buy_candidates)
        logger.info(f"매수 대상 종목 {len(buy_candidates)}개를 찾았습니다.")

        from app.services.daily_log_service import save_order

        for candidate in buy_candidates:
            try:
                ticker = candidate["ticker"]
                stock_name = candidate["stock_name"]

                if ticker.endswith(".X") or ticker.endswith(".N"):
                    exchange_code = "NYSE" if ticker.endswith(".N") else "NASD"
                    pure_ticker = ticker.split(".")[0]
                else:
                    exchange_code = "NASD"
                    pure_ticker = ticker

                if pure_ticker in holding_tickers:
                    logger.info(f"{stock_name}({ticker}) - 이미 보유 중인 종목이므로 매수하지 않습니다.")
                    summary["items"].append({"ticker": pure_ticker, "stock_name": stock_name, "outcome": "already_holding"})
                    continue

                api_exchange_code = "NYS" if exchange_code == "NYSE" else "NAS"
                price_result = get_current_price({"AUTH": "", "EXCD": api_exchange_code, "SYMB": pure_ticker})

                if price_result.get("rt_cd") != "0":
                    msg1 = price_result.get("msg1", "알 수 없는 오류")
                    logger.error(f"{stock_name}({ticker}) 현재가 조회 실패: {msg1}")
                    summary["items"].append({"ticker": pure_ticker, "stock_name": stock_name, "outcome": "price_fetch_failed", "error": msg1})
                    continue

                current_price = float(price_result.get("output", {}).get("last", 0))
                if current_price <= 0:
                    logger.error(f"{stock_name}({ticker}) 현재가가 유효하지 않습니다: {current_price}")
                    summary["items"].append({"ticker": pure_ticker, "stock_name": stock_name, "outcome": "invalid_price"})
                    continue

                quantity = settings.TRADING_BUY_QUANTITY
                order_data = {
                    "CANO": settings.KIS_CANO,
                    "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
                    "OVRS_EXCG_CD": exchange_code,
                    "PDNO": pure_ticker,
                    "ORD_DVSN": settings.TRADING_ORDER_TYPE,
                    "ORD_QTY": str(quantity),
                    "OVRS_ORD_UNPR": str(current_price),
                    "is_buy": True,
                }

                logger.info(f"{stock_name}({ticker}) 매수 주문 실행: 수량 {quantity}주, 가격 ${current_price}")
                order_result = order_overseas_stock(order_data)
                msg1 = order_result.get("msg1", "")
                order_success = order_result.get("rt_cd") == "0"

                save_order(
                    side="buy",
                    ticker=pure_ticker,
                    stock_name=stock_name,
                    exchange_code=exchange_code,
                    quantity=quantity,
                    limit_price=current_price,
                    order_type=settings.TRADING_ORDER_TYPE,
                    rt_cd=order_result.get("rt_cd"),
                    api_message=msg1,
                    success=order_success,
                    source="auto_buy",
                    payload=order_result,
                    ny_trading_date=now_ny.strftime("%Y-%m-%d"),
                )

                if order_success:
                    logger.info(f"{stock_name}({ticker}) 매수 주문 성공: {msg1 or '주문이 접수되었습니다.'}")
                    summary["items"].append({"ticker": pure_ticker, "stock_name": stock_name, "outcome": "order_success", "quantity": quantity, "limit_price": current_price, "exchange_code": exchange_code, "api_message": msg1})
                    summary["ordered_count"] = summary.get("ordered_count", 0) + 1
                else:
                    logger.error(f"{stock_name}({ticker}) 매수 주문 실패: {msg1 or '알 수 없는 오류'}")
                    summary["items"].append({"ticker": pure_ticker, "stock_name": stock_name, "outcome": "order_failed", "error": msg1, "exchange_code": exchange_code})
                    summary["success"] = False

                time.sleep(1)

            except Exception as e:
                logger.error(f"{candidate['stock_name']}({candidate['ticker']}) 매수 처리 중 오류: {str(e)}", exc_info=True)
                summary["items"].append({"ticker": candidate.get("ticker"), "stock_name": candidate.get("stock_name"), "outcome": "candidate_exception", "error": str(e)})
                summary["success"] = False

        logger.info("자동 매수 처리가 완료되었습니다.")
        return summary

# 싱글톤 인스턴스 생성
stock_scheduler = StockScheduler()

_eod_llm_report_daily_registered = False


def _run_eod_llm_report_daily() -> None:
    from app.services.eod_llm_report_service import run_eod_llm_report_daily

    run_eod_llm_report_daily()


def ensure_eod_llm_report_daily_job_scheduled() -> None:
    """전역 schedule 에 EOD LLM 일일 리포트 잡을 한 번만 등록한다 (매일 KST 1회)."""
    global _eod_llm_report_daily_registered
    if _eod_llm_report_daily_registered:
        return
    hhmm = (settings.SCHEDULE_EOD_LLM_REPORT_TIME_KST or "07:00").strip()
    schedule.every().day.at(hhmm).do(_run_eod_llm_report_daily)
    _eod_llm_report_daily_registered = True
    logger.info("EOD LLM 일일 리포트 잡 등록 (매일 KST %s, Supabase 분 로그 필터 → Gemini)", hhmm)


def start_scheduler():
    """매수 스케줄러 시작 함수"""
    return stock_scheduler.start()

def stop_scheduler():
    """매수 스케줄러 중지 함수"""
    return stock_scheduler.stop()

def start_sell_scheduler():
    """매도 스케줄러 시작 함수"""
    return stock_scheduler.start_sell_scheduler()

def stop_sell_scheduler():
    """매도 스케줄러 중지 함수"""
    return stock_scheduler.stop_sell_scheduler()

def _next_kst_daily_run_iso(hhmm: str) -> str:
    """설정된 KST 시각의 다음 발생 시각을 ISO8601 로 반환."""
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst)
    parts = (hhmm or "00:00").strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.isoformat()


def _next_sell_check_iso() -> str | None:
    """매도 스케줄러가 장중 점검할 때까지 남은 시간 기준 다음 분(뉴욕) — 장외면 None."""
    ny = pytz.timezone("America/New_York")
    now_ny = datetime.now(ny)
    wd = now_ny.weekday()
    if wd > 4:
        return None
    hm = now_ny.hour * 60 + now_ny.minute
    open_m = 9 * 60 + 30
    close_m = 16 * 60
    if hm < open_m or hm >= close_m:
        return None
    nxt = (now_ny.replace(second=0, microsecond=0) + timedelta(minutes=1))
    if nxt.hour == 16 and nxt.minute > 0:
        return None
    return nxt.astimezone(pytz.UTC).isoformat()


def get_scheduler_status():
    """스케줄러 상태·다음 매수 시각(KST)·다음 매도 점검 시각(뉴욕 장중)"""
    buy_running = stock_scheduler.running
    sell_running = stock_scheduler.sell_running
    next_buy_at = _next_kst_daily_run_iso(settings.SCHEDULE_AUTO_BUY_TIME)
    next_sell_at = _next_sell_check_iso() if sell_running else None
    msg = (
        f"매수 스케줄러: {'실행 중' if buy_running else '중지됨'}, "
        f"매도 스케줄러: {'실행 중' if sell_running else '중지됨'}"
    )
    return {
        "buy_running": buy_running,
        "sell_running": sell_running,
        "message": msg,
        "schedule_buy_time_kst": settings.SCHEDULE_AUTO_BUY_TIME,
        "schedule_sell_interval_min": settings.SCHEDULE_AUTO_SELL_INTERVAL_MIN,
        "next_auto_buy_at": next_buy_at,
        "next_sell_check_at": next_sell_at,
    }

def run_auto_buy_now():
    """즉시 매수 실행 함수 (테스트용)"""
    stock_scheduler._run_auto_buy()
    
def run_auto_sell_now():
    """즉시 매도 실행 함수 (테스트용)"""
    stock_scheduler._run_auto_sell()

# 경제 데이터 스케줄러 관련 변수 및 함수
economic_data_scheduler_running = False
economic_data_scheduler_thread = None

def _run_economic_data_update(telegram_source: str = "경제스케줄"):
    """경제·주가 DB 갱신 후, 신규 행이 있으면 저장 모델로 추론·예측 테이블 갱신."""
    elog = logging.getLogger("economic_scheduler")
    try:
        elog.info("경제 데이터 업데이트 작업 시작")
        result = asyncio.run(update_economic_data_in_background())
        elog.info("경제 데이터 업데이트 작업 완료: %s", result)

        rdict = result if isinstance(result, dict) else {}
        econ_tg_sent = notify_telegram_economic_update(rdict, source=telegram_source)

        from app.services.daily_log_service import save_daily_economic_log, save_daily_inference_log
        save_daily_economic_log(rdict, telegram_sent=econ_tg_sent)

        updated = int((rdict).get("updated_records") or 0)
        if (
            settings.SCHEDULE_AFTER_ECONOMIC_RUN_INFERENCE
            and rdict.get("success")
            and updated > 0
        ):
            elog.info("신규 저장 행 %s건 → 모델 추론 및 predicted_stocks / stock_analysis_results 갱신", updated)
            try:
                from predict_model.predict.run_inference import run_inference_and_save_to_db

                inf = run_inference_and_save_to_db()
                elog.info("추론·DB 갱신 완료: %s", inf)
                inf_tg_sent = notify_telegram_inference_success(inf, source=f"{telegram_source}_추론")
                save_daily_inference_log(inf or {}, telegram_sent=inf_tg_sent)
            except Exception as inf_e:
                elog.error(
                    "추론·DB 갱신 실패(경제 데이터는 이미 저장됨): %s",
                    inf_e,
                    exc_info=True,
                )
                inf_tg_sent = notify_telegram_inference_failure(inf_e, source=f"{telegram_source}_추론")
                save_daily_inference_log({"error": str(inf_e)}, telegram_sent=inf_tg_sent)
        elif rdict.get("success") and updated == 0:
            elog.info("저장된 신규 행이 없어 추론을 건너뜁니다.")

        return True
    except Exception as e:
        elog.error("경제 데이터 업데이트 작업 중 오류 발생: %s", e, exc_info=True)
        econ_tg_sent = notify_telegram_economic_update(
            {"success": False, "error": str(e), "traceback": traceback.format_exc()},
            source=telegram_source,
        )
        try:
            from app.services.daily_log_service import save_daily_economic_log
            save_daily_economic_log({"success": False, "error": str(e)}, telegram_sent=econ_tg_sent)
        except Exception:
            pass
        return False

def _run_economic_scheduler():
    """경제 데이터 스케줄러 백그라운드 실행 함수"""
    global economic_data_scheduler_running
    while economic_data_scheduler_running:
        with _schedule_run_lock:
            schedule.run_pending()
        time.sleep(1)

def start_economic_data_scheduler():
    """경제 데이터 업데이트 스케줄러 시작 함수"""
    global economic_data_scheduler_running, economic_data_scheduler_thread
    
    if economic_data_scheduler_running:
        logger = logging.getLogger('economic_scheduler')
        logger.warning("경제 데이터 스케줄러가 이미 실행 중입니다.")
        return False
    
    schedule.every().day.at(settings.SCHEDULE_ECONOMIC_UPDATE_TIME).do(_run_economic_data_update)
    
    # 별도 스레드에서 스케줄러 실행
    economic_data_scheduler_running = True
    economic_data_scheduler_thread = threading.Thread(target=_run_economic_scheduler)
    economic_data_scheduler_thread.daemon = True
    economic_data_scheduler_thread.start()
    
    logger = logging.getLogger('economic_scheduler')
    logger.info(
        "경제 데이터 스케줄러 시작 (KST %s, 추론 후행: %s)",
        settings.SCHEDULE_ECONOMIC_UPDATE_TIME,
        settings.SCHEDULE_AFTER_ECONOMIC_RUN_INFERENCE,
    )
    ensure_eod_llm_report_daily_job_scheduled()
    return True

def stop_economic_data_scheduler():
    """경제 데이터 업데이트 스케줄러 중지 함수"""
    global economic_data_scheduler_running, economic_data_scheduler_thread
    
    if not economic_data_scheduler_running:
        logger = logging.getLogger('economic_scheduler')
        logger.warning("경제 데이터 스케줄러가 실행 중이 아닙니다.")
        return False
    
    # 경제 데이터 관련 작업 취소
    economic_jobs = [job for job in schedule.jobs if job.job_func.__name__ == '_run_economic_data_update']
    for job in economic_jobs:
        schedule.cancel_job(job)
    
    economic_data_scheduler_running = False
    if economic_data_scheduler_thread:
        economic_data_scheduler_thread.join(timeout=5)
        economic_data_scheduler_thread = None
    
    logger = logging.getLogger('economic_scheduler')
    logger.info("경제 데이터 업데이트 스케줄러가 중지되었습니다.")
    return True

def run_economic_data_update_now():
    """즉시 경제 데이터 업데이트 실행 함수 (테스트용)"""
    return _run_economic_data_update("즉시실행")


def run_inference_now():
    """경제 갱신 없이 즉시 추론·예측 DB만 갱신 (테스트용)"""
    from predict_model.predict.run_inference import run_inference_and_save_to_db

    return run_inference_and_save_to_db()