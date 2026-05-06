"""
Google Generative Language API — `models/{model}:generateContent` (REST).

환경: `.env` 의 GEMINI_API_KEY, GEMINI_MODEL_ID (기본 gemini-2.5-flash).
"""

from __future__ import annotations

# ─── 모듈 임포트 ───
import json
from typing import Any, Optional

import requests

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── 상수 정의 ───

_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


# ─── 공개 API ───


class GeminiApiError(RuntimeError):
    """API HTTP 오류·본문 파싱 실패·빈 candidates 등."""


def generate_content(
    user_text: str,
    *,
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout_sec: float = 120.0,
) -> str:
    """
    사용자 메시지 한 덩어리를 보내고, 모델이 생성한 본문 텍스트를 반환합니다.

    model_id / api_key 를 생략하면 `app.core.config.settings` 값을 사용합니다.
    """
    if not (user_text or "").strip():
        raise GeminiApiError("user_text 가 비어 있습니다.")

    from app.core.config import settings

    mid = (model_id or settings.GEMINI_MODEL_ID or "gemini-2.5-flash").strip()
    key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not key:
        raise GeminiApiError("GEMINI_API_KEY 가 비어 있습니다. .env 를 확인하세요.")

    url = _GENERATE_URL.format(model=mid)
    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_text}],
            }
        ],
    }

    try:
        r = requests.post(
            url,
            params={"key": key},
            json=payload,
            timeout=timeout_sec,
        )
    except requests.RequestException as e:
        raise GeminiApiError(f"요청 실패: {e}") from e

    try:
        data = r.json()
    except json.JSONDecodeError as e:
        raise GeminiApiError(f"JSON 파싱 실패 (HTTP {r.status_code}): {r.text[:500]}") from e

    if r.status_code != 200:
        err = data.get("error") if isinstance(data, dict) else data
        raise GeminiApiError(f"HTTP {r.status_code}: {err}")

    if not isinstance(data, dict):
        raise GeminiApiError(f"예상치 못한 응답 형식: {data!r}")

    cands = data.get("candidates") or []
    if not cands:
        raise GeminiApiError(f"응답에 candidates 없음: {json.dumps(data, ensure_ascii=False)[:2000]}")

    first = cands[0] if isinstance(cands[0], dict) else {}
    content = first.get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        raise GeminiApiError(
            f"응답에 parts 없음 (finishReason={first.get('finishReason')!r}): "
            f"{json.dumps(data, ensure_ascii=False)[:2000]}"
        )

    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            texts.append(str(p.get("text", "")))
    out = "".join(texts).strip()
    if not out:
        logger.warning("Gemini 응답 parts 는 있으나 텍스트가 비어 있음: %s", data)
        return "(빈 텍스트 응답)"
    return out


def get_llm_answer(user_text: str, **kwargs: Any) -> str:
    """질의 한 번 → 답변 텍스트 (`generate_content` 별칭)."""
    return generate_content(user_text, **kwargs)
