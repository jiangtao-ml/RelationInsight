"""T-002 文本解析器测试：正常文本 / 含错误行文本 / 冻结 message_id 算法 / 写库与去重。

约定：
- 不联网；数据库一律用 pytest 的 `tmp_path`，不触碰 `backend/data/`。
- `parser.py` 以顶层模块方式 `from db import ...`（与 `backend/main.py` 一致），
  因此测试需先把 `backend/` 放进 `sys.path`。
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from parser import (  # noqa: E402
    REASON_BAD_SPEAKER,
    REASON_EMPTY_BODY,
    REASON_NO_COLON,
    REASON_NO_SPACE,
    STATUS_INSERTED,
    STATUS_NOTHING_TO_IMPORT,
    STATUS_REJECTED_CONFLICT,
    MessageDTO,
    import_chat,
    insert_messages,
    make_message_id,
    make_person_id,
    parse_chat,
)

CONVERSATION_ID = "conv-test-001"

NORMAL_TEXT = "\n".join(
    [
        "A: 今天有空聊聊吗？",
        "",
        "B: 有，你说。",
        "A: 我最近在想周末的安排。",
        "B: 好吧，那周六下午两点，老地方见。",
    ]
)

NORMAL_BODIES = [
    "今天有空聊聊吗？",
    "有，你说。",
    "我最近在想周末的安排。",
    "好吧，那周六下午两点，老地方见。",
]

ERROR_TEXT = "\n".join(
    [
        "A: 第一条正常",
        "a: 小写说话人不接受",
        "这条没有冒号前缀",
        "A:缺空格",
        "A: ",
        "   ",
        "A：全角冒号不支持",
        "B: 尾部保留  空格：还有：冒号",
    ]
)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """每个用例一个独立临时库：互不污染，也不写进 backend/data/。"""
    return tmp_path / "relationinsight_test.db"


def _count_rows(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_parse_normal_text_builds_messages_with_frozen_message_id() -> None:
    """夹具 1：正常文本 → MessageDTO 列表 + 冻结的 message_id 算法。"""
    result = parse_chat(NORMAL_TEXT, CONVERSATION_ID)

    assert result.errors == []
    assert result.ok is True
    assert result.blank_lines_skipped == 1

    assert [m.seq for m in result.messages] == [0, 1, 2, 3]
    assert [m.source_line for m in result.messages] == [1, 3, 4, 5]
    assert [m.body for m in result.messages] == NORMAL_BODIES
    assert all(m.conversation_id == CONVERSATION_ID for m in result.messages)

    # ARCHITECTURE.md §6（2026-09-22 冻结，方案 A）：
    # message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")，seq 从 0 开始
    for message in result.messages:
        expected = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{CONVERSATION_ID}:{message.seq}"))
        assert message.message_id == expected
        assert message.message_id == make_message_id(CONVERSATION_ID, message.seq)

    assert len({m.message_id for m in result.messages}) == 4  # 全局唯一
    assert result.messages[0].person_id == make_person_id(CONVERSATION_ID, "A")
    assert result.messages[1].person_id == make_person_id(CONVERSATION_ID, "B")
    assert result.messages[0].person_id != result.messages[1].person_id


def test_parse_reports_error_lines_and_still_keeps_valid_ones() -> None:
    """夹具 2：含错误行的文本 → 错误列表（行号 + 原因），且成功行照常解析。"""
    result = parse_chat(ERROR_TEXT, CONVERSATION_ID)

    assert [(e.line_number, e.reason) for e in result.errors] == [
        (2, REASON_BAD_SPEAKER),
        (3, REASON_NO_COLON),
        (4, REASON_NO_SPACE),
        (5, REASON_EMPTY_BODY),
        (7, REASON_NO_COLON),
    ]
    assert result.errors[1].raw_line == "这条没有冒号前缀"
    assert result.ok is False
    assert result.blank_lines_skipped == 1

    # 错误行不阻断可解析行；seq 只对成功行递增，且仍从 0 开始
    assert [m.seq for m in result.messages] == [0, 1]
    assert [m.source_line for m in result.messages] == [1, 8]
    assert [m.body for m in result.messages] == ["第一条正常", "尾部保留  空格：还有：冒号"]


def test_parse_chat_rejects_bad_arguments() -> None:
    with pytest.raises(TypeError):
        parse_chat(None, CONVERSATION_ID)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_chat("A: 你好", "")
    with pytest.raises(ValueError):
        make_person_id(CONVERSATION_ID, "C")


def test_make_message_id_is_deterministic_and_conversation_scoped() -> None:
    cid = "会话 with 中文 + spaces"

    assert make_message_id(cid, 0) == str(uuid.uuid5(uuid.NAMESPACE_URL, f"{cid}:0"))
    assert make_message_id(cid, 0) == make_message_id(cid, 0)  # 可复现，无随机成分
    assert make_message_id(cid, 0) != make_message_id(cid, 1)  # seq 敏感
    assert make_message_id(cid, 0) != make_message_id(f"{cid} ", 0)  # conversation_id 不 strip
    assert make_message_id(cid, 0) != make_message_id(f"{cid}x", 0)


def test_blank_lines_are_skipped_and_counted() -> None:
    result = parse_chat("\n\n   \nA: 只有一条\n\n", CONVERSATION_ID)

    assert result.blank_lines_skipped == 4
    assert result.errors == []
    assert len(result.messages) == 1
    assert result.messages[0].source_line == 4


def test_import_chat_writes_messages_and_persons(db_path: Path) -> None:
    """service 函数：解析结果落到 messages / persons 表。"""
    report = import_chat(NORMAL_TEXT, CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_INSERTED
    assert report.rejected is False
    assert report.inserted_count == 4
    assert report.conflicts == []
    assert report.errors == []
    assert report.blank_lines_skipped == 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT message_id, conversation_id, person_id, seq, body, source_line"
            " FROM messages ORDER BY seq"
        ).fetchall()
        assert len(rows) == 4
        assert [r["seq"] for r in rows] == [0, 1, 2, 3]
        assert [r["body"] for r in rows] == NORMAL_BODIES
        assert [r["source_line"] for r in rows] == [1, 3, 4, 5]
        assert all(r["conversation_id"] == CONVERSATION_ID for r in rows)
        assert rows[0]["message_id"] == make_message_id(CONVERSATION_ID, 0)

        persons = conn.execute("SELECT id, role FROM persons ORDER BY role").fetchall()
        assert [p["role"] for p in persons] == ["A", "B"]
        assert {p["id"] for p in persons} == {m.person_id for m in report.messages}

        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()

    # 同一文本、不同 conversation_id → 不同 message_id，可共存
    other = import_chat(NORMAL_TEXT, "conv-test-002", db_path=db_path)
    assert other.status == STATUS_INSERTED
    assert _count_rows(db_path, "messages") == 8
    assert _count_rows(db_path, "persons") == 4


def test_duplicate_import_rejects_whole_batch_and_lists_conflicts(db_path: Path) -> None:
    """重复导入：拒绝整批，并在错误报告中列出冲突 ID 与来源行号。"""
    first = import_chat(NORMAL_TEXT, CONVERSATION_ID, db_path=db_path)
    assert first.status == STATUS_INSERTED

    second = import_chat(NORMAL_TEXT, CONVERSATION_ID, db_path=db_path)

    assert second.status == STATUS_REJECTED_CONFLICT
    assert second.rejected is True
    assert second.inserted_count == 0
    assert [c.message_id for c in second.conflicts] == [m.message_id for m in first.messages]
    assert [c.source_line for c in second.conflicts] == [1, 3, 4, 5]

    # 整批拒绝：库内行数不变（不做部分导入、不静默跳过）
    assert _count_rows(db_path, "messages") == 4
    assert _count_rows(db_path, "persons") == 2


def test_insert_messages_rejects_batch_when_only_some_ids_conflict(db_path: Path) -> None:
    """只要批内有一个 ID 已存在，整批都不写入——不冲突的那条也不能落库。"""
    import_chat(NORMAL_TEXT, CONVERSATION_ID, db_path=db_path)  # seq 0..3 已入库

    conflicting = MessageDTO(
        message_id=make_message_id(CONVERSATION_ID, 0),
        conversation_id=CONVERSATION_ID,
        person_id=make_person_id(CONVERSATION_ID, "A"),
        seq=0,
        body="与库内 seq=0 冲突",
        source_line=1,
    )
    fresh = MessageDTO(
        message_id=make_message_id(CONVERSATION_ID, 99),
        conversation_id=CONVERSATION_ID,
        person_id=make_person_id(CONVERSATION_ID, "B"),
        seq=99,
        body="这条本身不冲突",
        source_line=2,
    )

    report = insert_messages([conflicting, fresh], db_path=db_path)

    assert report.rejected is True
    assert report.inserted_count == 0
    assert [c.message_id for c in report.conflicts] == [conflicting.message_id]
    assert [c.source_line for c in report.conflicts] == [1]
    assert _count_rows(db_path, "messages") == 4


def test_insert_messages_detects_duplicate_inside_one_batch(db_path: Path) -> None:
    duplicated = MessageDTO(
        message_id=make_message_id(CONVERSATION_ID, 7),
        conversation_id=CONVERSATION_ID,
        person_id=make_person_id(CONVERSATION_ID, "A"),
        seq=7,
        body="同一批里出现两次",
        source_line=1,
    )

    report = insert_messages([duplicated, replace(duplicated, source_line=2)], db_path=db_path)

    assert report.rejected is True
    assert report.inserted_count == 0
    assert [c.source_line for c in report.conflicts] == [1, 2]
    assert _count_rows(db_path, "messages") == 0


def test_import_chat_without_valid_lines_inserts_nothing(db_path: Path) -> None:
    report = import_chat("hello world\n还是不合格式的一行", CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_NOTHING_TO_IMPORT
    assert report.inserted_count == 0
    assert report.messages == []
    assert len(report.errors) == 2
    assert not db_path.exists()  # 没有任何可写入内容时，不创建库文件


def test_insert_messages_with_empty_batch_is_a_noop(db_path: Path) -> None:
    report = insert_messages([], db_path=db_path)

    assert report.status == STATUS_NOTHING_TO_IMPORT
    assert report.inserted_count == 0
    assert not db_path.exists()
