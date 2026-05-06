"""
프로젝트 공용 로거.

- get_logger() 로만 로거를 얻어 사용한다.
- 기본은 stdout 로깅(쿠버네티스/도커 로그 수집 친화적).
- 파일 로깅은 옵션(LOG_TO_FILE=1)일 때만 활성화한다.
- 모든 로그 메시지는 [JJW] 프리픽스로 통일한다.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

_init_lock = Lock()
_initialized = False


class _RingBufferHandler(logging.Handler):
    """최근 로그를 메모리에 보관(관리자 tail용)."""

    def __init__(self, capacity: int) -> None:
        super().__init__()
        self._buf: deque[str] = deque(maxlen=max(1, int(capacity)))
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            # 포맷 실패는 로깅 자체를 깨지 않게 한다.
            return
        with self._lock:
            self._buf.append(msg)

    def tail(self, lines: int) -> list[str]:
        n = max(1, int(lines))
        with self._lock:
            if not self._buf:
                return []
            if n >= len(self._buf):
                return list(self._buf)
            # deque는 슬라이싱이 안 되므로 list로 변환 후 tail
            data = list(self._buf)
            return data[-n:]


_ring_handler: _RingBufferHandler | None = None


def _ensure_initialized() -> None:
    """핸들러/포맷터 1회 초기화 (중복 핸들러 방지)."""
    global _initialized
    global _ring_handler
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return

        repo_root = Path(__file__).resolve().parents[2]

        level_name = (os.getenv("LOG_LEVEL", "INFO") or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

        fmt = "%(asctime)s [JJW] %(levelname)s %(name)s - %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

        root = logging.getLogger()
        root.setLevel(level)

        # 기존 핸들러 유지 + 우리 핸들러 중복 방지
        existing_ids = {id(h) for h in root.handlers}

        # 관리자 페이지 tail용: 최근 로그를 메모리 링버퍼에 유지
        ring_capacity = int(os.getenv("LOG_RING_MAX_LINES", "5000") or 5000)
        _ring_handler = _RingBufferHandler(capacity=ring_capacity)
        _ring_handler.setLevel(level)
        _ring_handler.setFormatter(formatter)
        if id(_ring_handler) not in existing_ids:
            root.addHandler(_ring_handler)

        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)
        if id(stream) not in existing_ids:
            root.addHandler(stream)

        # 파일 로깅은 로컬/필요 시에만 사용. (K8s에선 stdout 수집이 정석)
        # LOG_TO_FILE=1 이면 파일 로깅 활성화
        log_to_file = (os.getenv("LOG_TO_FILE", "") or "").strip().lower() in ("1", "true", "yes", "y", "on")
        if log_to_file:
            log_dir = Path(os.getenv("LOG_DIR", str(repo_root / "log"))).expanduser()
            log_dir.mkdir(parents=True, exist_ok=True)
            file_name = (os.getenv("LOG_FILE_NAME", "app.log") or "app.log").strip()
            max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)) or (10 * 1024 * 1024))
            backup_count = int(os.getenv("LOG_BACKUP_COUNT", "10") or 10)

            file_path = (log_dir / file_name).resolve()
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            if id(file_handler) not in existing_ids:
                root.addHandler(file_handler)

        # uvicorn/fastapi 기본 로거도 root로 흘리기
        #
        # uvicorn은 자체 핸들러를 달고 propagate=False인 경우가 많아서,
        # root에 붙인 링버퍼(admin/logs memory)로 로그가 들어오지 않을 수 있다.
        # 여기서는 "로그를 하나로 모으는" 쪽을 우선하여, uvicorn 계열 로거의 핸들러를 제거하고
        # propagate=True로 설정한다(루트 포맷/[JJW] 통일 + 링버퍼 수집).
        try:
            for lname in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
                lg = logging.getLogger(lname)
                # uvicorn이 설정한 핸들러(별도 포맷/별도 stdout)를 제거해 중복 출력 방지
                lg.handlers = []
                lg.propagate = True
                lg.setLevel(level)
        except Exception:
            # 로깅 초기화는 앱을 죽이지 않도록 한다.
            pass

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


def tail_memory_logs(lines: int = 250) -> str:
    """
    파일 로그가 없는 환경(K8s stdout 기본)에서도 동작하는 tail.
    반환은 포맷된 문자열 여러 줄을 '\n'으로 join한 결과.
    """
    _ensure_initialized()
    if not _ring_handler:
        return ""
    return "\n".join(_ring_handler.tail(lines))

