"""T-004 分批分析管道测试：切批 / 样本门闩 / 脱敏 / 证据校验 / 落库 / 失败处理。

约定：
- 不联网：模型一律用 `llm.FakeDeepSeekClient`；数据库一律用 pytest 的 `tmp_path`，
  不触碰 `backend/data/relationinsight.db`。
- `pipeline` 以包方式导入（`backend/` 先进 `sys.path`），与 `parser` / `llm` 的导入方式一致。
- 每条用例对应 TASKS.md T-004 验收标准 ①–⑤ 中的一项（见各 docstring）。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection  # noqa: E402
from llm import FakeDeepSeekClient, mask_text  # noqa: E402
from llm.deepseek import ERROR_AUTH, ERROR_BAD_RESPONSE, DeepSeekError  # noqa: E402
from parser import import_chat  # noqa: E402
from pipeline import (  # noqa: E402
    BATCH_SIZE,
    MIN_MESSAGES_FOR_ANALYSIS,
    PROMPT_VERSION,
    QUOTE_MAX_CHARS,
    REASON_EVIDENCE_NOT_IN_BATCH,
    REASON_NO_EVIDENCE,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INSUFFICIENT_SAMPLE,
    SYSTEM_PROMPT,
    InsufficientSampleError,
    analyze_conversation,
    analyze_conversation_from_db,
    build_system_prompt,
    make_analysis_id,
    make_evidence_id,
    normalise_quote,
    plan_batches,
)

CONVERSATION_ID = "conv-pipeline-001"

PII_PHONE = "13800138000"
PII_EMAIL = "zhangsan.lee@example.com"
PII_ID_CARD = "11010119900307123X"
PII_BANK_CARD = "6222021234567890123"
PII_BODY = (
    f"我的手机号是 {PII_PHONE}，邮箱 {PII_EMAIL}，"
    f"身份证 {PII_ID_CARD}，卡号 {PII_BANK_CARD}，都发你。"
)
RAW_PII = (PII_PHONE, PII_EMAIL, PII_ID_CARD, PII_BANK_CARD)


# ---------------------------------------------------------------- 夹具 / 工具


def make_text(count: int, *, bodies: dict[int, str] | None = None) -> str:
    """生成 `count` 行合法聊天文本（A/B 交替）。"""
    overrides = bodies or {}
    lines = []
    for index in range(count):
        speaker = "A" if index % 2 == 0 else "B"
        lines.append(f"{speaker}: {overrides.get(index, f'第{index:03d}条消息')}")
    return "\n".join(lines)


def seed_conversation(
    tmp_path: Path,
    count: int,
    *,
    conversation_id: str = CONVERSATION_ID,
    bodies: dict[int, str] | None = None,
) -> Path:
    """把 `count` 条消息经 T-002 解析器写入临时库，返回库路径。"""
    db_path = tmp_path / "relationinsight.db"
    result = import_chat(make_text(count, bodies=bodies), conversation_id, db_path=db_path)
    assert result.inserted_count == count, f"夹具写入失败：{result}"
    return db_path


def table_rows(db_path: Path, table: str, order_by: str = "rowid") -> list[sqlite3.Row]:
    conn = get_connection(db_path)
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    finally:
        conn.close()


def message_ids(db_path: Path, conversation_id: str = CONVERSATION_ID) -> list[str]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT message_id FROM messages WHERE conversation_id = ? ORDER BY seq",
            (conversation_id,),
        ).fetchall()
    finally:
        conn.close()
    return [row["message_id"] for row in rows]


def make_profile(
    *,
    a_evidence: list[str] | None = None,
    b_evidence: list[str] | None = None,
    dyad_evidence: list[str] | None = None,
    a_confidence: float = 0.6,
    sample_size: int | None = None,
) -> dict:
    """手工构造一份符合 ARCHITECTURE.md §5 的画像（便于精确控制证据 ID）。"""

    def tendency(prefix: str, evidence: list[str]) -> dict:
        return {
            "claim_key": f"{prefix}.style",
            "statement": f"{prefix} 在本批中呈现出可复核的互动模式。",
            "confidence": 0.6,
            "sample_size": len(evidence) if sample_size is None else sample_size,
            "evidence_message_ids": evidence,
        }

    a_ids = list(a_evidence or [])
    b_ids = list(b_evidence or [])
    dyad_ids = list(dyad_evidence or [])

    persons: dict = {
        "A": {"tendencies": [tendency("A", a_ids)] if a_ids else []},
        "B": {"tendencies": [tendency("B", b_ids)] if b_ids else []},
    }
    if persons["A"]["tendencies"]:
        persons["A"]["tendencies"][0]["confidence"] = a_confidence

    return {
        "schema_version": "1.0",
        "persons": persons,
        "dyad": {"tendencies": [tendency("dyad", dyad_ids)] if dyad_ids else []},
        "warnings": [],
    }


# ---------------------------------------------------------------- 验收 ① 切批


def test_plan_batches_splits_100_messages_into_two_full_batches(tmp_path):
    """验收 ①：100 条 → 恰好 2 个完整批，边界与 seq 区间正确，无余数批。"""
    db_path = seed_conversation(tmp_path, 100)
    from pipeline import load_messages

    messages = load_messages(CONVERSATION_ID, db_path=db_path)

    plan = plan_batches(messages)

    assert plan.total_messages == 100
    assert plan.batch_count == 2
    assert plan.full_batch_count == 2
    assert plan.remainder_batch is None
    assert plan.remainder_size == 0
    assert [b.size for b in plan.batches] == [BATCH_SIZE, BATCH_SIZE]
    assert [b.batch_index for b in plan.batches] == [0, 1]
    assert all(b.is_remainder is False for b in plan.batches)

    first, second = plan.batches
    assert (first.seq_from, first.seq_to) == (0, 49)
    assert (second.seq_from, second.seq_to) == (50, 99)
    assert first.message_id_from == messages[0].message_id
    assert first.message_id_to == messages[49].message_id
    assert second.message_id_to == messages[99].message_id
    assert plan.message_ids == [m.message_id for m in messages]  # 不重不漏


def test_plan_batches_keeps_remainder_as_its_own_batch(tmp_path):
    """验收 ①（余数规则）：120 条 → 50 + 50 + 20；余数批独立成批并记录样本量。"""
    db_path = seed_conversation(tmp_path, 120)
    from pipeline import load_messages

    plan = plan_batches(load_messages(CONVERSATION_ID, db_path=db_path))

    assert plan.batch_count == 3
    assert plan.full_batch_count == 2
    assert [b.size for b in plan.batches] == [50, 50, 20]
    remainder = plan.remainder_batch
    assert remainder is not None
    assert remainder.batch_index == 2
    assert remainder.is_remainder is True
    assert remainder.sample_size == 20
    assert (remainder.seq_from, remainder.seq_to) == (100, 119)
    assert "余数批（20 条" in plan.describe()
    assert sum(b.size for b in plan.batches) == 120  # 余数不丢弃、不合并


def test_plan_batches_51_messages_gives_one_full_batch_plus_remainder(tmp_path):
    """验收 ①：51 条 → 1 完整批 + 1 条余数批（余数为 1 也照做）。"""
    db_path = seed_conversation(tmp_path, 51)
    from pipeline import load_messages

    plan = plan_batches(load_messages(CONVERSATION_ID, db_path=db_path))

    assert [b.size for b in plan.batches] == [50, 1]
    assert plan.batches[1].is_remainder is True
    assert plan.batches[1].sample_size == 1


def test_plan_batches_rejects_non_ascending_seq(tmp_path):
    """切批边界依赖导入顺序：seq 乱序必须早失败，不能静默切错批。"""
    from pipeline import load_messages

    messages = list(reversed(load_messages(CONVERSATION_ID, db_path=seed_conversation(tmp_path, 25))))
    with pytest.raises(ValueError, match="seq 升序"):
        plan_batches(messages)


def test_plan_batches_rejects_bad_arguments(tmp_path):
    """参数校验：batch_size / min_messages / messages 类型。"""
    from pipeline import load_messages

    messages = load_messages(CONVERSATION_ID, db_path=seed_conversation(tmp_path, 25))

    with pytest.raises(ValueError, match="batch_size"):
        plan_batches(messages, batch_size=0)
    with pytest.raises(ValueError, match="min_messages"):
        plan_batches(messages, min_messages=0)
    with pytest.raises(ValueError, match="消息序列"):
        plan_batches("A: 不是列表")


# ---------------------------------------------------------------- 验收 ④ 样本门闩


@pytest.mark.parametrize("count", [0, 1, 19])
def test_plan_batches_gate_rejects_below_minimum(tmp_path, count):
    """验收 ④：< 20 条（含 0 条）抛 InsufficientSampleError，文案含「样本不足」。"""
    from pipeline import load_messages

    if count == 0:
        messages: list = []
    else:
        messages = load_messages(CONVERSATION_ID, db_path=seed_conversation(tmp_path, count))

    with pytest.raises(InsufficientSampleError) as excinfo:
        plan_batches(messages)

    assert "样本不足" in str(excinfo.value)
    assert excinfo.value.message_count == count
    assert excinfo.value.minimum == MIN_MESSAGES_FOR_ANALYSIS


def test_plan_batches_accepts_exactly_minimum(tmp_path):
    """边界：恰好 20 条应通过门闩（>= 而非 >）。"""
    from pipeline import load_messages

    plan = plan_batches(load_messages(CONVERSATION_ID, db_path=seed_conversation(tmp_path, 20)))
    assert plan.total_messages == 20
    assert plan.batch_count == 1


def test_below_minimum_returns_report_and_never_calls_model(tmp_path):
    """验收 ④：19 条 → status=insufficient_sample，不调模型、不写 analyses。"""
    db_path = seed_conversation(tmp_path, 19)
    client = FakeDeepSeekClient()

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_INSUFFICIENT_SAMPLE
    assert report.ok is False
    assert "样本不足" in report.message
    assert report.total_messages == 19
    assert client.call_count == 0
    assert table_rows(db_path, "analyses") == []
    assert table_rows(db_path, "evidence") == []
    assert report.warnings and "19" in report.warnings[0]


# ---------------------------------------------------------------- 验收 ① + ② 落库主路径


def test_100_messages_writes_two_analyses_rows_with_valid_evidence(tmp_path):
    """验收 ①②：100 条 → 2 行 analyses、evidence 齐全且 ID 在 messages 表内存在。"""
    db_path = seed_conversation(tmp_path, 100)
    client = FakeDeepSeekClient()

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_COMPLETED
    assert report.ok is True
    assert report.analyses_written == 2
    assert report.batch_count == 2
    assert client.call_count == 2
    assert report.dropped_count == 0

    analyses = table_rows(db_path, "analyses", order_by="batch_index")
    assert [row["batch_index"] for row in analyses] == [0, 1]
    assert [row["seq_from"] for row in analyses] == [0, 50]
    assert [row["seq_to"] for row in analyses] == [49, 99]
    assert all(row["model"] == "deepseek-chat" for row in analyses)
    assert all(row["prompt_version"] == PROMPT_VERSION for row in analyses)
    assert all(row["conversation_id"] == CONVERSATION_ID for row in analyses)

    known = set(message_ids(db_path))
    evidence = table_rows(db_path, "evidence")
    assert len(evidence) == report.evidence_written > 0
    assert all(row["message_id"] in known for row in evidence)          # 验收 ②
    assert all(row["analysis_id"] in {a["id"] for a in analyses} for row in evidence)
    assert all(row["quote"] for row in evidence)                        # 非空摘录


def test_remainder_batch_is_analysed_and_sample_size_recorded(tmp_path):
    """验收 ① 余数规则：120 条 → 3 次调用 / 3 行 analyses，末批样本量 20 写入元数据。"""
    db_path = seed_conversation(tmp_path, 120)
    client = FakeDeepSeekClient()

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_COMPLETED
    assert client.call_count == 3
    analyses = table_rows(db_path, "analyses", order_by="batch_index")
    assert [row["batch_index"] for row in analyses] == [0, 1, 2]

    remainder_row = analyses[2]
    assert (remainder_row["seq_from"], remainder_row["seq_to"]) == (100, 119)
    payload = json.loads(remainder_row["result_json"])
    assert any("sample_size=20" in w for w in payload["warnings"])      # 样本量进该批元数据
    assert len(client.calls[2].message_ids) == 20


def test_evidence_ids_are_checked_against_messages_table(tmp_path):
    """验收 ①②：模型编造的 ID 不入库；同一批次里真实存在的 ID 照常入库。"""
    db_path = seed_conversation(tmp_path, 24)
    ids = message_ids(db_path)
    fabricated = str(uuid.uuid5(uuid.NAMESPACE_URL, "fabricated-id"))
    client = FakeDeepSeekClient(
        responses=[make_profile(a_evidence=[ids[0], fabricated], b_evidence=[ids[1]])]
    )

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_COMPLETED
    stored = {row["message_id"] for row in table_rows(db_path, "evidence")}
    assert stored == {ids[0], ids[1]}
    assert fabricated not in stored
    assert report.dropped_count == 1
    assert any(REASON_EVIDENCE_NOT_IN_BATCH in d.reason for d in report.batch_outcomes[0].dropped)
    assert any(REASON_EVIDENCE_NOT_IN_BATCH in w for w in json.loads(
        table_rows(db_path, "analyses")[0]["result_json"]
    )["warnings"])


def test_evidence_id_from_another_conversation_is_rejected(tmp_path):
    """验收 ②：证据 ID 属于别的会话（不在本批）→ 丢弃，不得跨批次引用。"""
    db_path = seed_conversation(tmp_path, 22)
    other_db = tmp_path / "other.db"
    import_chat(make_text(4), "other-conv", db_path=other_db)
    foreign_ids = message_ids(other_db, "other-conv")
    ids = message_ids(db_path)

    client = FakeDeepSeekClient(
        responses=[make_profile(a_evidence=[ids[0], foreign_ids[0]], b_evidence=[ids[1]])]
    )
    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    stored = {row["message_id"] for row in table_rows(db_path, "evidence")}
    assert foreign_ids[0] not in stored
    assert stored == {ids[0], ids[1]}
    assert report.dropped_count == 1


def test_tendency_without_evidence_is_not_persisted(tmp_path):
    """验收 ③：无证据的结论不入库，并在报告与 result_json.warnings 中留痕。"""
    db_path = seed_conversation(tmp_path, 21)
    ids = message_ids(db_path)
    profile = make_profile(b_evidence=[ids[1]])
    profile["persons"]["A"]["tendencies"] = [
        {
            "claim_key": "A.unsupported",
            "statement": "这条结论故意不给证据。",
            "confidence": 0.9,
            "sample_size": 10,
            "evidence_message_ids": [],
        }
    ]
    client = FakeDeepSeekClient(responses=[profile])

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_COMPLETED
    evidence = table_rows(db_path, "evidence")
    assert {row["claim_key"] for row in evidence} == {"B.style"}
    assert report.dropped_count == 1
    dropped = report.batch_outcomes[0].dropped[0]
    assert dropped.claim_key == "A.unsupported"
    assert dropped.reason == REASON_NO_EVIDENCE

    stored = json.loads(table_rows(db_path, "analyses")[0]["result_json"])
    assert stored["persons"]["A"]["tendencies"] == []           # 结论未入库
    assert any(REASON_NO_EVIDENCE in w for w in stored["warnings"])


def test_tendency_whose_evidence_is_all_fabricated_is_dropped(tmp_path):
    """验收 ②③ 组合：证据全被剔除 → 结论本身也不入库。"""
    db_path = seed_conversation(tmp_path, 20)
    ids = message_ids(db_path)
    bogus = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"bogus-{i}")) for i in range(2)]
    client = FakeDeepSeekClient(responses=[make_profile(a_evidence=bogus, b_evidence=[ids[0]])])

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    stored = json.loads(table_rows(db_path, "analyses")[0]["result_json"])
    assert stored["persons"]["A"]["tendencies"] == []
    assert {row["claim_key"] for row in table_rows(db_path, "evidence")} == {"B.style"}
    assert report.dropped_count == 3  # 2 条越界引用 + 1 次「无证据结论」


def test_dyad_tendency_keeps_evidence_speaker_role(tmp_path):
    """speaker_role 恒定记录该条证据消息的说话人；dyad 结论不置 NULL。

    ARCHITECTURE.md §4.5 只约束该列为 A/B，未规定 dyad 结论必须为 NULL。
    取「证据消息的真实说话人」这一读法：UI 点开证据时可直接显示是谁说的。
    """
    db_path = seed_conversation(tmp_path, 21)
    ids = message_ids(db_path)
    client = FakeDeepSeekClient(
        responses=[make_profile(a_evidence=[ids[0]], dyad_evidence=[ids[1]])]
    )

    analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    by_claim = {row["claim_key"]: row for row in table_rows(db_path, "evidence")}
    assert by_claim["A.style"]["speaker_role"] == "A"  # ids[0] 由 A 发出
    assert by_claim["dyad.style"]["speaker_role"] == "B"  # 证据消息 ids[1] 由 B 发出


# ---------------------------------------------------------------- 验收 ⑤ 脱敏


def test_raw_pii_never_reaches_the_model_and_quote_is_masked(tmp_path):
    """验收 ⑤：调用前脱敏；库内 body 仍是原文，evidence.quote 是脱敏后文本。"""
    db_path = seed_conversation(tmp_path, 22, bodies={0: PII_BODY})
    client = FakeDeepSeekClient()

    analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert client.call_count == 1
    sent_texts = client.calls[0].texts
    sent_blob = "\n".join(sent_texts)
    for raw in RAW_PII:
        assert raw not in sent_blob, f"原文 {raw} 被发到模型"
    assert "[手机号]" in sent_blob and "[邮箱]" in sent_blob
    assert "[身份证号]" in sent_blob and "[银行卡号]" in sent_blob

    # 本地仍存原文（策略 α：本地不脱敏）
    conn = get_connection(db_path)
    try:
        body = conn.execute("SELECT body FROM messages WHERE seq = 0").fetchone()["body"]
    finally:
        conn.close()
    assert body == PII_BODY

    # 证据摘录必须是脱敏后的文本
    pii_message_id = message_ids(db_path)[0]
    quotes = [row["quote"] for row in table_rows(db_path, "evidence") if row["message_id"] == pii_message_id]
    assert quotes, "应有一条证据指向含 PII 的消息"
    for quote in quotes:
        for raw in RAW_PII:
            assert raw not in quote
        assert quote == normalise_quote(mask_text(PII_BODY))


def test_evidence_quote_is_prefix_of_masked_text_sent_to_model(tmp_path):
    """ARCHITECTURE.md §4.5：quote 必须能对应到「发出去的那份脱敏文本」。"""
    db_path = seed_conversation(tmp_path, 20, bodies={0: PII_BODY, 1: "第二" * (QUOTE_MAX_CHARS + 40)})
    client = FakeDeepSeekClient()

    analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    sent_by_id = dict(zip(client.calls[0].message_ids, client.calls[0].texts))
    for row in table_rows(db_path, "evidence"):
        masked = sent_by_id[row["message_id"]]
        assert row["quote"] == normalise_quote(masked)
        assert masked.startswith(row["quote"])
        assert len(row["quote"]) <= QUOTE_MAX_CHARS


def test_normalise_quote_collapses_whitespace_and_truncates():
    assert normalise_quote("  a\t b\n\nc  ") == "a b c"
    long_text = "x" * (QUOTE_MAX_CHARS + 10)
    assert len(normalise_quote(long_text)) == QUOTE_MAX_CHARS
    with pytest.raises(TypeError):
        normalise_quote(None)


def test_client_receives_original_bodies_and_masks_them_itself(tmp_path):
    """验收 ⑤ 的边界：管道交给客户端的是原文，脱敏发生在客户端内部（T-003）。"""
    db_path = seed_conversation(tmp_path, 20, bodies={0: PII_BODY})
    client = FakeDeepSeekClient()

    analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert client.calls[0].texts[0] == mask_text(PII_BODY)
    assert client.calls[0].texts[0] != PII_BODY


def test_logs_never_contain_chat_bodies(tmp_path, caplog):
    """PRIVACY.md：日志只允许出现会话 ID / message_id / 条数，不得出现正文。"""
    db_path = seed_conversation(tmp_path, 20, bodies={0: PII_BODY, 3: "不可外泄的私密句子"})
    client = FakeDeepSeekClient()

    with caplog.at_level(logging.DEBUG):
        analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    blob = "\n".join(record.getMessage() for record in caplog.records)
    assert PII_BODY not in blob
    assert "不可外泄的私密句子" not in blob
    for raw in RAW_PII:
        assert raw not in blob
    assert CONVERSATION_ID in blob  # 该记的还在


# ---------------------------------------------------------------- 提示词


def test_system_prompt_carries_every_required_prohibition():
    """系统提示词必须写明：禁止诊断/人格标签/读心/操控建议 + 证据绑定 + 严格 JSON。"""
    for word in ("禁止", "诊断", "人格", "读心", "操控"):
        assert word in SYSTEM_PROMPT, f"提示词缺少「{word}」"
    assert "evidence_message_ids" in SYSTEM_PROMPT
    assert "message_id" in SYSTEM_PROMPT
    assert "禁止编造证据" in SYSTEM_PROMPT
    assert "严格 JSON" in SYSTEM_PROMPT
    assert '"schema_version"' in SYSTEM_PROMPT and '"dyad"' in SYSTEM_PROMPT
    for diagnostic in ("自恋型", "NPD", "依恋"):
        assert diagnostic in SYSTEM_PROMPT  # 明确点名禁止的诊断词
    assert PROMPT_VERSION  # 版本号会写进 analyses.prompt_version


def test_build_system_prompt_appends_extra_rules():
    default = build_system_prompt()
    assert default == SYSTEM_PROMPT
    extended = build_system_prompt("本批共 20 条消息。")
    assert extended.startswith(SYSTEM_PROMPT)
    assert "本批共 20 条消息。" in extended
    with pytest.raises(TypeError):
        build_system_prompt(123)


def test_pipeline_uses_our_system_prompt(tmp_path):
    """管道必须把 pipeline.prompt 的提示词传给客户端（可覆盖）。"""
    db_path = seed_conversation(tmp_path, 20)
    client = FakeDeepSeekClient()

    analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert client.calls[0].system_prompt == SYSTEM_PROMPT

    custom = FakeDeepSeekClient()
    report = analyze_conversation_from_db(
        CONVERSATION_ID, custom, db_path=db_path, system_prompt="自定义提示词"
    )
    assert report.status == STATUS_COMPLETED  # 已存在的批次被跳过，不会重调
    assert custom.call_count == 0


# ---------------------------------------------------------------- 说话人映射


def test_speaker_roles_come_from_persons_table(tmp_path):
    """T-004 必须传 person_roles，否则 MessageDTO 无法定说话人（只会得到 '?'）。"""
    db_path = seed_conversation(tmp_path, 20)
    client = FakeDeepSeekClient()

    analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    speakers = {item["speaker"] for item in client.calls[0].payload["messages"]}
    assert speakers == {"A", "B"}
    assert "?" not in speakers


def test_explicit_person_roles_override_db_lookup(tmp_path):
    """显式传入 person_roles 时以调用方为准（且不会因缺 persons 行而失败）。"""
    db_path = seed_conversation(tmp_path, 20)
    from pipeline import load_messages

    messages = load_messages(CONVERSATION_ID, db_path=db_path)
    swapped = {m.person_id: ("B" if m.seq % 2 == 0 else "A") for m in messages}
    client = FakeDeepSeekClient()

    report = analyze_conversation(
        messages, client, conversation_id=CONVERSATION_ID, db_path=db_path, person_roles=swapped
    )

    assert report.status == STATUS_COMPLETED
    first = client.calls[0].payload["messages"][0]
    assert first["speaker"] == "B"  # seq=0 本来解析为 A，被覆盖为 B


# ---------------------------------------------------------------- 幂等 / 失败 / 结构校验


def test_second_run_skips_existing_batches_without_calling_model(tmp_path):
    """重复运行不覆盖旧行、不重复烧额度：已存在的批次直接跳过。"""
    db_path = seed_conversation(tmp_path, 120)
    first_client = FakeDeepSeekClient()
    first = analyze_conversation_from_db(CONVERSATION_ID, first_client, db_path=db_path)

    second_client = FakeDeepSeekClient()
    second = analyze_conversation_from_db(CONVERSATION_ID, second_client, db_path=db_path)

    assert first.analyses_written == 3
    assert second.status == STATUS_COMPLETED
    assert second.analyses_written == 0
    assert second.batches_skipped == 3
    assert second_client.call_count == 0
    assert len(table_rows(db_path, "analyses")) == 3
    assert len(table_rows(db_path, "evidence")) == first.evidence_written


def test_analysis_and_evidence_ids_are_deterministic():
    assert make_analysis_id("conv-1", 0) == make_analysis_id("conv-1", 0)
    assert make_analysis_id("conv-1", 0) != make_analysis_id("conv-1", 1)
    assert make_analysis_id("conv-1", 0) == str(
        uuid.uuid5(uuid.NAMESPACE_URL, "analysis:conv-1:0")
    )
    evidence_id = make_evidence_id("analysis-x", "A.style", "msg-1")
    assert evidence_id == str(uuid.uuid5(uuid.NAMESPACE_URL, "evidence:analysis-x:A.style:msg-1"))


def test_deepseek_error_stops_pipeline_and_reports_failure(tmp_path):
    """统一错误处理：401 等错误 → status=failed、停止后续批次、不写任何行。"""
    db_path = seed_conversation(tmp_path, 120)
    client = FakeDeepSeekClient(
        error=DeepSeekError(ERROR_AUTH, "鉴权失败：请检查环境变量 DEEPSEEK_API_KEY", status_code=401)
    )

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_FAILED
    assert report.ok is False
    assert report.analyses_written == 0
    assert report.evidence_written == 0
    assert client.call_count == 1                      # 第一批就失败，不再打第二批
    assert table_rows(db_path, "analyses") == []
    assert table_rows(db_path, "evidence") == []
    assert report.failures and "auth_error" in report.failures[0]
    assert report.batch_outcomes[0].status == "failed"
    assert report.batch_outcomes[0].error_kind == "auth_error"
    assert "鉴权失败" in report.message


def test_error_report_never_contains_chat_body(tmp_path):
    """错误路径也不得夹带正文：失败摘要只保留错误类型与状态码。

    说明：本用例依赖 T-003 的契约「`DeepSeekError.detail` 不含聊天原文」；
    管道不额外清洗客户端异常文本，这一点已记入 HANDOFF 的遗留问题。
    """
    db_path = seed_conversation(tmp_path, 20, bodies={0: PII_BODY})
    client = FakeDeepSeekClient(
        error=DeepSeekError(ERROR_AUTH, "鉴权失败：请检查环境变量 DEEPSEEK_API_KEY", status_code=401)
    )

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_FAILED
    blob = "\n".join([report.message, *report.failures, *report.warnings])
    assert PII_BODY not in blob
    for raw in RAW_PII:
        assert raw not in blob


def test_invalid_model_json_is_reported_as_failed_batch(tmp_path):
    """模型返回结构不合法 → DeepSeekError(bad_response) 被管道接住，不会崩。"""
    db_path = seed_conversation(tmp_path, 20)
    # 缺 dyad / warnings：analyze_batch 的 §5 结构校验会判为 bad_response（校验在管道之前）
    client = FakeDeepSeekClient(
        responses=[{"schema_version": "1.0", "persons": {"A": {"tendencies": []}, "B": {"tendencies": []}}}]
    )

    report = analyze_conversation_from_db(CONVERSATION_ID, client, db_path=db_path)

    assert report.status == STATUS_FAILED
    assert report.batch_outcomes[0].error_kind == ERROR_BAD_RESPONSE
    assert table_rows(db_path, "analyses") == []


def test_empty_message_list_is_insufficient_sample(tmp_path):
    """空输入走同一条门闩：不做任何写库动作。"""
    db_path = tmp_path / "empty.db"
    client = FakeDeepSeekClient()

    report = analyze_conversation([], client, conversation_id=CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_INSUFFICIENT_SAMPLE
    assert report.total_messages == 0
    assert client.call_count == 0


def test_load_messages_returns_dtos_in_seq_order(tmp_path):
    """`load_messages()` 按 seq 升序返回 MessageDTO，且 body 为原文。"""
    from pipeline import load_messages

    db_path = seed_conversation(tmp_path, 21, bodies={0: PII_BODY})
    messages = load_messages(CONVERSATION_ID, db_path=db_path)

    assert [m.seq for m in messages] == list(range(21))
    assert messages[0].body == PII_BODY
    assert messages[0].conversation_id == CONVERSATION_ID
    assert all(m.person_id for m in messages)
