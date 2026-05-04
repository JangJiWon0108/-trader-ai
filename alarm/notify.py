"""스케줄·트레이딩 관련 텔레그램 알림 (본문이 길면 분할 전송)."""

from __future__ import annotations

# ─── 모듈 임포트 ───
import json
import logging
import traceback
from typing import Any

from alarm.telegram import send_telegram_long_text

logger = logging.getLogger(__name__)

# ─── 헬퍼 함수 ───


def _json_pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ─── 공개 API ───


def notify_telegram_daily_eod_report(report_text: str, *, ny_date: str) -> bool:
    """미국장 마감 일일 LLM 리포트. 전송 성공 시 True."""
    body = f"[Trader-AI] 미국장 마감 일일 리포트 (NY {ny_date})\n\n{(report_text or '').strip()}"
    return bool(send_telegram_long_text(body))


def notify_telegram_eod_report_generation_failed(
    exc: BaseException,
    *,
    ny_date: str,
    phase: str = "general",
) -> None:
    """EOD 리포트 생성/전송 실패 알림."""
    body = "\n".join(
        [
            f"[Trader-AI] EOD LLM 리포트 실패 (NY {ny_date}, phase={phase})",
            str(exc),
            traceback.format_exc(),
        ]
    )
    if not send_telegram_long_text(body):
        logger.debug("텔레그램 미설정 또는 전송 실패(EOD 실패 알림)")


def notify_telegram_auto_sell_run(summary: dict | None) -> bool:
    """자동 매도 1분 점검 한 번의 요약(장외 스킵·후보 없음·종목별 성공/실패 등)."""
    summary = summary or {}
    body = "\n".join(
        [
            "[Trader-AI] 자동 매도 1분 점검 결과",
            _json_pretty(summary),
        ]
    )
    sent = bool(send_telegram_long_text(body))
    if not sent:
        logger.warning(
            "자동 매도 텔레그램 전송 실패 또는 미설정(TELEGRAM_*). stock_scheduler.log 확인."
        )
    return sent


def notify_telegram_trading_job_exception(job_label: str, exc: BaseException) -> None:
    """자동 매수/매도 작업 전체 예외."""
    body = "\n".join(
        [
            f"[Trader-AI] {job_label} 작업 전체 예외",
            str(exc),
            traceback.format_exc(),
        ]
    )
    if not send_telegram_long_text(body):
        logger.debug("텔레그램 미설정 또는 전송 실패(%s)", job_label)


def notify_telegram_economic_update(result: dict | None, *, source: str) -> bool:
    """경제·주가 일일(또는 수동) 갱신 성공/실패."""
    result = result or {}
    if result.get("success"):
        dr = result.get("date_range") or {}
        payload = {
            "message": result.get("message"),
            "total_records": result.get("total_records"),
            "updated_records": result.get("updated_records"),
            "date_range": dr,
            "saved_rows": result.get("saved_rows") or [],
        }
        body = "\n".join(
            [
                f"[Trader-AI] 경제·주가 DB 갱신 성공 ({source})",
                _json_pretty(payload),
            ]
        )
    else:
        parts = [
            f"[Trader-AI] 경제·주가 DB 갱신 실패 ({source})",
            f"error: {result.get('error', '알 수 없음')}",
        ]
        tb = result.get("traceback")
        if tb:
            parts.extend(["", "traceback:", str(tb)])
        body = "\n".join(parts)

    sent = bool(send_telegram_long_text(body))
    if not sent:
        logger.debug("텔레그램 미설정 또는 전송 실패(경제 %s)", source)
    return sent


def notify_telegram_inference_success(inf: dict | None, *, source: str) -> bool:
    """추론·DB 갱신 성공 (analysis_records 전체)."""
    inf = inf or {}
    payload = {
        "model_dir": inf.get("model_dir"),
        "prediction_rows": inf.get("prediction_rows"),
        "analysis_rows": inf.get("analysis_rows"),
        "write_db": inf.get("write_db"),
        "analysis_records": inf.get("analysis_records") or [],
    }
    body = "\n".join(
        [
            f"[Trader-AI] 추론·DB 갱신 성공 ({source})",
            _json_pretty(payload),
        ]
    )
    sent = bool(send_telegram_long_text(body))
    if not sent:
        logger.debug("텔레그램 미설정 또는 전송 실패(추론 성공 %s)", source)
    return sent


def notify_telegram_inference_failure(exc: BaseException, *, source: str) -> bool:
    """추론·DB 갱신 실패."""
    body = "\n".join(
        [
            f"[Trader-AI] 추론·DB 갱신 실패 ({source})",
            str(exc),
            traceback.format_exc(),
        ]
    )
    sent = bool(send_telegram_long_text(body))
    if not sent:
        logger.debug("텔레그램 미설정 또는 전송 실패(추론 실패 %s)", source)
    return sent
