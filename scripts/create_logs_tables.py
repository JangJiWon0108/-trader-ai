"""
Supabase Management API 로 로그 테이블 생성.

사전 준비:
  1. https://supabase.com/dashboard/account/tokens 에서 PAT 생성
  2. .env 에 SUPABASE_MANAGEMENT_TOKEN=sbp_xxx... 추가

실행:
  .venv/bin/python scripts/create_logs_tables.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
TOKEN = os.getenv("SUPABASE_MANAGEMENT_TOKEN", "")

if not TOKEN:
    print("❌  .env 에 SUPABASE_MANAGEMENT_TOKEN 없음")
    print("   https://supabase.com/dashboard/account/tokens 에서 PAT 생성 후 추가하세요")
    sys.exit(1)

m = re.search(r"https://([^.]+)\.supabase\.co", SUPABASE_URL)
if not m:
    print(f"❌  SUPABASE_URL 파싱 실패: {SUPABASE_URL!r}")
    sys.exit(1)

PROJECT_REF = m.group(1)
API_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ─── SQL 마이그레이션 ───

MIGRATIONS: list[tuple[str, str]] = [
    # ① scheduler_minute_logs 생성 (없으면) + telegram_sent 컬럼
    (
        "scheduler_minute_logs 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS scheduler_minute_logs (
          id               bigint generated always as identity primary key,
          job_type         text        not null,
          kst_at           timestamptz not null default now(),
          ny_et_at         timestamptz,
          ny_trading_date  text,
          market_hours     boolean,
          status           text,
          success          boolean,
          candidate_count  int,
          payload          jsonb,
          telegram_sent    boolean,
          telegram_sent_at timestamptz
        );
        """,
    ),
    (
        "scheduler_minute_items 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS scheduler_minute_items (
          id            bigint generated always as identity primary key,
          run_id        bigint references scheduler_minute_logs(id) on delete cascade,
          ticker        text,
          stock_name    text,
          outcome       text,
          exchange_code text,
          quantity      int,
          limit_price   numeric,
          error         text,
          api_message   text,
          sell_reasons  jsonb
        );
        """,
    ),
    # ② daily_buy_logs
    (
        "daily_buy_logs 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS daily_buy_logs (
          id               bigint generated always as identity primary key,
          kst_at           timestamptz not null default now(),
          ny_trading_date  text        not null,
          success          boolean,
          status           text,
          candidate_count  int,
          ordered_count    int,
          payload          jsonb,
          telegram_sent    boolean,
          telegram_sent_at timestamptz
        );
        """,
    ),
    # ③ daily_buy_items
    (
        "daily_buy_items 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS daily_buy_items (
          id            bigint generated always as identity primary key,
          run_id        bigint references daily_buy_logs(id) on delete cascade,
          ticker        text,
          stock_name    text,
          outcome       text,
          exchange_code text,
          quantity      int,
          limit_price   numeric,
          error         text,
          api_message   text
        );
        """,
    ),
    # ④ daily_economic_logs
    (
        "daily_economic_logs 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS daily_economic_logs (
          id               bigint generated always as identity primary key,
          kst_at           timestamptz not null default now(),
          ny_trading_date  text,
          success          boolean,
          status           text,
          updated_records  int,
          error            text,
          payload          jsonb,
          telegram_sent    boolean,
          telegram_sent_at timestamptz
        );
        """,
    ),
    # ⑤ daily_inference_logs
    (
        "daily_inference_logs 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS daily_inference_logs (
          id               bigint generated always as identity primary key,
          kst_at           timestamptz not null default now(),
          ny_trading_date  text,
          success          boolean,
          status           text,
          error            text,
          payload          jsonb,
          telegram_sent    boolean,
          telegram_sent_at timestamptz
        );
        """,
    ),
    # ⑥ daily_eod_llm_logs
    (
        "daily_eod_llm_logs 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS daily_eod_llm_logs (
          id               bigint generated always as identity primary key,
          kst_at           timestamptz not null default now(),
          ny_trading_date  text        not null,
          success          boolean,
          status           text,
          report_text      text,
          error            text,
          phase            text,
          telegram_sent    boolean,
          telegram_sent_at timestamptz
        );
        """,
    ),
    # ⑦ order_history (KIS 주문 단건 이력)
    (
        "order_history 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS order_history (
          id               bigint generated always as identity primary key,
          kst_at           timestamptz not null default now(),
          ny_trading_date  text,
          side             text        not null,  -- buy / sell
          ticker           text        not null,
          stock_name       text,
          exchange_code    text,
          quantity         int,
          limit_price      numeric,
          order_type       text,
          rt_cd            text,
          api_message      text,
          success          boolean,
          source           text,       -- auto_buy / auto_sell / manual
          payload          jsonb
        );
        CREATE INDEX IF NOT EXISTS idx_order_history_date   ON order_history (ny_trading_date);
        CREATE INDEX IF NOT EXISTS idx_order_history_ticker ON order_history (ticker);
        """,
    ),
    # ⑧ balance_snapshots (일일 잔고 스냅샷)
    (
        "balance_snapshots 테이블 생성",
        """
        CREATE TABLE IF NOT EXISTS balance_snapshots (
          id               bigint generated always as identity primary key,
          kst_at           timestamptz not null default now(),
          ny_trading_date  text,
          holdings_count   int,
          total_eval_usd   numeric,
          payload          jsonb
        );
        """,
    ),
    # ⑧ 인덱스
    (
        "인덱스 생성",
        """
        CREATE INDEX IF NOT EXISTS idx_daily_buy_logs_date    ON daily_buy_logs    (ny_trading_date);
        CREATE INDEX IF NOT EXISTS idx_daily_economic_date    ON daily_economic_logs (ny_trading_date);
        CREATE INDEX IF NOT EXISTS idx_daily_inference_date   ON daily_inference_logs (ny_trading_date);
        CREATE INDEX IF NOT EXISTS idx_daily_eod_llm_date     ON daily_eod_llm_logs   (ny_trading_date);
        CREATE INDEX IF NOT EXISTS idx_balance_snapshots_date ON balance_snapshots     (ny_trading_date);
        """,
    ),
]


def run_sql(label: str, sql: str) -> bool:
    try:
        resp = httpx.post(API_URL, headers=HEADERS, json={"query": sql.strip()}, timeout=30)
        if resp.status_code in (200, 201):
            print(f"  ✅  {label}")
            return True
        else:
            print(f"  ❌  {label}")
            print(f"      HTTP {resp.status_code}: {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"  ❌  {label}: {e}")
        return False


def main() -> None:
    print(f"프로젝트: {PROJECT_REF}\n")
    ok = 0
    fail = 0
    for label, sql in MIGRATIONS:
        if run_sql(label, sql):
            ok += 1
        else:
            fail += 1

    print(f"\n완료: {ok}개 성공, {fail}개 실패")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
