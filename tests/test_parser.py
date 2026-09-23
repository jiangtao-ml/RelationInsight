"""T-002 文本解析器测试：宽容标记 / 连续发言合并 / 未标记兜底 / 冻结 message_id 算法 / 写库与去重。

2026-09-23 改版（`ARCHITECTURE.md` §6「放宽冻结」）新增覆盖：
- 多格式说话人标记：`A:` / `a:` / `张三:` / `张三：` / `我:` / `你:` / `[张三]` / `【张三】`，中英文冒号都接受；
- 冒号后 0 个 / 1 个 / 多个空格；同一段文本里中英文冒号混用；
- 连续发言默认合并（`merge_consecutive=True`）：`seq` 只 +1、`body` 用空格连接、`source_lines` 保留原始行号；
- 未标记行（无标记 / 双人之外的第三人 / 纯数字时间前缀）进 `ParseResult.unmarked`：**不报错、不阻断导入**。

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
    REASON_EMPTY_BODY,
    REASON_UNMARKED_EXTRA_SPEAKER,
    REASON_UNMARKED_NO_MARKER,
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


def _bulk_text(count: int, *, start: int = 0) -> str:
    """生成 count 行合法的 `A: …` / `B: …` 文本（A/B 交替，故不会触发合并）。"""
    return "\n".join(
        f"{'A' if (start + index) % 2 == 0 else 'B'}: 第{start + index + 1}条消息"
        for index in range(count)
    )


def _parse(lines: list[str], **kwargs):
    """把若干行拼成一段文本再解析（默认开启连续发言合并）。"""
    return parse_chat("\n".join(lines), CONVERSATION_ID, **kwargs)


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


def _bodies(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [row[0] for row in conn.execute("SELECT body FROM messages ORDER BY seq")]
    finally:
        conn.close()


# ---------------------------------------------------------------- 夹具 1：正常文本


def test_parse_normal_text_builds_messages_with_frozen_message_id() -> None:
    """正常文本 → MessageDTO 列表 + 冻结的 message_id 算法。"""
    result = parse_chat(NORMAL_TEXT, CONVERSATION_ID)

    assert result.errors == []
    assert result.ok is True
    assert result.unmarked == []
    assert result.blank_lines_skipped == 1

    assert [m.seq for m in result.messages] == [0, 1, 2, 3]
    assert [m.source_line for m in result.messages] == [1, 3, 4, 5]
    assert [m.source_lines for m in result.messages] == [[1], [3], [4], [5]]
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


# ---------------------------------------------------------------- 决策 1：多格式标记


MARKER_CASES: list[tuple[str, str]] = [
    ("A: 你好", "B: 在的"),  # 优先级 1：大写单字母 + 半角冒号（v0.1 唯一支持的写法）
    ("a: 你好", "b: 在的"),  # 单字母大小写不敏感
    ("A：你好", "B：在的"),  # 全角冒号
    ("A:你好", "B:在的"),  # 冒号后 0 个空格
    ("A:     你好", "B:  在的"),  # 冒号后多个空格
    ("张三: 你好", "李四: 在的"),  # 优先级 2：真实姓名（半角冒号）
    ("张三：你好", "李四：在的"),  # 真实姓名（全角冒号）
    ("张三2: 你好", "li_si: 在的"),  # 名字允许中文 / 英文 / 数字 / 下划线
    ("我: 你好", "你: 在的"),  # 优先级 3：我 / 你
    ("我：你好", "你：在的"),
    ("[张三] 你好", "[李四] 在的"),  # 优先级 4：半角方括号
    ("【张三】你好", "【李四】在的"),  # 全角方括号（右括号后 0 个空格）
]


@pytest.mark.parametrize("first,second", MARKER_CASES)
def test_speaker_markers_accept_all_documented_shapes(first: str, second: str) -> None:
    """决策 1：列出的多种标记写法都要能识别，且仍归到 A / B 两个人。"""
    result = _parse([first, second])

    assert result.errors == []
    assert result.unmarked == []
    assert [m.body for m in result.messages] == ["你好", "在的"]
    assert [m.seq for m in result.messages] == [0, 1]
    assert [m.source_lines for m in result.messages] == [[1], [2]]
    # 两个不同标记 → A / B 两个角色（首次出现的拿 A），不是四个人
    assert [m.person_id for m in result.messages] == [
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "B"),
    ]


def test_marker_separator_allows_zero_one_or_many_spaces() -> None:
    """决策 1：冒号后 0~N 个空格都接受，正文只剥掉作为分隔的空白。"""
    result = _parse(["A:你好", "B: 在的", "A:     很多空格"])

    assert result.errors == []
    assert result.unmarked == []
    assert [m.body for m in result.messages] == ["你好", "在的", "很多空格"]
    assert [m.source_line for m in result.messages] == [1, 2, 3]


def test_halfwidth_and_fullwidth_colons_can_mix_in_one_text() -> None:
    """决策 1：同一段文本里中英文冒号混用都要识别；同一个人换冒号写法不因此被拆成两条消息。"""
    result = _parse(["张三: 半角冒号", "张三：全角冒号", "李四：换人说话"])

    assert result.errors == []
    assert result.unmarked == []
    assert [m.body for m in result.messages] == ["半角冒号 全角冒号", "换人说话"]
    assert [m.source_lines for m in result.messages] == [[1, 2], [3]]
    assert [m.person_id for m in result.messages] == [
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "B"),
    ]


def test_role_aliases_letters_and_symbolic_names_are_the_same_two_people() -> None:
    """`A:` 与 `我:` 是同一个人（角色 A），`B:` 与 `你:` 是同一个人（角色 B）。"""
    result = _parse(["A: 第一条", "我: 第二条", "你: 第三条", "B: 第四条", "[我] 第五条"])

    assert result.errors == []
    assert result.unmarked == []
    assert [m.body for m in result.messages] == ["第一条 第二条", "第三条 第四条", "第五条"]
    assert [m.person_id for m in result.messages] == [
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "B"),
        make_person_id(CONVERSATION_ID, "A"),
    ]
    # 五人写法只产出两个角色 —— 双人系统不允许「猜」出第三个说话人
    assert {m.person_id for m in result.messages} == {
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "B"),
    }


# ---------------------------------------------------------------- 决策 2：连续发言合并


def test_consecutive_turns_of_one_speaker_merge_into_a_single_message() -> None:
    """决策 2：3 条张三 + 1 条李四 → 2 条消息；seq 只 +1，source_lines 保留原始行号。"""
    result = _parse(["张三: 第一条", "张三: 第二条", "张三: 第三条", "李四: 第四条"])

    assert result.errors == []
    assert len(result.messages) == 2

    merged, other = result.messages
    assert merged.body == "第一条 第二条 第三条"
    assert merged.seq == 0 and other.seq == 1  # seq 只 +1（不是每条 +1）
    assert merged.source_line == 1  # 旧字段保留第一条行号
    assert merged.source_lines == [1, 2, 3]  # 合并前的原始行号列表
    assert other.body == "第四条"
    assert other.source_lines == [4]
    # message_id 仍按**合并后**的 seq 生成，算法本身不变
    assert merged.message_id == make_message_id(CONVERSATION_ID, 0)
    assert other.message_id == make_message_id(CONVERSATION_ID, 1)


def test_merge_consecutive_false_keeps_every_line_as_its_own_message() -> None:
    """`merge_consecutive=False`（前端「不合并」开关）→ 每行一条消息。"""
    result = _parse(
        ["张三: 第一条", "张三: 第二条", "张三: 第三条", "李四: 第四条"],
        merge_consecutive=False,
    )

    assert [m.body for m in result.messages] == ["第一条", "第二条", "第三条", "第四条"]
    assert [m.seq for m in result.messages] == [0, 1, 2, 3]
    assert [m.source_line for m in result.messages] == [1, 2, 3, 4]
    assert [m.source_lines for m in result.messages] == [[1], [2], [3], [4]]
    assert [m.person_id for m in result.messages] == [
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "A"),
        make_person_id(CONVERSATION_ID, "B"),
    ]


def test_merged_seq_starts_at_seq_offset() -> None:
    """合并与 `seq_offset`（T-008 追加导入续号）叠加时，seq 仍从偏移量起算。"""
    result = _parse(["A: 一", "A: 二", "B: 三"], seq_offset=7)

    assert [m.seq for m in result.messages] == [7, 8]
    assert [m.message_id for m in result.messages] == [
        make_message_id(CONVERSATION_ID, 7),
        make_message_id(CONVERSATION_ID, 8),
    ]


def test_empty_body_line_does_not_break_a_consecutive_run() -> None:
    """`A: `（标记在、正文空）仍记为解析错误，但**不打断**连续段（它没有内容）。"""
    result = _parse(["A: 一", "A: ", "A: 二"])

    assert [(e.line_number, e.reason) for e in result.errors] == [(2, REASON_EMPTY_BODY)]
    assert result.unmarked == []
    assert [m.body for m in result.messages] == ["一 二"]
    assert [m.source_lines for m in result.messages] == [[1, 3]]


# ---------------------------------------------------------------- 决策 3：未标记兜底


def test_unmarked_line_between_two_turns_is_reported_without_blocking() -> None:
    """决策 3：识别不出的行进 `unmarked`（不报错、不阻断），并打断连续段（说话人未知）。"""
    result = _parse(["A: 第一条", "完全没标记的一行", "A: 第二条"])

    assert result.errors == []
    assert result.ok is True  # 未标记行不算失败
    assert result.has_unmarked is True
    assert [m.body for m in result.messages] == ["第一条", "第二条"]  # 未标记行不阻断 A/B 行
    assert [m.source_lines for m in result.messages] == [[1], [3]]  # 也不跨它合并
    assert [(u.line_number, u.raw_text, u.reason) for u in result.unmarked] == [
        (2, "完全没标记的一行", REASON_UNMARKED_NO_MARKER)
    ]


def test_third_speaker_is_unmarked_rather_than_guessed() -> None:
    """识别到第 3 个说话人时只把该行标为未标记，不猜它属于 A 还是 B。"""
    result = _parse(["张三: 一", "李四: 二", "王五: 三"])

    assert result.errors == []
    assert [m.body for m in result.messages] == ["一", "二"]
    assert [(u.line_number, u.reason) for u in result.unmarked] == [
        (3, REASON_UNMARKED_EXTRA_SPEAKER)
    ]


def test_numeric_prefix_looks_like_a_timestamp_and_stays_unmarked() -> None:
    """`10:30 出发` 这类纯数字前缀更像时间戳，不认作说话人（同样不报错）。"""
    result = _parse(["A: 我十点半出发", "10:30 出发"])

    assert result.errors == []
    assert [m.body for m in result.messages] == ["我十点半出发"]
    assert [(u.line_number, u.reason) for u in result.unmarked] == [
        (2, REASON_UNMARKED_NO_MARKER)
    ]


# ---------------------------------------------------------------- 空行与参数校验


def test_blank_lines_are_skipped_counted_and_do_not_break_a_run() -> None:
    result = _parse(["A: 一", "", "   ", "A: 二"])

    assert result.blank_lines_skipped == 2
    assert result.errors == []
    assert result.unmarked == []
    assert [m.body for m in result.messages] == ["一 二"]
    assert [m.source_lines for m in result.messages] == [[1, 4]]


def test_leading_and_trailing_blank_lines_are_counted() -> None:
    result = parse_chat("\n\n   \nA: 只有一条\n\n", CONVERSATION_ID)

    assert result.blank_lines_skipped == 4
    assert result.errors == []
    assert len(result.messages) == 1
    assert result.messages[0].source_line == 4


def test_parse_chat_rejects_bad_arguments() -> None:
    with pytest.raises(TypeError):
        parse_chat(None, CONVERSATION_ID)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_chat("A: 你好", "")
    with pytest.raises(ValueError):
        make_person_id(CONVERSATION_ID, "C")
    # seq_offset 早失败：非 int / 负数都不许悄悄写成序号 0（§6 追加导入自动续号）
    with pytest.raises(TypeError):
        parse_chat("A: 你好", CONVERSATION_ID, seq_offset="50")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_chat("A: 你好", CONVERSATION_ID, seq_offset=-1)
    # merge_consecutive 必须是 bool：字符串 "false" 不能被当成真值
    with pytest.raises(TypeError):
        parse_chat("A: 你好", CONVERSATION_ID, merge_consecutive="false")  # type: ignore[arg-type]


def test_make_message_id_is_deterministic_and_conversation_scoped() -> None:
    cid = "会话 with 中文 + spaces"

    assert make_message_id(cid, 0) == str(uuid.uuid5(uuid.NAMESPACE_URL, f"{cid}:0"))
    assert make_message_id(cid, 0) == make_message_id(cid, 0)  # 可复现，无随机成分
    assert make_message_id(cid, 0) != make_message_id(cid, 1)  # seq 敏感
    assert make_message_id(cid, 0) != make_message_id(f"{cid} ", 0)  # conversation_id 不 strip
    assert make_message_id(cid, 0) != make_message_id(f"{cid}x", 0)


# ---------------------------------------------------------------- 写库 / 去重 / 追加


def test_import_chat_writes_messages_and_persons(db_path: Path) -> None:
    """service 函数：解析结果落到 messages / persons 表。"""
    report = import_chat(NORMAL_TEXT, CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_INSERTED
    assert report.rejected is False
    assert report.inserted_count == 4
    assert report.conflicts == []
    assert report.errors == []
    assert report.unmarked == []
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


def test_import_chat_skips_unmarked_lines_but_keeps_the_rest(db_path: Path) -> None:
    """决策 3：未标记行**不阻断导入**，也不落库；报告的 `unmarked` 带行号与原行。"""
    text = "\n".join(
        ["A: 第一条", "没有标记的一行", "B: 第二条", "A: 第三条", "10:30 出发", "A: 第四条"]
    )

    report = import_chat(text, CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_INSERTED
    assert report.rejected is False
    assert report.errors == []  # 未标记 ≠ 解析错误
    assert report.inserted_count == 4
    assert [m.body for m in report.messages] == ["第一条", "第二条", "第三条", "第四条"]
    assert [m.source_line for m in report.messages] == [1, 3, 4, 6]
    assert [(u.line_number, u.reason) for u in report.unmarked] == [
        (2, REASON_UNMARKED_NO_MARKER),
        (5, REASON_UNMARKED_NO_MARKER),
    ]

    assert _bodies(db_path) == ["第一条", "第二条", "第三条", "第四条"]
    assert _count_rows(db_path, "messages") == 4


def test_import_chat_with_only_unmarked_lines_inserts_nothing(db_path: Path) -> None:
    report = import_chat("hello world\n还是不合格式的一行", CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_NOTHING_TO_IMPORT
    assert report.inserted_count == 0
    assert report.messages == []
    assert report.errors == []  # 宽容解析：这是「未标记」，不是「坏格式」
    assert [u.line_number for u in report.unmarked] == [1, 2]
    assert not db_path.exists()  # 没有任何可写入内容时，不创建库文件


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


def test_insert_messages_with_empty_batch_is_a_noop(db_path: Path) -> None:
    report = insert_messages([], db_path=db_path)

    assert report.status == STATUS_NOTHING_TO_IMPORT
    assert report.inserted_count == 0
    assert not db_path.exists()


def test_parse_chat_with_seq_offset_continues_numbering() -> None:
    """T-008 缺陷修复（§6 2026-09-23）：seq_offset=50 → seq 从 50 起，message_id 不与 seq 0-49 冲突。"""
    text = _bulk_text(20)

    result = parse_chat(text, CONVERSATION_ID, seq_offset=50)

    assert result.errors == []
    assert [m.seq for m in result.messages] == list(range(50, 70))
    assert [m.source_line for m in result.messages] == list(range(1, 21))
    assert result.messages[0].message_id == make_message_id(CONVERSATION_ID, 50)
    assert result.messages[-1].message_id == make_message_id(CONVERSATION_ID, 69)
    # 与「首段文本 seq 0-49」的 ID 完全不重合：这正是旧实现必然冲突的原因
    first_segment_ids = {make_message_id(CONVERSATION_ID, seq) for seq in range(50)}
    assert first_segment_ids.isdisjoint({m.message_id for m in result.messages})


def test_appended_import_continues_seq_and_write_succeeds(db_path: Path) -> None:
    """T-008 缺陷修复：先导入 50 条，再以 seq_offset=50 追加 20 条 → 两次都成功，库内共 70 条。"""
    first = import_chat(_bulk_text(50), CONVERSATION_ID, db_path=db_path)
    assert first.status == STATUS_INSERTED
    assert first.inserted_count == 50
    assert first.messages[-1].seq == 49

    appended = import_chat(_bulk_text(20, start=50), CONVERSATION_ID, seq_offset=50, db_path=db_path)

    assert appended.status == STATUS_INSERTED
    assert appended.rejected is False
    assert appended.inserted_count == 20
    assert appended.conflicts == []
    assert [m.seq for m in appended.messages] == list(range(50, 70))

    conn = sqlite3.connect(db_path)
    try:
        seqs = [row[0] for row in conn.execute("SELECT seq FROM messages ORDER BY seq")]
        ids = [row[0] for row in conn.execute("SELECT message_id FROM messages ORDER BY seq")]
    finally:
        conn.close()
    assert seqs == list(range(70))
    assert len(set(ids)) == 70
    assert _count_rows(db_path, "messages") == 70
    assert _count_rows(db_path, "persons") == 2  # 同一会话的 A/B 不重复建行

    # 不带 seq_offset（旧行为）时，同一段追加文本仍会被「拒绝整批」——证明修复点在续号而不在冲突策略
    naive = import_chat(_bulk_text(20, start=50), CONVERSATION_ID, db_path=db_path)
    assert naive.status == STATUS_REJECTED_CONFLICT
    assert naive.inserted_count == 0
    assert len(naive.conflicts) == 20
    assert _count_rows(db_path, "messages") == 70


# ---------------------------------------------------------------- 导入接口的未标记行回执


@pytest.fixture()
def api(db_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """注入临时库的 TestClient（不联网、不碰真实库）：只用于核对导入接口的响应体。"""
    import main

    monkeypatch.setattr(main.app.state, "db_path", db_path, raising=False)
    monkeypatch.setattr(main.app.state, "audit_path", tmp_path / "deletion_audit.jsonl", raising=False)
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        yield client


def test_import_api_returns_unmarked_lines_with_50_char_preview(db_path: Path, api) -> None:
    """`POST /messages:import` 回执带 `unmarked_lines`（行号 + 前 50 字符），且不阻断导入。"""
    long_line = "没有标记的一行" * 12  # 120 字符：预览必须被截到 50 字符

    response = api.post(
        f"/conversations/{CONVERSATION_ID}/messages:import",
        json={"text": "\n".join(["张三: 第一条", long_line, "李四: 第二条"])},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "inserted"
    assert payload["inserted_count"] == 2
    assert payload["errors"] == []
    assert payload["conflicts"] == []
    assert payload["unmarked_lines"] == [
        {"line_number": 2, "preview": long_line[:50]},
    ]
    assert _count_rows(db_path, "messages") == 2
    assert _bodies(db_path) == ["第一条", "第二条"]