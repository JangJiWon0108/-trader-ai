"""
총자산/총수익률 스냅샷 저장/조회.

- 데이터 소스: Supabase `holdings`(raw) + `holdings_summary.cash_usd`
- 스냅샷 목적: 프론트 대시보드 "그래프 보기"용 시계열(정규장 1시간 간격)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

import pytz

from app.db.supabase import supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)


NY = pytz.timezone("America/New_York")


@dataclass(frozen=True)
class EquityMetrics:
    ts_utc: datetime
    ts_ny: datetime
    ny_trading_date: str  # YYYY-MM-DD
    stock_value_usd: float
    cash_usd: float
    total_assets_usd: float
    total_cost_usd: float
    total_pnl_usd: float
    total_return_pct: float


def _f(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        return float(str(x).strip() or "0")
    except Exception:
        return 0.0


def _line_cost_usd(h: dict) -> float:
    # KIS `frcr_buy_amt_smtl1`이 비는 케이스가 있어 fallback 제공
    from_api = _f(h.get("frcr_buy_amt_smtl1"))
    if from_api > 0:
        return from_api
    qty = _f(h.get("ovrs_cblc_qty"))
    avg = _f(h.get("pchs_avg_pric"))
    return max(0.0, qty * avg)


def _line_eval_usd(h: dict) -> float:
    qty = _f(h.get("ovrs_cblc_qty"))
    price = _f(h.get("now_pric2"))
    return max(0.0, qty * price)


def _line_pnl_usd(h: dict) -> float:
    kis = _f(h.get("frcr_evlu_pfls_amt"))
    if kis != 0.0:
        return kis
    return _line_eval_usd(h) - _line_cost_usd(h)


def compute_equity_metrics_from_db(*, now: datetime | None = None) -> EquityMetrics:
    """
    DB 스냅샷 기준으로 총자산/총수익률(%) 계산.

    NOTE:
    - "총수익률" 정의는 현재 프론트 대시보드와 동일하게 유지한다:
      (평가손익 합 / 매입원가 합) * 100
    """
    ts_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ts_ny = ts_utc.astimezone(NY)
    ny_trading_date = ts_ny.strftime("%Y-%m-%d")

    h_resp = supabase.table("holdings").select("raw").execute()
    rows = [r.get("raw") for r in (h_resp.data or []) if isinstance(r, dict) and isinstance(r.get("raw"), dict)]

    s_resp = supabase.table("holdings_summary").select("cash_usd").eq("id", "main").limit(1).execute()
    cash_usd = 0.0
    try:
        cash_usd = float(((s_resp.data or [{}])[0].get("cash_usd") or 0) or 0)
    except Exception:
        cash_usd = 0.0

    total_cost = 0.0
    total_eval = 0.0
    total_pnl = 0.0
    for h in rows:
        total_cost += _line_cost_usd(h)
        total_eval += _line_eval_usd(h)
        total_pnl += _line_pnl_usd(h)

    total_assets = float(total_eval + (cash_usd if cash_usd > 0 else 0.0))
    total_return_pct = (total_pnl / total_cost) * 100.0 if total_cost > 0 else 0.0

    return EquityMetrics(
        ts_utc=ts_utc,
        ts_ny=ts_ny,
        ny_trading_date=ny_trading_date,
        stock_value_usd=float(total_eval),
        cash_usd=float(cash_usd),
        total_assets_usd=float(total_assets),
        total_cost_usd=float(total_cost),
        total_pnl_usd=float(total_pnl),
        total_return_pct=float(total_return_pct),
    )


def is_due_hourly_market_snapshot(*, now: datetime | None = None) -> bool:
    """
    미국 정규장(ET)에서 1시간 간격 스냅샷(10:00, 11:00, ..., 16:00)만 True.

    - 의도: 장 시작 직후(09:30) 데이터 불안정 구간을 피하고, "정각" 샘플링으로 단순화.
    - (참고) KST 기준:
      - 서머타임: 23:00 ~ 05:00
      - 미적용: 00:00 ~ 06:00
    """
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).astimezone(NY)
    wd = ts.weekday()
    if wd > 4:
        return False
    open_dt = ts.replace(hour=9, minute=30, second=0, microsecond=0)
    close_dt = ts.replace(hour=16, minute=0, second=0, microsecond=0)
    if not (open_dt <= ts <= close_dt):
        return False
    if ts.minute != 0:
        return False
    if not (10 <= ts.hour <= 16):
        return False
    return True


def snapshot_key_for_now(*, now: datetime | None = None) -> str:
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).astimezone(NY)
    return f"{ts.strftime('%Y-%m-%d')}-{ts.strftime('%H%M')}"


def save_equity_snapshot_if_due(*, now: datetime | None = None, force: bool = False) -> dict:
    """
    due 시점이면 스냅샷 저장(best-effort). 실패해도 예외를 던지지 않음.
    """
    try:
        if not force and not is_due_hourly_market_snapshot(now=now):
            return {"attempted": False, "saved": False, "reason": "not_due"}

        m = compute_equity_metrics_from_db(now=now)
        payload = {
            "snapshot_key": snapshot_key_for_now(now=m.ts_utc),
            "ts_utc": m.ts_utc.isoformat(),
            "ts_ny": m.ts_ny.isoformat(),
            "ny_trading_date": m.ny_trading_date,
            "stock_value_usd": m.stock_value_usd,
            "cash_usd": m.cash_usd,
            "total_assets_usd": m.total_assets_usd,
            "total_cost_usd": m.total_cost_usd,
            "total_pnl_usd": m.total_pnl_usd,
            "total_return_pct": m.total_return_pct,
            "source": "scheduler",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 테이블/unique 제약은 환경마다 다를 수 있어 insert로 best-effort.
        supabase.table("equity_snapshots").insert(payload).execute()
        return {"attempted": True, "saved": True, "snapshot_key": payload["snapshot_key"], "metrics": payload}
    except Exception as e:
        logger.warning("equity_snapshot 저장 실패(무시): %s", e, exc_info=True)
        return {"attempted": True, "saved": False, "error": str(e)}


def list_equity_snapshots(*, days: int = 7) -> list[dict]:
    """
    최근 N일 스냅샷 조회 (ts_utc desc).
    """
    days = int(max(1, min(90, days)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        resp = (
            supabase.table("equity_snapshots")
            .select("*")
            .gte("ts_utc", cutoff.isoformat())
            .order("ts_utc", desc=False)
            .execute()
        )
        return list(resp.data or [])
    except Exception as e:
        logger.warning("equity_snapshots 조회 실패: %s", e, exc_info=True)
        return []

