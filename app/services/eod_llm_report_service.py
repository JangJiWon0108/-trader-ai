"""
일일 마감 LLM 리포트 (Gemini → 텔레그램).

- 5분 폴링 없음: `SCHEDULE_EOD_LLM_REPORT_TIME_KST` 에 **하루 1회**만 실행 (전역 schedule, KST).
- 입력: Supabase `scheduler_minute_logs` 중 **의미 있는** auto_sell 분 로그 + 잔고·분석·경제 스냅샷.
- 중복 방지: `.cache/eod_llm_report_last_ny_date.txt` 에 집계 기준 뉴욕 거래일 저장.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytz

from app.core.config import settings

log = logging.getLogger("eod_llm_report")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = _REPO_ROOT / ".cache"
_STATE_FILE = _STATE_DIR / "eod_llm_report_last_ny_date.txt"


def _read_last_sent_ny_date() -> str | None:
    try:
        s = _STATE_FILE.read_text(encoding="utf-8").strip()
        return s or None
    except FileNotFoundError:
        return None


def _write_last_sent_ny_date(ny_date: str) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(ny_date.strip(), encoding="utf-8")


def last_completed_ny_trading_date() -> str:
    """현재 뉴욕 시각 기준, 가장 최근 평일 날짜(YYYY-MM-DD). 주말이면 금요일까지 되돌림."""
    ny = pytz.timezone("America/New_York")
    d: date = datetime.now(ny).date()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def is_interesting_minute_log(row: dict) -> bool:
    """
    LLM에 넣을 가치가 있는 분 로그인지.

    제외: 장외 스킵, 락 스킵, 장중이지만 매도 후보 0건으로 조용히 끝난 분(no_sell_candidates & count 0).
    """
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    st = row.get("status") or payload.get("status")
    if st in ("skipped_not_market_hours", "skipped_lock"):
        return False
    cc = row.get("candidate_count")
    if cc is None:
        cc = payload.get("candidate_count")
    try:
        cc_int = int(cc) if cc is not None else 0
    except (TypeError, ValueError):
        cc_int = 0
    if st == "no_sell_candidates" and cc_int == 0:
        return False
    return True


def fetch_auto_sell_minute_logs_for_ny_date(ny_trading_date: str) -> list[dict]:
    """해당 뉴욕 거래일의 auto_sell 분 로그 전부(상한)."""
    try:
        from app.db.supabase import supabase

        resp = (
            supabase.table("scheduler_minute_logs")
            .select("id,kst_at,ny_et_at,ny_trading_date,market_hours,status,success,candidate_count,payload")
            .eq("job_type", "auto_sell")
            .eq("ny_trading_date", ny_trading_date)
            .order("kst_at", desc=False)
            .limit(2500)
            .execute()
        )
        return list(resp.data or [])
    except Exception as e:
        log.warning("scheduler_minute_logs 조회 실패: %s", e, exc_info=True)
        return []


def gather_eod_llm_context(target_ny_date: str) -> dict:
    """일일 리포트용 통합 컨텍스트 (분 로그 필터 + 기존 스냅샷)."""
    raw_rows = fetch_auto_sell_minute_logs_for_ny_date(target_ny_date)
    interesting = [r for r in raw_rows if is_interesting_minute_log(r)]
    # 토큰 과다 방지: 최대 400행
    interesting = interesting[:400]

    ctx: dict[str, Any] = {
        "report_target_ny_date": target_ny_date,
        "minute_logs": {
            "total_rows": len(raw_rows),
            "interesting_rows": len(interesting),
            "interesting": interesting,
        },
        "kis_use_mock": settings.KIS_USE_MOCK,
        "predict_model_dir": str(settings.predict_model_path),
    }

    try:
        from app.services.balance_service import get_all_overseas_balances

        bal = get_all_overseas_balances()
        ctx["balance"] = {
            "rt_cd": bal.get("rt_cd"),
            "msg1": bal.get("msg1"),
            "holdings_count": len(bal.get("output1") or []),
            "holdings_sample": (bal.get("output1") or [])[:30],
        }
    except Exception as e:
        ctx["balance_error"] = str(e)

    try:
        from app.db.supabase import supabase

        try:
            sa = (
                supabase.table("stock_analysis_results")
                .select("*")
                .order("id", desc=True)
                .limit(45)
                .execute()
            )
        except Exception:
            sa = supabase.table("stock_analysis_results").select("*").limit(45).execute()
        ctx["stock_analysis_recent"] = sa.data or []
    except Exception as e:
        ctx["stock_analysis_error"] = str(e)

    try:
        from app.db.supabase import supabase

        ec = (
            supabase.table("economic_and_stock_data")
            .select("*")
            .order("날짜", desc=True)
            .limit(2)
            .execute()
        )
        ctx["economic_latest_rows"] = ec.data or []
    except Exception as e:
        ctx["economic_error"] = str(e)

    return ctx


def _build_prompt(target_ny_date: str, ctx: dict) -> str:
    raw = json.dumps(ctx, ensure_ascii=False, default=str)
    max_json = 120_000
    if len(raw) > max_json:
        raw = raw[:max_json] + "\n... (truncated for model input)"

    return f"""역할: 한국어 주식·자동매매 **일일 마감 리포트** 작성자.
