"""
LLM 래퍼 재노출.

- 기본 구현: Upstage(OpenAI 호환 API)
- 하위 호환: 기존 코드의 `GeminiApiError` import 를 깨지 않기 위해 alias 제공
"""

from llm.upstage import UpstageApiError, generate_content, get_llm_answer

# Backward-compat alias (기존 import 유지용)
GeminiApiError = UpstageApiError

__all__ = ["UpstageApiError", "GeminiApiError", "generate_content", "get_llm_answer"]
