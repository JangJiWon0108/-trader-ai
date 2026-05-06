"""스케줄·트레이딩 관련 텔레그램 알림 (본문이 길면 분할 전송)."""

from __future__ import annotations

# ─── 모듈 임포트 ───
import json
import traceback
from typing import Any

from alarm.telegram import send_telegram_long_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

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


def _format_holdings_section(balance: dict | None) -> str:
    """보유 종목 + 평가손익 섹션 문자열 반환."""
    if not balance:
        return ""
    holdings = balance.get("output1") or []
    if not holdings:
        return "\n━━ 보유 종목 없음 ━━"
    lines = ["\n━━ 보유 종목 ━━"]
    total_pl = 0.0
    total_cost = 0.0
    for h in holdings:
        ticker = h.get("ovrs_pdno", "")
        name = h.get("ovrs_item_name") or ticker
        qty = h.get("ovrs_cblc_qty", "0")
        avg = h.get("pchs_avg_pric", "0")
        now_p = h.get("now_pric2", "0")
        pl_amt = float(h.get("frcr_evlu_pfls_amt") or 0)
        pl_rt = float(h.get("evlu_pfls_rt") or 0)
        try:
            total_cost += float(avg or 0) * float(qty or 0)
        except (ValueError, TypeError):
            pass
        total_pl += pl_amt
        s = "+" if pl_amt >= 0 else ""
        sr = "+" if pl_rt >= 0 else ""
        lines.append(f"  {name}({ticker}) {qty}주 | 매수${avg} → 현재${now_p} | {s}{pl_amt:.1f}$ ({sr}{pl_rt:.2f}%)")
    s = "+" if total_pl >= 0 else ""
    if total_cost > 0:
        total_pct = total_pl / total_cost * 100
        sp = "+" if total_pct >= 0 else ""
        lines.append(f"\n📊 총 평가손익: {s}{total_pl:.1f}$ ({sp}{total_pct:.2f}%)")
    else:
        lines.append(f"\n📊 총 평가손익: {s}{total_pl:.1f}$")
    return "\n".join(lines)


def notify_telegram_auto_sell_run(summary: dict | None) -> bool:
    """자동 매도 1분 점검 결과 — 잔고·후보 조건·수익률 포함."""
    summary = summary or {}
    kst = summary.get("kst", "")
    ny = summary.get("ny_et", "")
    items = summary.get("items") or []
    candidate_count = int(summary.get("candidate_count") or 0)
    balance = summary.get("balance_snapshot")

    ordered = [i for i in items if i.get("outcome") == "order_success"]
    failed_order = [i for i in items if i.get("outcome") == "order_failed"]

    lines = ["[Trader-AI] 자동 매도 점검"]
    lines.append(f"⏰ {kst}  (NY: {ny})")

    if candidate_count == 0:
        lines.append("ℹ️ 매도 후보 없음")
    else:
        lines.append(
            f"📊 후보 {candidate_count}개 | 매도성공 {len(ordered)}건 | 실패 {len(failed_order)}건"
        )

    if items:
        lines.append("\n━━ 후보 상세 ━━")
        for it in items:
            outcome = it.get("outcome", "")
            ticker = it.get("ticker", "")
            name = it.get("stock_name") or ticker
            qty = it.get("quantity", "")
            lp = it.get("limit_price")
            pp = it.get("purchase_price")
            pct = it.get("price_change_pct")
            sell_reasons = it.get("sell_reasons") or []
            tech = it.get("tech_details") or []
            sentiment = it.get("sentiment_score")

            if outcome == "order_success":
                st = f"✅ 매도완료 @${lp}"
            elif outcome == "order_failed":
                st = f"❌ 매도실패: {it.get('error', '')}"
            else:
                st = f"⚠️ {outcome}"

            price_info = ""
            if pp is not None and lp is not None:
                sign = "+" if (pct or 0) >= 0 else ""
                pct_str = f"{sign}{pct:.1f}%" if pct is not None else ""
                price_info = f" | 매수${float(pp):.2f}→현재${float(lp):.2f} ({pct_str})"

            lines.append(f"\n🔸 {name}({ticker}) {qty}주{price_info}")
            lines.append(f"   {st}")
            for r in sell_reasons:
                lines.append(f"   근거: {r}")
            if tech:
                lines.append(f"   기술지표: {', '.join(str(t) for t in tech)}")
            if sentiment is not None:
                lines.append(f"   감성: {float(sentiment):.3f}")

    holdings_text = _format_holdings_section(balance)
    if holdings_text:
        lines.append(holdings_text)

    try:
        from app.core.config import settings as _s
        lines.append(
            f"\n⚙️ 기준: 익절+{_s.SELL_TAKE_PROFIT_PCT}% | 손절{_s.SELL_STOP_LOSS_PCT}% | RSI>{_s.SELL_RSI_OVERBOUGHT} | 감성<{_s.SELL_SENTIMENT_MAX}"
        )
    except Exception:
        pass

    body = "\n".join(lines)
    sent = bool(send_telegram_long_text(body))
    if not sent:
        logger.warning("자동 매도 텔레그램 전송 실패 또는 미설정(TELEGRAM_*). stock_scheduler.log 확인.")
    return sent