집계 기준 뉴욕 거래일: {target_ny_date}

데이터 설명:
- minute_logs.interesting: 해당일 Supabase에 쌓인 **1분 매도 점검** 중, 장외/락 스킵·빈 장중 분을 제외한 **이벤트가 있었던 분**만 담았습니다.
- minute_logs.total_rows: 같은 날짜의 전체 분 로그 개수(참고).
- balance / stock_analysis_recent / economic_latest_rows: 리포트 시점 스냅샷.

요구사항:
- 제목 한 줄 + 본문. 당일 자동 매도 점검에서 무엇이 있었는지(시도·성공·실패·API 이슈 등) 요약
- interesting 가 비어 있으면 "해당일 유의미한 분 이벤트 없음"을 명시하고, 스냅샷만으로 짧게 마무리
- 특정 종목 매매를 단정적으로 권하지 말 것. 마지막에 투자 판단은 본인 책임 한 줄
- 2800자 내외

JSON:
{raw}
"""


def run_eod_llm_report_daily() -> None:
    """
    스케줄러에서 **하루 1회** 호출 (KST 시각은 `SCHEDULE_EOD_LLM_REPORT_TIME_KST`).

    집계일 = `last_completed_ny_trading_date()` (주말이면 금요일 등).
    """
    if not getattr(settings, "SCHEDULE_EOD_LLM_REPORT_ENABLED", True):
        return

    target_ny_date = last_completed_ny_trading_date()
    if _read_last_sent_ny_date() == target_ny_date:
        return

    from alarm.notify import notify_telegram_daily_eod_report, notify_telegram_eod_report_generation_failed
    from app.services.daily_log_service import save_daily_eod_llm_log
    from llm import GeminiApiError, get_llm_answer

    try:
        log.info("EOD LLM 리포트 생성 시작 (집계 NY date=%s)", target_ny_date)
        ctx = gather_eod_llm_context(target_ny_date)
        prompt = _build_prompt(target_ny_date, ctx)
        report = get_llm_answer(prompt)
        tg_sent = notify_telegram_daily_eod_report(report, ny_date=target_ny_date)
        if tg_sent:
            _write_last_sent_ny_date(target_ny_date)
            log.info("EOD LLM 리포트 전송 완료 (NY date=%s)", target_ny_date)
            save_daily_eod_llm_log(target_ny_date, status="sent", report_text=report, telegram_sent=True)
        else:
            log.warning("EOD LLM 텔레그램 전송 실패 — 상태 파일 미갱신")
            save_daily_eod_llm_log(target_ny_date, status="telegram_failed", report_text=report, telegram_sent=False)
    except GeminiApiError as e:
        log.error("EOD LLM Gemini 오류: %s", e, exc_info=True)
        notify_telegram_eod_report_generation_failed(e, ny_date=target_ny_date, phase="gemini")
        save_daily_eod_llm_log(target_ny_date, status="gemini_error", error=str(e), phase="gemini", telegram_sent=False)
    except Exception as e:
        log.error("EOD LLM 리포트 실패: %s", e, exc_info=True)
        notify_telegram_eod_report_generation_failed(e, ny_date=target_ny_date, phase="general")
        save_daily_eod_llm_log(target_ny_date, status="general_error", error=str(e), phase="general", telegram_sent=False)
