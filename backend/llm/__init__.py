"""T-003 模型客户端包：DeepSeek（OpenAI 兼容）+ 测试用假客户端。

只做再导出，便于 T-004 写成 `from llm import DeepSeekClient, FakeDeepSeekClient, DeepSeekError`。
"""

from __future__ import annotations

from .deepseek import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT_SECONDS,
    DeepSeekClient,
    DeepSeekError,
    FakeCall,
    FakeDeepSeekClient,
    MaskedBatch,
    MaskedMessage,
    RequestSnapshot,
    build_user_payload,
    find_unknown_evidence_ids,
    mask_text,
    mask_text_with_count,
    parse_json_object,
    validate_profile_json,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_TIMEOUT_SECONDS",
    "DeepSeekClient",
    "DeepSeekError",
    "FakeCall",
    "FakeDeepSeekClient",
    "MaskedBatch",
    "MaskedMessage",
    "RequestSnapshot",
    "build_user_payload",
    "find_unknown_evidence_ids",
    "mask_text",
    "mask_text_with_count",
    "parse_json_object",
    "validate_profile_json",
]
