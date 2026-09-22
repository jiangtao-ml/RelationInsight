"""T-003 DeepSeek API 客户端封装：OpenAI 兼容 Chat Completions（model=deepseek-chat）。

规格来源
--------
- `ARCHITECTURE.md` §0（v0.1 冻结）：模型名 `deepseek-chat`，OpenAI 兼容接口；脱敏 **策略 α**
  ——`messages.body` 存原文，**调用模型前**正则脱敏，`evidence.quote` 存脱敏后文本。
- `ARCHITECTURE.md` §5：批次 JSON 画像契约；`validate_profile_json()` 按该契约做结构校验。
- `ARCHITECTURE.md` §8：`DEEPSEEK_API_KEY` 只从环境变量读取；`base_url` 假设
  `https://api.deepseek.com`；日志默认 info，body 明文不进日志。
- `PRIVACY.md`：日志与异常信息不得包含聊天原文。

本文件采用、但尚未被规格冻结的假设（已同步到 HANDOFF 的「需人工确认」）
------------------------------------------------------------------------
1. `DEEPSEEK_BASE_URL` 覆盖 base_url（默认 `https://api.deepseek.com`）；`DEEPSEEK_MODEL`
   可覆盖模型名，默认值即规格冻结的 `deepseek-chat`。
2. 脱敏只覆盖策略 α 明列的 4 类：邮箱、手机号、身份证号、银行卡号。QQ 号、微信号、详细地址、
   姓名**不在**范围（留给 T-007 与人工确认）。
3. 18 位纯数字串一律按身份证号处理（与 18 位银行卡号无法从字面区分），故身份证规则排在银行卡
   规则之前；银行卡规则只吃 16-19 位且未被前面规则命中的数字串。
4. 重试：仅 429 / 5xx / 超时 / 连接失败做有限重试（默认 3 次尝试、指数退避）；401 立即失败。
   规格只要求「统一错误类型」，未规定次数。
5. `response_format={"type": "json_object"}` 默认开启（TASKS.md 标注「若 API 支持」）。
6. 只做**结构**校验（键名 / 类型 / confidence 取值域）。证据 `message_id` 是否真的在库中由 T-004
   写库时校验；本模块提供 `strict_evidence_ids` 开关与 `find_unknown_evidence_ids()`，默认只记
   警告不阻断（避免误杀「引用上一批消息」的合理情况）。
7. 本模块**不写数据库**：只负责「脱敏 → 调用 → 校验 → 统一错误」，落库属 T-004。
8. 签名兼容：TASKS.md 写作 `analyze_batch(messages, schema)`，本实现为
   `analyze_batch(messages, system_prompt=None, *, schema=None, ...)`，两个名字都接受。

日志规范（硬性）：只记 `message_id`、条数、模型名、状态码；**不记** body（脱敏前后都不记）。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

logger = logging.getLogger(__name__)

API_KEY_ENV = "DEEPSEEK_API_KEY"
BASE_URL_ENV = "DEEPSEEK_BASE_URL"
MODEL_ENV = "DEEPSEEK_MODEL"

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 1.5
SCHEMA_VERSION = "1.0"

# DeepSeekError.kind 取值（统一错误分类，调用方只比较这些常量）
ERROR_MISSING_KEY = "missing_api_key"
ERROR_MISSING_DEPENDENCY = "missing_dependency"
ERROR_CONFIG = "config_error"
ERROR_AUTH = "auth_error"
ERROR_RATE_LIMIT = "rate_limited"
ERROR_SERVER = "server_error"
ERROR_TIMEOUT = "timeout"
ERROR_CONNECTION = "connection_error"
ERROR_BAD_RESPONSE = "bad_response"

DEFAULT_SYSTEM_PROMPT = """你是关系互动分析助手，只描述「在这段对话里观察到什么」，不做人格评判。
只输出一个 JSON 对象，结构必须是：
{
  "schema_version": "1.0",
  "persons": {
    "A": {"tendencies": [{"claim_key": "...", "statement": "...", "confidence": 0.0, "sample_size": 0, "evidence_message_ids": ["..."]}]},
    "B": {"tendencies": []}
  },
  "dyad": {"tendencies": []},
  "warnings": []
}
硬性禁止：
1) 禁止任何诊断或类型化标签（如「自恋型」「回避型依恋」「抑郁」「人格障碍」）。
2) 禁止操控、试探、PUA、报复、欺骗或施压类建议，也不要指导如何改变对方。
3) 每条 statement 必须能在给出的 messages 里找到依据；evidence_message_ids 只能引用输入中真实
   出现过的 message_id，不得编造。