def notify_telegram_auto_buy_run(summary: dict | None) -> bool:
    """자동 매수 결과 — 잔고·후보 분석·수익률 포함."""
    summary = summary or {}
    kst = summary.get("kst", "")
    items = summary.get("items") or []
    candidate_count = int(summary.get("candidate_count") or 0)
    ordered_count = int(summary.get("ordered_count") or 0)
    status = summary.get("status", "")
    balance = summary.get("balance_snapshot")

    ordered = [i for i in items if i.get("outcome") == "order_success"]
    already = [i for i in items if i.get("outcome") == "already_holding"]
    failed = [i for i in items if i.get("outcome") == "order_failed"]

    lines = ["[Trader-AI] 자동 매수 결과"]
    lines.append(f"⏰ {kst}")

    if status in ("no_candidates", "balance_error", "balance_exception"):
        lines.append(f"ℹ️ {status}")
    else:
        lines.append(
            f"📊 후보 {candidate_count}개 | 매수성공 {ordered_count}건 | 이미보유 {len(already)}개 | 실패 {len(failed)}건"
        )

    actionable = [i for i in items if i.get("outcome") not in ("already_holding",)]
    if actionable:
        lines.append("\n━━ 매수 상세 ━━")
        for it in actionable:
            outcome = it.get("outcome", "")
            ticker = it.get("ticker", "")
            name = it.get("stock_name") or ticker
            qty = it.get("quantity", "")
            lp = it.get("limit_price")

            if outcome == "order_success":
                lines.append(f"\n✅ {name}({ticker}) {qty}주 @${lp}")
            elif outcome == "order_failed":
                lines.append(f"\n❌ {name}({ticker}) 매수실패: {it.get('error', '')}")
            else:
                lines.append(f"\n⚠️ {name}({ticker}) {outcome}")
                continue

            detail_parts = []
            if it.get("accuracy") is not None:
                detail_parts.append(f"모델정확도{float(it['accuracy']):.0f}%")
            if it.get("rise_probability") is not None:
                detail_parts.append(f"상승확률{float(it['rise_probability']):.1f}%")
            if it.get("rsi") is not None:
                detail_parts.append(f"RSI {float(it['rsi']):.1f}")
            if it.get("golden_cross") is not None:
                detail_parts.append("골든크로스" if it["golden_cross"] else "데드크로스")
            if it.get("macd_buy_signal") is not None:
                detail_parts.append("MACD↑" if it["macd_buy_signal"] else "MACD↓")
            if it.get("sentiment_score") is not None:
                detail_parts.append(f"감성{float(it['sentiment_score']):.2f}")
            if it.get("composite_score") is not None:
                detail_parts.append(f"종합점수{float(it['composite_score']):.2f}")
            if detail_parts:
                lines.append(f"   {' | '.join(detail_parts)}")

    if already:
        lines.append(f"\n➖ 이미 보유: {', '.join(i.get('ticker','') for i in already)}")

    holdings_text = _format_holdings_section(balance)
    if holdings_text:
        lines.append(holdings_text)

    body = "\n".join(lines)
    sent = bool(send_telegram_long_text(body))
    if not sent:
        logger.warning("자동 매수 텔레그램 전송 실패 또는 미설정(TELEGRAM_*)")
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
        "llm_layer": inf.get("llm_layer"),
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
