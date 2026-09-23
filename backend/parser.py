"""T-002 文本解析器：解析 `A: 正文` / `B: 正文`，生成 MessageDTO 并写入 messages 表。

规格来源
--------
- `ARCHITECTURE.md` §0（v0.1 冻结）：第一版**仅**支持 `A: 正文` 与 `B: 正文`；不支持时间前缀、
  微信/QQ 导出。`A`/`B` 仅接受**大写**。
- `ARCHITECTURE.md` §6（2026-09-22 冻结方案 A；2026-09-23 补冻结「追加导入自动续号」）：
  `message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`；`seq` 是**会话内的全局序号**
  （不是「本段文本内的序号」），起点由调用方通过 `seq_offset` 给出（导入端取库内 `MAX(seq)+1`），
  新批次据此续号，使「同一会话追加消息」不再因 `message_id` 冲突被「拒绝整批」。
  重复导入策略 = **拒绝整批**：写库前对全批 `message_id` 做存在性检查，只要有一个已存在就整批
  不写入，并在报告中列出冲突 ID 与来源行号（不做部分导入、不静默跳过）。

本文件采用、但尚未被规格冻结的假设（已记入 HANDOFF 的「需人工确认」）
------------------------------------------------------------------------
1. `person_id = uuid5(NAMESPACE_URL, f"person:{conversation_id}:{role}")`：会话内 A / B 各一个
   确定性 ID（`ARCHITECTURE.md` §6 只冻结了 `message_id`，未冻结 `person_id`）。
2. 文本中含解析错误行时，仍导入**可解析成功**的行，并在报告中列出错误；只有 `message_id`
   冲突才拒绝整批（TASKS.md T-002 只要求「非 A:/B: 行记入错误列表」，未规定必须整批中止）。
3. `A: `（冒号 + 一个空格后正文为空）与「仅空格的正文」视为解析错误。
4. 正文按原文完整保留：`A: ` 之后的所有字符（含多余空格、二次冒号）原样入库，不做 strip。
5. 仅以 `:`（半角冒号）识别前缀；全角 `：` 不识别，计入错误行。

日志规范（PRIVACY.md §4.2）：只记录会话 ID、条数、`message_id`；**不得**记录 `body` 明文。
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from db import get_connection, init_db

logger = logging.getLogger(__name__)

SPEAKERS: tuple[str, str] = ("A", "B")

# 解析错误原因文案（进错误报告，便于使用者定位问题行）
REASON_NO_COLON = "找不到说话人前缀的冒号：本行不是 `A: 正文` / `B: 正文` 格式"
REASON_BAD_SPEAKER = "说话人标记无效：仅支持大写 A 或 B（不支持小写、昵称、时间戳前缀）"
REASON_NO_SPACE = "冒号后必须恰好一个空格，例如 `A: 你好`"
REASON_EMPTY_BODY = "正文为空：`A: ` / `B: ` 之后没有可分析的内容"

# 状态值（报告用，避免调用方比较散落字符串）
STATUS_INSERTED = "inserted"
STATUS_REJECTED_CONFLICT = "rejected_conflict"
STATUS_NOTHING_TO_IMPORT = "nothing_to_import"

_SQL_CHUNK = 500  # 单条 SELECT 的最大参数个数，避免超过 SQLite 变量上限


def _utc_now() -> str:
    """ISO-8601 UTC 字符串（`ARCHITECTURE.md` §4 约定）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class MessageDTO:
    """解析结果中的一条消息（字段与 TASKS.md T-002「输出」一致）。"""

    message_id: str
    conversation_id: str
    person_id: str
    seq: int
    body: str
    source_line: int


@dataclass(frozen=True)
class ParseError:
    """一行无法解析的记录。"""

    line_number: int
    raw_line: str
    reason: str


@dataclass
class ParseResult:
    messages: list[MessageDTO] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    blank_lines_skipped: int = 0

    @property
    def ok(self) -> bool:
        """全部行都解析成功（空行不算失败）。"""
        return not self.errors


@dataclass(frozen=True)
class Conflict:
    """`message_id` 冲突（重复导入）。"""

    message_id: str
    source_line: int


@dataclass
class InsertReport:
    status: str
    inserted_count: int
    conflicts: list[Conflict] = field(default_factory=list)
    persons_created: int = 0

    @property
    def rejected(self) -> bool:
        return self.status == STATUS_REJECTED_CONFLICT