4) 证据不足时降低 confidence 或写进 warnings，不得虚构事实。
5) 输入正文已脱敏，占位符（如 [手机号]）不得猜测或还原其原值。
6) 不确定的一律留空并写入 warnings，不要为了凑满结构而编内容。
"""

# ---------------------------------------------------------------- 脱敏（策略 α）

MASK_EMAIL = "[邮箱]"
MASK_PHONE = "[手机号]"
MASK_ID_CARD = "[身份证号]"
MASK_BANK_CARD = "[银行卡号]"

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[\s\-]?)?1[3-9]\d{9}(?!\d)")
ID_CARD_PATTERN = re.compile(r"(?<![0-9A-Za-z])\d{17}[\dXx](?![0-9A-Za-z])")
BANK_CARD_PATTERN = re.compile(r"(?<!\d)\d{16,19}(?!\d)")

# 顺序有意义：身份证（18 位）必须先于银行卡（16-19 位），否则 18 位身份证会被当成银行卡。
MASK_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", EMAIL_PATTERN, MASK_EMAIL),
    ("phone", PHONE_PATTERN, MASK_PHONE),
    ("id_card", ID_CARD_PATTERN, MASK_ID_CARD),
    ("bank_card", BANK_CARD_PATTERN, MASK_BANK_CARD),
)


class DeepSeekError(RuntimeError):
    """统一错误类型：401 / 429 / 5xx / 超时 / 缺 Key / 返回体不合法，全部归一到这里。

    - `kind`：ERROR_* 常量之一；
    - `status_code`：HTTP 状态码（无则 None）；
    - `retryable`：是否属于可重试类别（429 / 5xx / 超时 / 连接失败）；
    - `attempts`：实际尝试次数。

    约定：`detail` 与 `str(error)` **不得**包含聊天原文或 API Key（只出现类名、状态码、条数）。
    """

    def __init__(
        self,
        kind: str,
        detail: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        attempts: int = 1,
        request_id: str | None = None,
    ) -> None:
        super().__init__(f"[{kind}] {detail}")
        self.kind = kind
        self.detail = detail
        self.status_code = status_code
        self.retryable = retryable
        self.attempts = attempts
        self.request_id = request_id


def mask_text(text: str) -> str:
    """策略 α：把 4 类强标识替换为中文占位符（占位符不含数字，故本函数幂等）。"""
    return mask_text_with_count(text)[0]


def mask_text_with_count(text: str) -> tuple[str, int]:
    """脱敏并返回替换处数（顺序 `subn`，不会重复计数同一个数字串）。"""
    masked = text
    total = 0
    for _name, pattern, placeholder in MASK_RULES:
        masked, replaced = pattern.subn(placeholder, masked)
        total += replaced
    return masked, total


# ---------------------------------------------------------------- 数据容器


@dataclass(frozen=True)
class MaskedMessage:
    """一条已脱敏、可直接发给模型的消息（原文只存在本机库里）。"""

    message_id: str
    seq: int
    speaker: str
    text: str
    original_length: int
    mask_count: int

    @property
    def redacted(self) -> bool:
        return self.mask_count > 0


@dataclass
class MaskedBatch:
    """一个已脱敏批次。`mask_count == 0` 表示这批消息不含任何强标识。"""

    conversation_id: str
    messages: list[MaskedMessage] = field(default_factory=list)

    @property
    def message_ids(self) -> list[str]:
        return [m.message_id for m in self.messages]

    @property
    def mask_count(self) -> int:
        return sum(m.mask_count for m in self.messages)

    @property
    def unknown_speaker_count(self) -> int:
        return sum(1 for m in self.messages if m.speaker == "?")

    def __len__(self) -> int:
        return len(self.messages)


@dataclass(frozen=True)
class RequestSnapshot:
    """最近一次请求的元数据：只有 ID / 条数 / 长度，**不含**任何聊天文本。"""

    model: str
    conversation_id: str
    message_ids: tuple[str, ...]
    masked_count: int
    system_prompt_length: int
    user_content_length: int
    attempt: int
    request_id: str | None
    latency_seconds: float | None


@dataclass(frozen=True)
class _IncomingMessage:
    """内部中间态：把 MessageDTO / dict 归一成同一形状。"""

    message_id: str
    seq: int
    speaker: str
    body: str
    conversation_id: str | None


def _field(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _coerce_message(
    item: Any, index: int, person_roles: Mapping[str, str] | None
) -> _IncomingMessage:
    """接受 `parser.MessageDTO`、dict 或任意带同名属性的对象。

    说话人解析顺序：`speaker` → `role` → `person_roles[person_id]` → `?`。
    （`MessageDTO` 只有 `person_id`，所以 T-004 应传 `person_roles`，见模块 docstring 假设。）
    """
    message_id = _field(item, "message_id")
    if not isinstance(message_id, str) or not message_id:
        raise DeepSeekError(ERROR_CONFIG, f"第 {index} 条消息缺少 message_id")

    body = _field(item, "body")
    if not isinstance(body, str):
        raise DeepSeekError(ERROR_CONFIG, f"第 {index} 条消息缺少 body，或 body 不是字符串")

    seq = _field(item, "seq", index)
    if isinstance(seq, bool) or not isinstance(seq, int):
        seq = index

    speaker = _field(item, "speaker") or _field(item, "role")
    if not isinstance(speaker, str) or not speaker:
        person_id = _field(item, "person_id")
        if person_roles and isinstance(person_id, str) and person_id in person_roles:
            speaker = person_roles[person_id]
    if not isinstance(speaker, str) or not speaker:
        speaker = "?"

    conversation_id = _field(item, "conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id:
        conversation_id = None

    return _IncomingMessage(
        message_id=message_id,
        seq=seq,
        speaker=speaker,
        body=body,
        conversation_id=conversation_id,
    )


# ---------------------------------------------------------------- payload / 解析 / 校验


def build_user_payload(batch: MaskedBatch) -> str:
    """把脱敏后的批次组装成 user content（纯 JSON，便于断言「发出去的就是脱敏文本」）。"""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "conversation_id": batch.conversation_id,
        "masking": {
            "policy": "alpha",
            "applied": True,
            "replaced_total": batch.mask_count,
            "note": "所有 text 字段均为正则脱敏后的文本；占位符原值只存在本机，不得推测或还原。",
        },
        "messages": [
            {
                "message_id": message.message_id,
                "seq": message.seq,
                "speaker": message.speaker,
                "text": message.text,
            }
            for message in batch.messages
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def parse_json_object(content: str, *, request_id: str | None = None) -> dict:
    """从模型返回文本中取出 JSON 对象（容忍 ``` 围栏与前后说明文字）。"""
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError(ERROR_BAD_RESPONSE, "模型返回内容为空", request_id=request_id)

    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise DeepSeekError(
                ERROR_BAD_RESPONSE, "模型返回内容不是合法 JSON", request_id=request_id
            ) from exc
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as inner:
            raise DeepSeekError(
                ERROR_BAD_RESPONSE, f"模型返回内容不是合法 JSON（{inner.msg}）", request_id=request_id
            ) from inner

    if not isinstance(data, dict):
        raise DeepSeekError(ERROR_BAD_RESPONSE, "画像 JSON 顶层必须是对象", request_id=request_id)
    return data


_TENDENCY_FIELDS = ("claim_key", "statement", "confidence", "sample_size", "evidence_message_ids")


def validate_profile_json(data: Any) -> dict:
    """按 `ARCHITECTURE.md` §5 做结构校验；不合法抛 DeepSeekError(bad_response)。"""
    if not isinstance(data, Mapping):
        raise DeepSeekError(ERROR_BAD_RESPONSE, "画像 JSON 顶层必须是对象")

    missing = [key for key in ("schema_version", "persons", "dyad", "warnings") if key not in data]
    if missing:
        raise DeepSeekError(ERROR_BAD_RESPONSE, f"画像 JSON 缺少必需字段：{missing}")
    if not isinstance(data["schema_version"], str) or not data["schema_version"]:
        raise DeepSeekError(ERROR_BAD_RESPONSE, "schema_version 必须是非空字符串")

    persons = data["persons"]
    if not isinstance(persons, Mapping):
        raise DeepSeekError(ERROR_BAD_RESPONSE, "persons 必须是对象")
    for role in ("A", "B"):
        if role not in persons:
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"persons 缺少说话人 {role}")
        _validate_tendencies(_block_tendencies(persons[role], where=f"persons.{role}"), where=f"persons.{role}")

    dyad = data["dyad"]
    if not isinstance(dyad, Mapping):
        raise DeepSeekError(ERROR_BAD_RESPONSE, "dyad 必须是对象")
    _validate_tendencies(_block_tendencies(dyad, where="dyad"), where="dyad")

    if not isinstance(data["warnings"], list):
        raise DeepSeekError(ERROR_BAD_RESPONSE, "warnings 必须是列表")
    return dict(data)


def _block_tendencies(block: Any, *, where: str) -> list:
    if not isinstance(block, Mapping):
        raise DeepSeekError(ERROR_BAD_RESPONSE, f"{where} 必须是对象")
    tendencies = block.get("tendencies")
    if not isinstance(tendencies, list):
        raise DeepSeekError(ERROR_BAD_RESPONSE, f"{where}.tendencies 必须是列表")
    return tendencies


def _validate_tendencies(tendencies: list, *, where: str) -> None:
    for index, tendency in enumerate(tendencies):
        label = f"{where}.tendencies[{index}]"
        if not isinstance(tendency, Mapping):
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label} 必须是对象")

        missing = [key for key in _TENDENCY_FIELDS if key not in tendency]
        if missing:
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label} 缺少字段：{missing}")

        if not isinstance(tendency["claim_key"], str) or not tendency["claim_key"]:
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label}.claim_key 必须是非空字符串")
        if not isinstance(tendency["statement"], str) or not tendency["statement"].strip():
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label}.statement 必须是非空字符串")

        confidence = tendency["confidence"]
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label}.confidence 必须是 0~1 之间的数字")

        sample_size = tendency["sample_size"]
        if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label}.sample_size 必须是非负整数")

        evidence_ids = tendency["evidence_message_ids"]
        if not isinstance(evidence_ids, list) or not all(isinstance(i, str) and i for i in evidence_ids):
            raise DeepSeekError(ERROR_BAD_RESPONSE, f"{label}.evidence_message_ids 必须是非空字符串列表")


def iter_tendencies(data: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """遍历画像里的所有结论（persons.A / persons.B / dyad），产出 (位置, 结论)。"""
    persons = data.get("persons") or {}
    if isinstance(persons, Mapping):
        for role, block in persons.items():
            if not isinstance(block, Mapping):
                continue
            for tendency in block.get("tendencies") or []:
                if isinstance(tendency, Mapping):
                    yield f"persons.{role}", tendency

    dyad = data.get("dyad") or {}
    if isinstance(dyad, Mapping):
        for tendency in dyad.get("tendencies") or []:
            if isinstance(tendency, Mapping):
                yield "dyad", tendency


def find_unknown_evidence_ids(data: Mapping[str, Any], known_ids: Iterable[str]) -> list[str]:
    """返回画像里引用了、但不在 `known_ids` 中的证据 ID（T-004 写库前的自查）。"""
    known = set(known_ids)
    unknown: list[str] = []
    for _where, tendency in iter_tendencies(data):
        for evidence_id in tendency.get("evidence_message_ids") or []:
            if isinstance(evidence_id, str) and evidence_id not in known and evidence_id not in unknown:
                unknown.append(evidence_id)
    return unknown


# ---------------------------------------------------------------- 错误归一


def translate_exception(exc: BaseException) -> DeepSeekError:
    """把各种 SDK / 网络异常翻译成 DeepSeekError。

    只用异常类名与状态码判断，**不**把异常原文（可能含请求体）拼进错误信息。
    """
    if isinstance(exc, DeepSeekError):
        return exc

    name = type(exc).__name__
    lowered = name.lower()
    status = getattr(exc, "status_code", None)

    if status == 401 or "authentication" in lowered or "permissiondenied" in lowered:
        return DeepSeekError(
            ERROR_AUTH,
            f"鉴权失败（HTTP {status or 401}）：请检查环境变量 {API_KEY_ENV} 是否有效",
            status_code=status or 401,
        )
    if status == 429 or "ratelimit" in lowered:
        return DeepSeekError(
            ERROR_RATE_LIMIT,
            "触发限流（HTTP 429）：稍后重试或降低并发",
            status_code=status or 429,
            retryable=True,
        )
    if isinstance(status, int) and status >= 500:
        return DeepSeekError(
            ERROR_SERVER, f"服务端错误（HTTP {status}）", status_code=status, retryable=True
        )
    if isinstance(exc, TimeoutError) or "timeout" in lowered:
        return DeepSeekError(ERROR_TIMEOUT, f"请求超时（{name}）", retryable=True)
    if isinstance(exc, ConnectionError) or "connection" in lowered:
        return DeepSeekError(ERROR_CONNECTION, f"连接失败（{name}）", retryable=True)
    if isinstance(status, int) and 400 <= status < 500:
        return DeepSeekError(ERROR_BAD_RESPONSE, f"请求被拒绝（HTTP {status}）", status_code=status)
    return DeepSeekError(ERROR_BAD_RESPONSE, f"未预期的错误类型（{name}）")


def _extract_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise DeepSeekError(ERROR_BAD_RESPONSE, "模型返回体缺少 choices[0].message.content") from exc
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError(ERROR_BAD_RESPONSE, "模型返回内容为空")
    return content


def _extract_request_id(response: Any) -> str | None:
    for attribute in ("id", "_request_id"):
        value = getattr(response, attribute, None)
        if isinstance(value, str) and value:
            return value
    return None


# ---------------------------------------------------------------- 客户端


class BaseDeepSeekClient:
    """共用骨架：脱敏 → 组装 payload → 调用（带重试）→ 解析 → 结构校验。

    真实客户端只需实现 `_complete()`；`FakeDeepSeekClient` 复用同一套脱敏/校验逻辑，
    因此单测覆盖到的脱敏行为与线上一致。
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.model = model
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.timeout = float(timeout)
        self._sleep = sleep if sleep is not None else time.sleep
        self.last_request: RequestSnapshot | None = None

    # -- 脱敏 ----------------------------------------------------------

    def mask_batch(
        self,
        messages: Iterable[Any],
        *,
        conversation_id: str | None = None,
        person_roles: Mapping[str, str] | None = None,
    ) -> MaskedBatch:
        """把消息序列脱敏成可发送的批次（永不返回原始 body）。"""
        if messages is None or isinstance(messages, (str, bytes, Mapping)):
            raise DeepSeekError(ERROR_CONFIG, "messages 必须是消息序列（MessageDTO / dict 列表）")

        masked_messages: list[MaskedMessage] = []
        conversation_ids: set[str] = set()

        for index, item in enumerate(messages):
            incoming = _coerce_message(item, index, person_roles)
            masked_body, mask_count = mask_text_with_count(incoming.body)
            masked_messages.append(
                MaskedMessage(
                    message_id=incoming.message_id,
                    seq=incoming.seq,
                    speaker=incoming.speaker,
                    text=masked_body,
                    original_length=len(incoming.body),
                    mask_count=mask_count,
                )
            )
            if incoming.conversation_id:
                conversation_ids.add(incoming.conversation_id)

        if len(conversation_ids) > 1 and conversation_id is None:
            raise DeepSeekError(ERROR_CONFIG, "同一批只能包含同一个 conversation_id")

        resolved_conversation_id = conversation_id or (sorted(conversation_ids)[0] if conversation_ids else "unknown")
        return MaskedBatch(conversation_id=resolved_conversation_id, messages=masked_messages)

    # -- 主入口 --------------------------------------------------------

    def analyze_batch(
        self,
        messages: Sequence[Any] | Iterable[Any],
        system_prompt: str | None = None,
        *,
        schema: str | None = None,
        conversation_id: str | None = None,
        person_roles: Mapping[str, str] | None = None,
        strict_evidence_ids: bool = False,
    ) -> dict:
        """脱敏后调用模型，返回通过 `ARCHITECTURE.md` §5 结构校验的画像 dict。

        - `system_prompt`：系统提示词（必填语义；`schema` 是同义别名，兼容 TASKS.md 的写法）。
        - `person_roles`：`person_id -> "A"/"B"` 映射，供 `MessageDTO` 反查说话人（建议 T-004 传入）。
        - `strict_evidence_ids=True` 时，引用了本批不存在的 `message_id` 直接判为 bad_response。
        """
        prompt = system_prompt if system_prompt is not None else schema
        if prompt is None:
            prompt = DEFAULT_SYSTEM_PROMPT
        if not isinstance(prompt, str) or not prompt.strip():
            raise DeepSeekError(ERROR_CONFIG, "system_prompt 必须是非空字符串")

        batch = self.mask_batch(messages, conversation_id=conversation_id, person_roles=person_roles)
        if not batch.messages:
            raise DeepSeekError(ERROR_CONFIG, "messages 为空：拒绝发送空批次")
        if batch.unknown_speaker_count:
            logger.warning(
                "analyze_batch: %d/%d 条消息无法确定说话人（T-004 应传 person_roles）",
                batch.unknown_speaker_count,
                len(batch),
            )

        user_content = build_user_payload(batch)
        logger.info(
            "analyze_batch: model=%s conversation=%s messages=%d masked=%d first_id=%s last_id=%s",
            self.model,
            batch.conversation_id,
            len(batch),
            batch.mask_count,
            batch.message_ids[0],
            batch.message_ids[-1],
        )

        started = time.monotonic()
        content, request_id, attempt = self._request_with_retries(
            system_prompt=prompt, user_content=user_content
        )
        self.last_request = RequestSnapshot(
            model=self.model,
            conversation_id=batch.conversation_id,
            message_ids=tuple(batch.message_ids),
            masked_count=batch.mask_count,
            system_prompt_length=len(prompt),
            user_content_length=len(user_content),
            attempt=attempt,
            request_id=request_id,
            latency_seconds=round(time.monotonic() - started, 3),
        )

        data = parse_json_object(content, request_id=request_id)
        validate_profile_json(data)

        unknown = find_unknown_evidence_ids(data, batch.message_ids)
        if unknown:
            if strict_evidence_ids:
                raise DeepSeekError(
                    ERROR_BAD_RESPONSE,
                    f"返回的 evidence_message_ids 有 {len(unknown)} 个不在本批输入中（strict_evidence_ids=True，拒绝入库）",
                    request_id=request_id,
                )
            logger.warning(
                "analyze_batch: 返回的 evidence_message_ids 有 %d 个不在本批输入中（交 T-004 校验）",
                len(unknown),
            )
        return data

    # -- 重试 / 单次调用 ------------------------------------------------

    def _request_with_retries(
        self, *, system_prompt: str, user_content: str
    ) -> tuple[str, str | None, int]:
        last_error: DeepSeekError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                content, request_id = self._complete(
                    model=self.model,
                    system_prompt=system_prompt,
                    user_content=user_content,
                    timeout=self.timeout,
                    attempt=attempt,
                )
                return content, request_id, attempt
            except Exception as exc:  # noqa: BLE001 —— 统一翻译为 DeepSeekError
                error = translate_exception(exc)
                if not error.retryable or attempt >= self.max_attempts:
                    error.attempts = attempt
                    logger.warning(
                        "analyze_batch 失败：kind=%s status=%s attempts=%d（日志不含正文）",
                        error.kind,
                        error.status_code,
                        attempt,
                    )
                    raise error from exc
                last_error = error
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "analyze_batch 可重试错误：kind=%s status=%s attempt=%d/%d delay=%.1fs",
                    error.kind,
                    error.status_code,
                    attempt,
                    self.max_attempts,
                    delay,
                )
                if delay > 0:
                    self._sleep(delay)

        raise last_error or DeepSeekError(ERROR_BAD_RESPONSE, "未知失败：重试循环未产生结果")

    def _complete(
        self, *, model: str, system_prompt: str, user_content: str, timeout: float, attempt: int = 1
    ) -> tuple[str, str | None]:
        raise NotImplementedError


class DeepSeekClient(BaseDeepSeekClient):
    """真实客户端：OpenAI 兼容 Chat Completions，`model=deepseek-chat`。

    Key 只从 `DEEPSEEK_API_KEY` 读取（或显式构造参数），base_url 默认 `https://api.deepseek.com`。
    `client=` 可注入自建/替身客户端，单测据此避免真实网络。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        client: Any | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.environ.get(API_KEY_ENV, "")
        if not isinstance(resolved_key, str) or not resolved_key.strip():
            raise DeepSeekError(
                ERROR_MISSING_KEY,
                f"未配置 API Key：请设置环境变量 {API_KEY_ENV}（不要写进代码，也不要提交 .env）",
            )

        resolved_base_url = base_url if base_url is not None else (os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL)
        resolved_model = model if model is not None else (os.environ.get(MODEL_ENV) or DEFAULT_MODEL)
        resolved_timeout = float(timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS)

        super().__init__(
            model=(resolved_model or DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            timeout=resolved_timeout,
            sleep=sleep,
        )
        self.api_key = resolved_key.strip()
        self.base_url = (resolved_base_url or DEFAULT_BASE_URL).rstrip("/")
        self._client = client  # 注入点：单测传替身，避免真实网络

    def __repr__(self) -> str:
        # 刻意不打印 api_key：避免日志/异常回溯把 Key 带出去
        return (
            f"DeepSeekClient(model={self.model!r}, base_url={self.base_url!r}, "
            f"max_attempts={self.max_attempts}, timeout={self.timeout})"
        )

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import openai
        except ImportError as exc:
            raise DeepSeekError(
                ERROR_MISSING_DEPENDENCY, "未安装 openai 包：pip install -r requirements.txt"
            ) from exc
        self._client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        return self._client

    def _complete(
        self, *, model: str, system_prompt: str, user_content: str, timeout: float, attempt: int = 1
    ) -> tuple[str, str | None]:
        client = self._ensure_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        return _extract_content(response), _extract_request_id(response)


@dataclass
class FakeCall:
    """一次假调用的记录：只保留**脱敏后**文本与 ID，用于断言「原文没被发出去」。"""

    model: str
    system_prompt: str
    payload: dict
    attempt: int
    timeout: float

    @property
    def message_ids(self) -> list[str]:
        return [item["message_id"] for item in self.payload.get("messages", [])]

    @property
    def texts(self) -> list[str]:
        return [item["text"] for item in self.payload.get("messages", [])]


class FakeDeepSeekClient(BaseDeepSeekClient):
    """单测用假客户端：不联网、不读 Key，返回符合 `ARCHITECTURE.md` §5 的 JSON。

    - `responses`：按调用顺序返回的 dict / JSON 字符串队列；用完后回落到 `default_profile()`。
    - `error`：本次调用要抛出的异常（用于验证统一错误与重试，不涉及网络）。
    - `calls`：每次调用的记录（含脱敏后的 payload），原始 body 不会被保存。
    """

    def __init__(
        self,
        *,
        responses: Sequence[dict | str] | None = None,
        error: BaseException | None = None,
        model: str = DEFAULT_MODEL,
        schema_version: str = SCHEMA_VERSION,
        claim_key: str = "A.request_style",
        max_attempts: int = 1,
    ) -> None:
        super().__init__(
            model=model,
            max_attempts=max_attempts,
            backoff_seconds=0.0,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            sleep=lambda _seconds: None,  # 单测不真的等待
        )
        self.responses = list(responses or [])
        self.error = error
        self.schema_version = schema_version
        self.claim_key = claim_key
        self.calls: list[FakeCall] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def _complete(
        self, *, model: str, system_prompt: str, user_content: str, timeout: float, attempt: int = 1
    ) -> tuple[str, str | None]:
        payload = json.loads(user_content)  # payload 必须是严格 JSON
        self.calls.append(
            FakeCall(
                model=model,
                system_prompt=system_prompt,
                payload=payload,
                attempt=attempt,
                timeout=timeout,
            )
        )
        if self.error is not None:
            raise self.error
        if self.responses:
            nxt = self.responses.pop(0)
            content = nxt if isinstance(nxt, str) else json.dumps(nxt, ensure_ascii=False)
        else:
            content = json.dumps(self.default_profile(payload), ensure_ascii=False)
        return content, f"fake-request-{len(self.calls):04d}"

    def default_profile(self, payload: Mapping[str, Any]) -> dict:
        """按 §5 契约生成合法画像：证据 ID 只取自本次输入，不编造。"""
        by_speaker: dict[str, list[str]] = {}
        for item in payload.get("messages", []):
            by_speaker.setdefault(str(item.get("speaker", "?")), []).append(str(item.get("message_id")))

        suffix = self.claim_key.split(".", 1)[-1]
        persons: dict[str, Any] = {}
        for role in ("A", "B"):
            ids = by_speaker.get(role, [])
            tendencies: list[dict] = []
            if ids:
                tendencies.append(
                    {
                        "claim_key": f"{role}.{suffix}",
                        "statement": f"{role} 在本批对话中呈现出可复现的互动模式（假客户端占位结论）。",
                        "confidence": 0.5,
                        "sample_size": len(ids),
                        "evidence_message_ids": ids[:3],
                    }
                )
            persons[role] = {"tendencies": tendencies}

        return {
            "schema_version": self.schema_version,
            "persons": persons,
            "dyad": {"tendencies": []},
            "warnings": [] if payload.get("messages") else ["输入为空"],
        }
