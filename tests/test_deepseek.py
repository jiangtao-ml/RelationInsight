"""T-003 DeepSeek 客户端测试：全程离线（注入替身客户端 / 使用 FakeDeepSeekClient，不联网、不读真实 Key）。"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from llm import DeepSeekClient as PackagedDeepSeekClient  # noqa: E402
from llm.deepseek import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    ERROR_AUTH,
    ERROR_BAD_RESPONSE,
    ERROR_CONFIG,
    ERROR_CONNECTION,
    ERROR_MISSING_KEY,
    ERROR_RATE_LIMIT,
    ERROR_SERVER,
    ERROR_TIMEOUT,
    DeepSeekClient,
    DeepSeekError,
    FakeDeepSeekClient,
    find_unknown_evidence_ids,
    mask_text,
    parse_json_object,
    validate_profile_json,
)
from parser import make_message_id, make_person_id, parse_chat  # noqa: E402

CONVERSATION_ID = "conv-t003"

# 策略 α 的四类强标识各来一个（用于断言「发出去的文本里没有这些原值」）
SECRET_BODY = (
    "我的手机号是 13800138000，邮箱 zhangsan@example.com，"
    "身份证 110101199003071234，卡号 6222021234567890。"
)
SECRETS = ("13800138000", "zhangsan@example.com", "110101199003071234", "6222021234567890")

VALID_PROFILE = {
    "schema_version": "1.0",
    "persons": {
        "A": {
            "tendencies": [
                {
                    "claim_key": "A.request_style",
                    "statement": "在这段对话里较常直接提出请求。",
                    "confidence": 0.6,
                    "sample_size": 2,
                    "evidence_message_ids": [],
                }
            ]
        },
        "B": {"tendencies": []},
    },
    "dyad": {"tendencies": []},
    "warnings": [],
}


def _message(message_id: str, seq: int, speaker: str, body: str) -> dict:
    return {"message_id": message_id, "seq": seq, "speaker": speaker, "body": body}


SINGLE_MESSAGE = [_message("msg-1", 0, "A", "你好")]


# ---------------------------------------------------------------- 替身（不联网）


def _openai_response(content: str, *, request_id: str = "req-stub-0001") -> SimpleNamespace:
    return SimpleNamespace(
        id=request_id, choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class _StubCompletions:
    def __init__(self, owner: "StubOpenAI") -> None:
        self._owner = owner

    def create(self, **kwargs):
        self._owner.requests.append(kwargs)
        if self._owner.errors:
            raise self._owner.errors.pop(0)
        content = (
            self._owner.contents.pop(0)
            if self._owner.contents
            else json.dumps(VALID_PROFILE, ensure_ascii=False)
        )
        return _openai_response(content)


class StubOpenAI:
    """最小 OpenAI SDK 替身：记录请求参数、可返回内容或抛异常。"""

    def __init__(self, *, contents=None, errors=None) -> None:
        self.contents = list(contents or [])
        self.errors = list(errors or [])
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=_StubCompletions(self))


# 类名刻意与 openai SDK 的异常一致：translate_exception() 只按类名 + status_code 判断
class AuthenticationError(Exception):
    status_code = 401


class RateLimitError(Exception):
    status_code = 429


class InternalServerError(Exception):
    status_code = 500


class APITimeoutError(Exception):
    """与 openai.APITimeoutError 同名，且没有 status_code。"""


class APIConnectionError(Exception):
    pass


@pytest.fixture()
def deepseek_env(monkeypatch):
    """干净基线：清掉本机 DEEPSEEK_* 变量，避免真实 Key/URL 影响断言（结束自动还原）。"""
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-not-a-real-key")
    return monkeypatch


def _client(deepseek_env, **kwargs) -> DeepSeekClient:
    kwargs.setdefault("client", StubOpenAI())
    kwargs.setdefault("max_attempts", 1)
    return DeepSeekClient(**kwargs)


# ---------------------------------------------------------------- 脱敏（策略 α）


def test_mask_text_covers_all_four_policy_alpha_classes() -> None:
    masked = mask_text(SECRET_BODY)

    for secret in SECRETS:
        assert secret not in masked
    assert "[手机号]" in masked
    assert "[邮箱]" in masked
    assert "[身份证号]" in masked
    assert "[银行卡号]" in masked
    assert mask_text(masked) == masked  # 幂等：占位符不含数字


def test_mask_text_keeps_ordinary_numbers() -> None:
    text = "我们约在 3 点，工位 12 号，排队第 5 位。"
    assert mask_text(text) == text


# ---------------------------------------------------------------- 配置与 Key


def test_package_reexports_client() -> None:
    assert PackagedDeepSeekClient is DeepSeekClient


def test_client_reads_key_base_url_and_model_from_env(mocker, deepseek_env) -> None:
    mocker.patch.dict(
        "os.environ",
        {"DEEPSEEK_BASE_URL": "https://example.invalid/v1", "DEEPSEEK_MODEL": "deepseek-reasoner"},
    )
    client = DeepSeekClient(client=StubOpenAI())

    assert client.api_key == "sk-not-a-real-key"
    assert client.base_url == "https://example.invalid/v1"
    assert client.model == "deepseek-reasoner"
    assert "sk-not-a-real-key" not in repr(client)  # 打印对象不泄出 Key

    mocker.stopall()  # 还原环境变量 → 回落到规格默认值
    fallback = DeepSeekClient(client=StubOpenAI())
    assert fallback.base_url == DEFAULT_BASE_URL == "https://api.deepseek.com"
    assert fallback.model == DEFAULT_MODEL == "deepseek-chat"


def test_missing_api_key_raises_unified_error(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(DeepSeekError) as excinfo:
        DeepSeekClient()

    assert excinfo.value.kind == ERROR_MISSING_KEY
    assert "DEEPSEEK_API_KEY" in str(excinfo.value)


# ---------------------------------------------------------------- 调用前脱敏


def test_analyze_batch_masks_body_before_sending(deepseek_env) -> None:
    stub = StubOpenAI()
    client = _client(deepseek_env, client=stub)

    messages = [
        _message("msg-0", 0, "A", SECRET_BODY),
        _message("msg-1", 1, "B", SECRET_BODY),
    ]
    profile = client.analyze_batch(messages, "只输出 JSON")

    assert len(stub.requests) == 1
    request = stub.requests[0]
    assert request["model"] == "deepseek-chat"
    assert request["messages"][0] == {"role": "system", "content": "只输出 JSON"}
    assert request["messages"][1]["role"] == "user"

    user_content = request["messages"][1]["content"]
    for secret in SECRETS:
        assert secret not in user_content  # 原文没有被发出去
    assert "[手机号]" in user_content
    assert "msg-0" in user_content and "msg-1" in user_content  # 证据 ID 必须带上

    assert profile["schema_version"] == "1.0"
    assert client.last_request.message_ids == ("msg-0", "msg-1")
    assert client.last_request.masked_count == 8  # 每条 4 处
    assert client.last_request.attempt == 1


def test_analyze_batch_accepts_schema_alias_and_rejects_empty_batch(deepseek_env) -> None:
    stub = StubOpenAI()
    client = _client(deepseek_env, client=stub)

    client.analyze_batch(SINGLE_MESSAGE, schema="SCHEMA-AS-PROMPT")
    assert stub.requests[0]["messages"][0]["content"] == "SCHEMA-AS-PROMPT"

    with pytest.raises(DeepSeekError) as excinfo:
        client.analyze_batch([], DEFAULT_SYSTEM_PROMPT)
    assert excinfo.value.kind == ERROR_CONFIG
    assert len(stub.requests) == 1  # 空批次不发起请求


def test_default_system_prompt_carries_the_prohibitions() -> None:
    for keyword in ("禁止", "诊断", "message_id", "脱敏"):
        assert keyword in DEFAULT_SYSTEM_PROMPT


# ---------------------------------------------------------------- 统一错误 + 重试


@pytest.mark.parametrize(
    ("error", "kind", "status_code"),
    [
        (AuthenticationError("401 upstream"), ERROR_AUTH, 401),
        (RateLimitError("429 upstream"), ERROR_RATE_LIMIT, 429),
        (InternalServerError("500 upstream"), ERROR_SERVER, 500),
        (APITimeoutError("timed out"), ERROR_TIMEOUT, None),
        (APIConnectionError("connector closed"), ERROR_CONNECTION, None),
    ],
)
def test_sdk_errors_are_normalised_to_deepseek_error(deepseek_env, error, kind, status_code) -> None:
    stub = StubOpenAI(errors=[error])
    client = _client(deepseek_env, client=stub)

    with pytest.raises(DeepSeekError) as excinfo:
        client.analyze_batch(SINGLE_MESSAGE, DEFAULT_SYSTEM_PROMPT)

    assert excinfo.value.kind == kind
    assert excinfo.value.status_code == status_code
    assert excinfo.value.attempts == 1
    assert len(stub.requests) == 1


def test_rate_limit_is_retried_then_succeeds(deepseek_env) -> None:
    stub = StubOpenAI(errors=[RateLimitError("429 upstream")])
    sleeps: list[float] = []
    client = DeepSeekClient(
        client=stub, max_attempts=2, backoff_seconds=0.0, sleep=sleeps.append
    )

    profile = client.analyze_batch(SINGLE_MESSAGE, "只输出 JSON")

    assert len(stub.requests) == 2
    assert sleeps == []  # backoff=0 → 测试里不真的等待
    assert profile["persons"]["A"]["tendencies"][0]["claim_key"] == "A.request_style"
    assert client.last_request.attempt == 2


def test_auth_error_is_not_retried(deepseek_env) -> None:
    stub = StubOpenAI(errors=[AuthenticationError("401"), AuthenticationError("401")])
    client = DeepSeekClient(client=stub, max_attempts=3, backoff_seconds=0.0, sleep=lambda _s: None)

    with pytest.raises(DeepSeekError) as excinfo:
        client.analyze_batch(SINGLE_MESSAGE, "只输出 JSON")

    assert excinfo.value.kind == ERROR_AUTH
    assert len(stub.requests) == 1  # 401 立即失败，不重试


def test_error_messages_never_include_chat_body(deepseek_env) -> None:
    stub = StubOpenAI(errors=[InternalServerError(f"upstream complained about: {SECRET_BODY}")])
    client = _client(deepseek_env, client=stub)

    with pytest.raises(DeepSeekError) as excinfo:
        client.analyze_batch([_message("msg-1", 0, "A", SECRET_BODY)], DEFAULT_SYSTEM_PROMPT)

    for secret in SECRETS:
        assert secret not in str(excinfo.value)


# ---------------------------------------------------------------- 返回体解析 / 校验


def test_parse_json_object_tolerates_fences_and_prose() -> None:
    assert parse_json_object('```json\n{"schema_version": "1.0"}\n```') == {"schema_version": "1.0"}
    assert parse_json_object('前缀 {"a": 1} 后缀') == {"a": 1}

    with pytest.raises(DeepSeekError) as excinfo:
        parse_json_object("   ")
    assert excinfo.value.kind == ERROR_BAD_RESPONSE


def test_bad_json_and_schema_violations_raise(deepseek_env) -> None:
    with pytest.raises(DeepSeekError) as excinfo:
        _client(deepseek_env, client=StubOpenAI(contents=["抱歉，我无法完成。"])).analyze_batch(
            SINGLE_MESSAGE, "只输出 JSON"
        )
    assert excinfo.value.kind == ERROR_BAD_RESPONSE

    broken = json.dumps({"schema_version": "1.0", "persons": {"A": {"tendencies": []}}})
    with pytest.raises(DeepSeekError) as excinfo2:
        _client(deepseek_env, client=StubOpenAI(contents=[broken])).analyze_batch(
            SINGLE_MESSAGE, "只输出 JSON"
        )
    assert excinfo2.value.kind == ERROR_BAD_RESPONSE
    assert "dyad" in str(excinfo2.value)


def test_validate_profile_json_rejects_out_of_range_confidence() -> None:
    data = json.loads(json.dumps(VALID_PROFILE))
    data["persons"]["A"]["tendencies"][0]["confidence"] = 1.4

    with pytest.raises(DeepSeekError) as excinfo:
        validate_profile_json(data)

    assert excinfo.value.kind == ERROR_BAD_RESPONSE
    assert "confidence" in str(excinfo.value)


def test_find_unknown_evidence_ids_detects_fabricated_ids() -> None:
    data = json.loads(json.dumps(VALID_PROFILE))
    data["persons"]["A"]["tendencies"][0]["evidence_message_ids"] = ["msg-1", "msg-999", "msg-999"]

    assert find_unknown_evidence_ids(data, {"msg-1"}) == ["msg-999"]


def test_strict_evidence_ids_rejects_fabricated_references(deepseek_env) -> None:
    fabricated = json.loads(json.dumps(VALID_PROFILE))
    fabricated["persons"]["A"]["tendencies"][0]["evidence_message_ids"] = ["msg-404"]
    # 两次调用都返回同一份「编造证据」的画像
    stub = StubOpenAI(contents=[json.dumps(fabricated, ensure_ascii=False)] * 2)
    client = _client(deepseek_env, client=stub)

    # 默认只记警告、不阻断（避免误杀「引用上一批消息」的合理情况）
    client.analyze_batch(SINGLE_MESSAGE, "只输出 JSON")

    with pytest.raises(DeepSeekError) as excinfo:
        client.analyze_batch(SINGLE_MESSAGE, "只输出 JSON", strict_evidence_ids=True)
    assert excinfo.value.kind == ERROR_BAD_RESPONSE


# ---------------------------------------------------------------- Fake 客户端（离线联调）


def test_fake_client_returns_contract_json_and_records_masked_payload() -> None:
    text = "A: 我的手机号 13800138000，你记一下。\nB: 好的，我的邮箱 lisi@example.com。"
    parsed = parse_chat(text, CONVERSATION_ID)
    assert parsed.ok

    person_roles = {
        make_person_id(CONVERSATION_ID, "A"): "A",
        make_person_id(CONVERSATION_ID, "B"): "B",
    }
    fake = FakeDeepSeekClient()
    profile = fake.analyze_batch(
        parsed.messages,
        DEFAULT_SYSTEM_PROMPT,
        conversation_id=CONVERSATION_ID,
        person_roles=person_roles,
    )

    assert fake.call_count == 1
    assert validate_profile_json(profile) == profile
    assert profile["persons"]["A"]["tendencies"][0]["evidence_message_ids"] == [
        make_message_id(CONVERSATION_ID, 0)
    ]
    assert profile["persons"]["B"]["tendencies"][0]["evidence_message_ids"] == [
        make_message_id(CONVERSATION_ID, 1)
    ]

    recorded = fake.calls[0]
    assert recorded.message_ids == [message.message_id for message in parsed.messages]
    raw_payload = json.dumps(recorded.payload, ensure_ascii=False)
    assert "13800138000" not in raw_payload
    assert "lisi@example.com" not in raw_payload
    assert recorded.payload["masking"] == {
        "policy": "alpha",
        "applied": True,
        "replaced_total": 2,
        "note": "所有 text 字段均为正则脱敏后的文本；占位符原值只存在本机，不得推测或还原。",
    }
    assert fake.last_request.conversation_id == CONVERSATION_ID
    assert fake.last_request.request_id == "fake-request-0001"


def test_message_dto_without_role_mapping_is_marked_unknown_speaker() -> None:
    """MessageDTO 没有 speaker 字段：T-004 必须传 person_roles，否则说话人只能是 `?`。"""
    parsed = parse_chat("A: 你好", CONVERSATION_ID)
    fake = FakeDeepSeekClient()

    fake.analyze_batch(parsed.messages, DEFAULT_SYSTEM_PROMPT)

    assert fake.calls[0].payload["messages"][0]["speaker"] == "?"


def test_fake_client_can_simulate_errors_and_canned_responses(deepseek_env) -> None:
    fake = FakeDeepSeekClient(error=RateLimitError("429"))
    with pytest.raises(DeepSeekError) as excinfo:
        fake.analyze_batch(SINGLE_MESSAGE, "只输出 JSON")
    assert excinfo.value.kind == ERROR_RATE_LIMIT

    fake_ok = FakeDeepSeekClient(responses=[json.dumps(VALID_PROFILE, ensure_ascii=False)])
    assert fake_ok.analyze_batch(SINGLE_MESSAGE, "只输出 JSON")["persons"]["A"]["tendencies"][0][
        "claim_key"
    ] == "A.request_style"


# ---------------------------------------------------------------- 日志隐私


def test_logs_never_contain_chat_body(deepseek_env, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    stub = StubOpenAI()
    client = _client(deepseek_env, client=stub)

    client.analyze_batch([_message("msg-1", 0, "A", SECRET_BODY)], "只输出 JSON")

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for secret in SECRETS:
        assert secret not in logged
    assert "1234" not in logged  # 连片段都不该出现
    assert "msg-1" in logged  # 允许记录的只有 message_id / 条数
    assert "messages=1" in logged
