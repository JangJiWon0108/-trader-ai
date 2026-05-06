"""
프로젝트 공용 로거.

- get_logger() 로만 로거를 얻어 사용한다.
- 실행 시 log/ 디렉터리를 자동 생성한다.
- 모든 로그 메시지는 [JJW] 프리픽스로 통일한다.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

_init_lock = Lock()
_initialized = False


def _ensure_initialized() -> None:
    """핸들러/포맷터 1회 초기화 (중복 핸들러 방지)."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return

        repo_root = Path(__file__).resolve().parents[2]
        log_dir = Path(os.getenv("LOG_DIR", str(repo_root / "log"))).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)

        level_name = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

        fmt = "%(asctime)s [JJW] %(levelname)s %(name)s - %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

        root = logging.getLogger()
        root.setLevel(level)

        # 기존 핸들러 유지 + 우리 핸들러 중복 방지
        existing_ids = {id(h) for h in root.handlers}

        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)
        if id(stream) not in existing_ids:
            root.addHandler(stream)

        file_path = log_dir / "app.log"
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        if id(file_handler) not in existing_ids:
            root.addHandler(file_handler)

        _initialized = True


def get_logger(name: str | None = None) -> logging.Logger:
    """
    공용 로거 반환.

    사용 예:
      - log = get_logger(__name__)
      - log = get_logger("stock_scheduler")
    """
    _ensure_initialized()
    return logging.getLogger(name or "jjw")

