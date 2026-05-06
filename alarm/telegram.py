"""텔레그램 Bot API로 알림 전송. .env 의 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 사용."""

from __future__ import annotations

from typing import Any, Literal, Optional

import requests

from app.utils.logger import get_logger

logger = get_logger(__name__)

ParseMode = Optional[Literal["HTML", "MarkdownV2"]]


def send_telegram_message(
    text: str,
    *,
    parse_mode: ParseMode = None,
    disable_notification: bool = False,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    timeout_sec: float = 10.0,
) -> bool:
    """
    텔레그램으로 텍스트 메시지를 보냅니다.

    token/chat_id 를 넘기지 않으면 app.core.config 의 settings 값을 사용합니다.
    둘 중 하나라도 비어 있으면 전송하지 않고 False 를 반환합니다.
    """
    if not (text or "").strip():
        logger.warning("텔레그램 전송: 빈 메시지는 보내지 않습니다.")
        return False

    tok = (token or "").strip()
    cid = (chat_id or "").strip()
    if not tok or not cid:
        from app.core.config import settings

        tok = (tok or (settings.TELEGRAM_BOT_TOKEN or "")).strip()
        cid = (cid or (settings.TELEGRAM_CHAT_ID or "")).strip()

    if not tok or not cid:
        logger.warning(
            "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 가 비어 있어 알림을 보내지 않습니다."
        )
        return False

    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    payload: dict = {
        "chat_id": cid,
        "text": text,
        "disable_notification": disable_notification,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(url, json=payload, timeout=timeout_sec)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            logger.error("Telegram API 응답 오류: %s", data)
            return False
        return True
    except requests.RequestException as e:
        logger.error("Telegram 전송 실패: %s", e)
        return False


def send_telegram_long_text(
    text: str,
    *,
    chunk_chars: int = 4000,
    **kwargs: Any,
) -> bool:
    """
    긴 본문을 텔레그램 한도(4096자) 이하로 나눠 순차 전송합니다.

    kwargs 는 send_telegram_message 에 그대로 전달됩니다(parse_mode 등).
    """
    body = text or ""
    if len(body) <= chunk_chars:
        return send_telegram_message(body, **kwargs)

    parts: list[str] = []
    i = 0
    while i < len(body):
        parts.append(body[i : i + chunk_chars])
        i += chunk_chars

    ok_all = True
    for n, chunk in enumerate(parts, 1):
        prefix = f"[{n}/{len(parts)}]\n"
        if not send_telegram_message(prefix + chunk, **kwargs):
            ok_all = False
    return ok_all