@dataclass
class ImportReport:
    """`import_chat()` 的完整结果：解析错误 + 写入结果。"""

    status: str
    inserted_count: int
    messages: list[MessageDTO] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    blank_lines_skipped: int = 0

    @property
    def rejected(self) -> bool:
        return self.status == STATUS_REJECTED_CONFLICT


def make_message_id(conversation_id: str, seq: int) -> str:
    """冻结算法（`ARCHITECTURE.md` §6）：uuid5(NAMESPACE_URL, "{conversation_id}:{seq}")。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{conversation_id}:{seq}"))


def make_person_id(conversation_id: str, role: str) -> str:
    """本文件假设的 person_id 算法（未在规格中冻结，见模块 docstring 假设 1）。"""
    if role not in SPEAKERS:
        raise ValueError(f"role 只能是 A 或 B，收到：{role!r}")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"person:{conversation_id}:{role}"))


def parse_chat(text: str, conversation_id: str, *, seq_offset: int = 0) -> ParseResult:
    """把整段聊天文本解析成 MessageDTO 列表 + 错误行列表。

    - 空行（含仅空白行）跳过并计数，不产生消息、不产生错误。
    - `seq` 只对**成功解析**的行递增，**从 `seq_offset` 开始**（默认 0，首版行为不变）。
    - `seq_offset` = 会话内全局序号的起点：追加导入时由调用方传入库内 `MAX(seq)+1`
      （`ARCHITECTURE.md` §6「追加导入自动续号」），使新批次与既有 `message_id` 不冲突。
    - 非文本类型/`None` 输入抛 TypeError；`seq_offset` 非 int 或为负抛 TypeError / ValueError
      （早失败，避免静默丢数据或写坏序号）。
    """
    if not isinstance(text, str):
        raise TypeError("text 必须是 str")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError("conversation_id 必须是非空 str")
    if isinstance(seq_offset, bool) or not isinstance(seq_offset, int):
        raise TypeError("seq_offset 必须是 int")
    if seq_offset < 0:
        raise ValueError("seq_offset 必须 >= 0")

    result = ParseResult()
    seq = seq_offset

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            result.blank_lines_skipped += 1
            continue

        if ":" not in raw_line:
            result.errors.append(ParseError(line_number, raw_line, REASON_NO_COLON))
            continue

        speaker, rest = raw_line.split(":", 1)
        if speaker not in SPEAKERS:
            result.errors.append(ParseError(line_number, raw_line, REASON_BAD_SPEAKER))
            continue
        if not rest.startswith(" "):
            result.errors.append(ParseError(line_number, raw_line, REASON_NO_SPACE))
            continue

        body = rest[1:]  # 原文完整保留：只剥掉分隔用的那一个空格
        if not body.strip():
            result.errors.append(ParseError(line_number, raw_line, REASON_EMPTY_BODY))
            continue

        result.messages.append(
            MessageDTO(
                message_id=make_message_id(conversation_id, seq),
                conversation_id=conversation_id,
                person_id=make_person_id(conversation_id, speaker),
                seq=seq,
                body=body,
                source_line=line_number,
            )
        )
        seq += 1

    logger.info(
        "parse_chat: conversation=%s parsed=%d errors=%d blank_skipped=%d seq_offset=%d",
        conversation_id,
        len(result.messages),
        len(result.errors),
        result.blank_lines_skipped,
        seq_offset,
    )
    return result


def _chunks(items: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _connect(connection, db_path) -> tuple:
    """返回 (connection, 是否为本次新开)。新开时确保表结构存在。"""
    if connection is not None:
        return connection, False
    path = Path(db_path) if db_path is not None else None
    init_db(path)  # 幂等：CREATE TABLE IF NOT EXISTS
    return get_connection(path), True


def insert_messages(
    messages: Iterable[MessageDTO], *, connection=None, db_path=None
) -> InsertReport:
    """把消息写入 `messages` 表（需要时先补 `persons` 行）。

    重复导入策略（已冻结）：**拒绝整批**——只要批内有 `message_id` 已在库中（或批内重复），
    本条都不写入，冲突以 `InsertReport.conflicts` 返回。

    注意：传入自有 `connection` 时，本函数会用该连接开事务并提交。
    """
    rows = list(messages)
    if not rows:
        return InsertReport(status=STATUS_NOTHING_TO_IMPORT, inserted_count=0)

    conversation_id = rows[0].conversation_id
    for row in rows:
        if row.conversation_id != conversation_id:
            raise ValueError("同一批只能写入同一个 conversation_id")

    ids = [row.message_id for row in rows]
    in_batch_counts = Counter(ids)

    conn, owned = _connect(connection, db_path)
    try:
        existing: set[str] = set()
        for chunk in _chunks(ids, _SQL_CHUNK):
            placeholders = ",".join("?" * len(chunk))
            cursor = conn.execute(
                f"SELECT message_id FROM messages WHERE message_id IN ({placeholders})",
                list(chunk),
            )
            existing.update(row["message_id"] for row in cursor.fetchall())

        conflicts = [
            Conflict(row.message_id, row.source_line)
            for row in rows
            if row.message_id in existing or in_batch_counts[row.message_id] > 1
        ]
        if conflicts:
            logger.warning(
                "insert_messages 拒绝整批：conversation=%s conflicts=%d（未写入任何行）",
                conversation_id,
                len(conflicts),
            )
            return InsertReport(
                status=STATUS_REJECTED_CONFLICT, inserted_count=0, conflicts=conflicts
            )

        person_ids = {role: make_person_id(conversation_id, role) for role in SPEAKERS}
        present_person_ids = {row.person_id for row in rows}
        roles_present = [role for role, pid in person_ids.items() if pid in present_person_ids]

        now = _utc_now()
        persons_created = 0
        with conn:  # 事务：persons 与 messages 要么都成，要么都不成
            for role in roles_present:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO persons (id, conversation_id, role, display_label, created_at)"
                    " VALUES (?, ?, ?, NULL, ?)",
                    (person_ids[role], conversation_id, role, now),
                )
                persons_created += max(cursor.rowcount, 0)
            conn.executemany(
                "INSERT INTO messages (message_id, conversation_id, person_id, seq, sent_at,"
                " body, source_line, created_at) VALUES (?, ?, ?, ?, NULL, ?, ?, ?)",
                [
                    (
                        row.message_id,
                        row.conversation_id,
                        row.person_id,
                        row.seq,
                        row.body,
                        row.source_line,
                        now,
                    )
                    for row in rows
                ],
            )
    finally:
        if owned:
            conn.close()

    logger.info(
        "insert_messages: conversation=%s inserted=%d persons_created=%d seq_range=[%d,%d]",
        conversation_id,
        len(rows),
        persons_created,
        min(row.seq for row in rows),
        max(row.seq for row in rows),
    )
    return InsertReport(
        status=STATUS_INSERTED, inserted_count=len(rows), persons_created=persons_created
    )


def import_chat(
    text: str, conversation_id: str, *, seq_offset: int = 0, connection=None, db_path=None
) -> ImportReport:
    """解析 + 写入的一站式 service 函数（调用方通常只需要这个）。

    返回的 `ImportReport` 同时携带：写入结果（`status` / `inserted_count` / `conflicts`）、
    解析错误（`errors`）、跳过空行数（`blank_lines_skipped`）与解析出的 `messages`。

    `seq_offset`：会话内全局序号的起点（默认 0）。**追加导入**时必须传入库内 `MAX(seq)+1`，
    否则新批次的 `message_id` 会与既有行冲突并被「拒绝整批」（`ARCHITECTURE.md` §6）。
    """
    parsed = parse_chat(text, conversation_id, seq_offset=seq_offset)

    if not parsed.messages:
        logger.info("import_chat: conversation=%s 无可写入消息", conversation_id)
        return ImportReport(
            status=STATUS_NOTHING_TO_IMPORT,
            inserted_count=0,
            messages=parsed.messages,
            errors=parsed.errors,
            blank_lines_skipped=parsed.blank_lines_skipped,
        )

    inserted = insert_messages(parsed.messages, connection=connection, db_path=db_path)
    return ImportReport(
        status=inserted.status,
        inserted_count=inserted.inserted_count,
        messages=parsed.messages,
        conflicts=inserted.conflicts,
        errors=parsed.errors,
        blank_lines_skipped=parsed.blank_lines_skipped,
    )