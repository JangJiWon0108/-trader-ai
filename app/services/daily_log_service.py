"""일일/단건 로그 → Supabase (daily_buy_logs, daily_economic_logs, daily_inference_logs, daily_eod_llm_logs, order_history)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytz

log = logging.getLogger(__name__)


def _now_kst_iso() -> str:
    return datetime.now(pytz.timezone("Asia/Seoul")).isoformat()


def _ny_date() -> str:
    return datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")


def _db():
    from app.db.supabase import supabase
    return supabase


# ── 매수 ──────────────────────────────────────────────────────────────────────

def save_daily_buy_log(summary: dict) -> int | None:
    summary = summary or {}
    row: dict[str, Any] = {
        "kst_at": _now_kst_iso(),
        "ny_trading_date": summary.get("ny_trading_date") or _ny_date(),
        "success": summary.get("success"),
        "status": str(summary.get("status") or "unknown"),
        "candidate_count": summary.get("candidate_count"),
        "ordered_count": summary.get("ordered_count"),
        "payload": summary,
        "telegram_sent": summary.get("telegram_sent"),
    }
    try:
        ins = _db().table("daily_buy_logs").insert(row).execute()
        rows = ins.data or []
        if not rows:
            return None
        run_id = int(rows[0]["id"])

        items = summary.get("items") or []
        if items:
            bulk = [
                {
                    "run_id": run_id,
                    "ticker": it.get("ticker"),
                    "stock_name": it.get("stock_name"),
                    "outcome": str(it.get("outcome") or "unknown"),
                    "exchange_code": it.get("exchange_code"),
                    "quantity": it.get("quantity"),
                    "limit_price": it.get("limit_price"),
                    "error": it.get("error"),
                    "api_message": it.get("api_message"),
                }
                for it in items if isinstance(it, dict)
            ]
            if bulk:
                try:
                    _db().table("daily_buy_items").insert(bulk).execute()
                except Exception as e:
                    log.warning("daily_buy_items 저장 실패: %s", e)
        return run_id
    except Exception as e:
        log.warning("daily_buy_logs 저장 실패: %s", e, exc_info=True)
        return None


# ── 경제 데이터 ───────────────────────────────────────────────────────────────

def save_daily_economic_log(result: dict, telegram_sent: bool = False) -> None:
    result = result or {}
    row: dict[str, Any] = {
        "kst_at": _now_kst_iso(),
        "ny_trading_date": _ny_date(),
        "success": result.get("success"),
        "status": "success" if result.get("success") else "failed",
        "updated_records": result.get("updated_records"),
        "error": result.get("error"),
        "payload": result,
        "telegram_sent": telegram_sent,
    }
    try:
        _db().table("daily_economic_logs").insert(row).execute()
    except Exception as e:
        log.warning("daily_economic_logs 저장 실패: %s", e, exc_info=True)


# ── 추론 ──────────────────────────────────────────────────────────────────────

def save_daily_inference_log(result: dict, telegram_sent: bool = False) -> None:
    result = result or {}
    success = not result.get("error") and result.get("prediction_rows") is not None
    row: dict[str, Any] = {
        "kst_at": _now_kst_iso(),
        "ny_trading_date": _ny_date(),
        "success": success,
        "status": "success" if success else "failed",
        "error": result.get("error"),
        "payload": result,
        "telegram_sent": telegram_sent,
    }
    try:
        _db().table("daily_inference_logs").insert(row).execute()
    except Exception as e:
        log.warning("daily_inference_logs 저장 실패: %s", e, exc_info=True)


# ── EOD LLM ───────────────────────────────────────────────────────────────────

def save_daily_eod_llm_log(
    ny_date: str,
    status: str,
    report_text: str | None = None,
    error: str | None = None,
    phase: str | None = None,
    telegram_sent: bool = False,
) -> None:
    row: dict[str, Any] = {
        "kst_at": _now_kst_iso(),
        "ny_trading_date": ny_date,
        "success": status == "sent",
        "status": status,
        "report_text": report_text,
        "error": str(error) if error else None,
        "phase": phase,
        "telegram_sent": telegram_sent,
    }
    try:
        _db().table("daily_eod_llm_logs").insert(row).execute()
    except Exception as e:
        log.warning("daily_eod_llm_logs 저장 실패: %s", e, exc_info=True)


# ── 주문 단건 이력 ─────────────────────────────────────────────────────────────

def save_order(
    *,
    side: str,
    ticker: str,
    stock_name: str | None = None,
    exchange_code: str | None = None,
    quantity: int | None = None,
    limit_price: float | None = None,
    order_type: str | None = None,
    rt_cd: str | None = None,
    api_message: str | None = None,
    success: bool | None = None,
    source: str | None = None,
    payload: dict | None = None,
    ny_trading_date: str | None = None,
) -> None:
    row: dict[str, Any] = {
        "kst_at": _now_kst_iso(),
        "ny_trading_date": ny_trading_date or _ny_date(),
        "side": side,
        "ticker": ticker,
        "stock_name": stock_name,
        "exchange_code": exchange_code,
        "quantity": quantity,
        "limit_price": limit_price,
        "order_type": order_type,
        "rt_cd": rt_cd,
        "api_message": api_message,
        "success": success,
        "source": source,
        "payload": payload,
    }
    try:
        _db().table("order_history").insert(row).execute()
    except Exception as e:
        log.warning("order_history 저장 실패: %s", e, exc_info=True)
