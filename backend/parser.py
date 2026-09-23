"""T-002 文本解析器：宽容解析真实聊天文本 → MessageDTO → 写入 messages 表。

规格来源
--------
- `ARCHITECTURE.md` §0（v0.1 冻结）：第一版**仅**支持 `A: 正文` / `B: 正文`。
- `ARCHITECTURE.md` §6（**2026-09-23 放宽冻结**）：升级为**宽容解析器**——多格式说话人标记
  （`A:` / `张三:` / `我:` / `[张三]` / 无标记兜底）+ 连续发言合并 + 未标记行兜底。
- `ARCHITECTURE.md` §6（2026-09-22 冻结方案 A；2026-09-23 补冻结「追加导入自动续号」）：
  `message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`；`seq` 是**会话内的全局序号**
  （合并后的消息序号），起点由调用方通过 `seq_offset` 给出（导入端取库内 `MAX(seq)+1`）。
  重复导入策略 = **拒绝整批**：写库前对全批 `message_id` 做存在性检查，只要有一个已存在就整批
  不写入，并在报告中列出冲突 ID 与来源行号（不做部分导入、不静默跳过）。

说话人识别（优先级从高到低，`_split_speaker()`）
------------------------------------------------
1. `标记: 正文` / `标记：正文`——**中英文冒号都接受**，冒号后允许 **0~N 个空格**；
   标记允许 1–20 个「中文 / 英文 / 数字 / 下划线」字符（如 `A` / `张三` / `我` / `你`）。
2. `[标记] 正文` / `【标记】正文`——右括号后允许 0~N 个空格。
3. 都不匹配 → **未标记行**（`ParseResult.unmarked`），**不报错、不阻断导入**（决策 3）。

角色归属（`_resolve_roles()`：先扫全文收集标记，再定角色——两遍扫描，避免顺序歧义）
----------------------------------------------------------------------------------
- 单字母 `A` / `a` → 角色 **A**；`B` / `b` → 角色 **B**（大小写不敏感）。
- `我` → 角色 **A**（粘贴者本人）；`你` → 角色 **B**（对话对方）。
- 其余标记（姓名、方括号里的名字）按**首次出现顺序**填补尚空闲的角色（先 A 后 B）。
- 已凑满两人后再出现的新标记 → 该行归入「未标记」（双人系统只支持 A/B，不猜测、不报错）。

连续发言合并（默认开启，`merge_consecutive=True`；决策 2）
----------------------------------------------------------
- 同一角色的连续行合并成**一条**消息：`body` = 各条原文用**一个空格**连接，`seq` 只 +1。
- `source_lines` 记录合并前的**原始行号列表**（升序）；`source_line` 保留**第一条**行号。
- 空行（跳过）与「正文为空」的错误行**不打断**连续段（它们没有内容）；
  **未标记行打断**连续段（说话人未知，不能断言「连续」）。

本文件采用、但尚未被规格冻结的假设（已记入 HANDOFF 的「需人工确认」）
----------------------------------------------------------------------
1. `person_id = uuid5(NAMESPACE_URL, f"person:{conversation_id}:{role}")`：会话内 A / B 各一个
   确定性 ID（`ARCHITECTURE.md` §6 只冻结了 `message_id`，未冻结 `person_id`）。
2. 文本中含未标记行 / 解析错误行时，仍导入**可解析成功**的行，并在报告中列出；只有
   `message_id` 冲突才拒绝整批（TASKS.md T-002 从未规定「有坏行就整批中止」）。
3. 「正文为空」（如 `A: `、`张三：`）仍视为**解析错误**（标记存在但无内容，人工标注没有意义）；
   其余识别不出的行一律进「未标记」桶，**不报错**。
4. 正文按原文保留：只剥掉说话人标记之后**作为分隔的空白**（`lstrip`），正文内部与末尾原样入库。
5. **纯数字标记**（如 `10:30 出发` 里的 `10`）不认作说话人——那更像时间戳；该行归入「未标记」。
6. 合并后的 `body` 与 `source_lines` **不落库**（`messages` 表结构未变，只存 `source_line` = 首行号）；
   需要逐行原文时可回查首行号对应的 `messages.body`。
7. 判定「连续」只看**产出的消息**之间的相邻关系；同角色但中间夹了未标记行的两行**不合并**。

日志规范（PRIVACY.md §4.2）：只记录会话 ID、条数、`message_id`；**不得**记录 `body` 明文。
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from db import get_connection, init_db

logger = logging.getLogger(__name__)

SPEAKERS: tuple[str, str] = ("A", "B")
ROLE_A: str = "A"
ROLE_B: str = "B"

#: 合并同一角色连续发言时，各条原文之间的连接符（决策 2）。
BODY_JOINER = " "

#: 说话人标记允许的长度区间（决策 1：1–20 个字符）。
LABEL_MIN_CHARS = 1
LABEL_MAX_CHARS = 20

#: 单字母标记 → 角色（决策 1 优先级 1；**大小写不敏感**：`a` / `A` 是同一个说话人）。
LETTER_ROLE_HINTS: dict[str, str] = {"A": ROLE_A, "B": ROLE_B}

#: 整词标记 → 角色（决策 1 优先级 3：`我` 是粘贴者本人，`你` 是对话对方）。
WORD_ROLE_HINTS: dict[str, str] = {"我": ROLE_A, "你": ROLE_B}

#: 合法标记：1–20 个「中文 / 英文 / 数字 / 下划线」。
_LABEL_PATTERN = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff]{%d,%d}\Z" % (LABEL_MIN_CHARS, LABEL_MAX_CHARS))

#: 中英文冒号（决策 1：两者都接受）。
COLONS: tuple[str, ...] = (":", "：")

#: 方括号形式（决策 1 优先级 4）。
BRACKETS: tuple[tuple[str, str], ...] = (("[", "]"), ("【", "】"))

# 解析错误原因文案（进错误报告，便于使用者定位问题行）
REASON_EMPTY_BODY = "正文为空：说话人标记之后没有可分析的内容"

# 未标记行原因文案（进 `ParseResult.unmarked`；**不是**错误，不阻断导入）
REASON_UNMARKED_NO_MARKER = "没有可识别的说话人标记（不阻断导入，可在 ② A/B 标记里手动指定）"
REASON_UNMARKED_EXTRA_SPEAKER = "识别到第 3 个及以后的说话人，超出 A/B 双人范围（不阻断导入）"

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
    """解析结果中的一条消息（字段与 TASKS.md T-002「输出」一致）。

    `source_lines`（2026-09-23 决策 2 新增）是**合并前**的原始行号列表（升序）；
    `source_line` 保留第一条行号，与既有契约（`messages.source_line` 列）保持一致。
    """

    message_id: str
    conversation_id: str
    person_id: str
    seq: int
    body: str
    source_line: int
    source_lines: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class UnmarkedLine:
    """无法识别说话人的一行（决策 3：归入「未标记」桶，不报错、不阻断导入）。

    `reason` 说明为什么没标上（无标记 / 双人之外的第三人），供前端提示用。
    """

    line_number: int
    raw_text: str
    reason: str = ""


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
    unmarked: list[UnmarkedLine] = field(default_factory=list)
    blank_lines_skipped: int = 0

    @property
    def ok(self) -> bool:
        """全部行都解析成功（空行不算失败；「未标记行」也不算失败，见决策 3）。"""
        return not self.errors

    @property
    def has_unmarked(self) -> bool:
        """是否存在未标记行（前端据此提示「可手动标注」）。"""
        return bool(self.unmarked)


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
    """`import_chat()` 的完整结果：解析错误 + 未标记行 + 写入结果。"""

    status: str
    inserted_count: int
    messages: list[MessageDTO] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    unmarked: list[UnmarkedLine] = field(default_factory=list)
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


def _is_speaker_label(label: str) -> bool:
    """判断冒号 / 方括号里取出的文本能不能当说话人标记（决策 1 的字符与长度约束）。"""
    if not _LABEL_PATTERN.match(label):
        return False
    # 纯数字几乎必然是时间戳片段（`10:30 出发` 里的 `10`），不是人名 —— 归入「未标记」
    return not label.isdigit()


def _role_hint(label: str) -> str | None:
    """标记自带的角色倾向（`A`/`a`/`我` → A，`B`/`b`/`你` → B）；普通姓名返回 None。"""
    if len(label) == 1 and label.isascii() and label.isalpha():
        hint = LETTER_ROLE_HINTS.get(label.upper())
        if hint is not None:
            return hint
    return WORD_ROLE_HINTS.get(label)


def _resolve_roles(order: Sequence[str]) -> dict[str, str]:
    """把「按首次出现顺序排好的标记列表」解析成 `标记 -> 角色` 映射。

    规则（`ARCHITECTURE.md` §6，2026-09-23 决策 1）：
    1. 带倾向的标记直接占位（`A`/`a` → A、`B`/`b` → B、`我` → A、`你` → B）；两个标记落到同一条
       倾向时视为**同一个人**（如同一段文本里既有 `A:` 又有 `我:`）。
    2. 无倾向的标记（姓名、方括号里的名字）按**首次出现顺序**填补尚空闲的角色（先 A 后 B）。
    3. 角色用尽后仍未归类的标记**不写进映射**，调用方按「未标记」处理（双人系统只支持 A/B）。
    """
    roles: dict[str, str] = {}
    taken: set[str] = set()
    for label in order:
        hint = _role_hint(label)
        if hint is None:
            continue
        roles[label] = hint
        taken.add(hint)

    pending = [label for label in order if label not in roles]
    free = [role for role in SPEAKERS if role not in taken]
    for label, role in zip(pending, free):
        roles[label] = role
    return roles


def _split_speaker(raw_line: str) -> tuple[str, str] | None:
    """识别一行里的「说话人标记 + 正文」；识别不出来返回 None（调用方归入未标记）。

    按决策 1 的优先级：
    1. `标记: 正文` / `标记：正文`——取**第一个**冒号（中英文皆可），冒号后允许 0~N 个空格；
    2. `[标记] 正文` / `【标记】正文`——右括号后允许 0~N 个空格。
    """
    positions = [index for index in (raw_line.find(COLONS[0]), raw_line.find(COLONS[1])) if index >= 0]
    if positions:
        index = min(positions)
        label = raw_line[:index].strip()
        if _is_speaker_label(label):
            return label, raw_line[index + 1 :].lstrip()

    for opener, closer in BRACKETS:
        if not raw_line.startswith(opener):
            continue
        end = raw_line.find(closer, len(opener))
        if end < 0:
            continue
        label = raw_line[len(opener) : end].strip()
        if _is_speaker_label(label):
            return label, raw_line[end + 1 :].lstrip()
    return None


@dataclass(frozen=True)
class _Line:
    """扫描阶段的中间态：`label is None` 表示未标记行（`reason` 说明原因）。"""

    line_number: int
    raw_line: str
    label: str | None
    body: str = ""
    reason: str = ""


def parse_chat(
    text: str,
    conversation_id: str,
    *,
    seq_offset: int = 0,
    merge_consecutive: bool = True,
) -> ParseResult:
    """把整段聊天文本解析成 MessageDTO 列表 + 错误行列表 + 未标记行列表。

    - 空行（含仅空白行）跳过并计数，不产生消息、不产生错误。
    - `seq` 只对**产出的消息**递增，**从 `seq_offset` 开始**（默认 0；追加导入时由调用方传入
      库内 `MAX(seq)+1`，见 §6「追加导入自动续号」）。
    - `merge_consecutive=True`（默认）：同一角色的连续行合并成一条（决策 2）；
      置为 `False` 则逐行产出（每行一条消息）。
    - 非文本类型 / `None` 输入抛 TypeError；`seq_offset` 非 int 或为负抛 TypeError / ValueError；
      `merge_consecutive` 非 bool 抛 TypeError（早失败，避免静默丢数据或写坏序号）。
    """
    if not isinstance(text, str):
        raise TypeError("text 必须是 str")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError("conversation_id 必须是非空 str")
    if isinstance(seq_offset, bool) or not isinstance(seq_offset, int):
        raise TypeError("seq_offset 必须是 int")
    if seq_offset < 0:
        raise ValueError("seq_offset 必须 >= 0")
    if not isinstance(merge_consecutive, bool):
        raise TypeError("merge_consecutive 必须是 bool")

    result = ParseResult()
    scanned: list[_Line] = []
    label_order: list[str] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            result.blank_lines_skipped += 1
            continue

        split = _split_speaker(raw_line)
        if split is None:
            scanned.append(_Line(line_number, raw_line, None, reason=REASON_UNMARKED_NO_MARKER))
            continue

        label, body = split
        if not body.strip():
            result.errors.append(ParseError(line_number, raw_line, REASON_EMPTY_BODY))
            continue

        if label not in label_order:
            label_order.append(label)
        scanned.append(_Line(line_number, raw_line, label, body))

    # 先扫全文收集标记（`label_order`）再定角色：避免「先出现的姓名抢走 A」这类顺序歧义
    roles = _resolve_roles(label_order)

    messages: list[MessageDTO] = []
    run_lines: list[int] = []
    run_bodies: list[str] = []
    run_role: str | None = None

    def flush_run() -> None:
        """把当前连续段落成一条消息：`seq` 只 +1，`source_lines` 记录合并前的行号。"""
        if run_role is None or not run_lines:
            return
        seq = seq_offset + len(messages)
        messages.append(
            MessageDTO(
                message_id=make_message_id(conversation_id, seq),
                conversation_id=conversation_id,
                person_id=make_person_id(conversation_id, run_role),
                seq=seq,
                body=BODY_JOINER.join(run_bodies),
                source_line=run_lines[0],
                source_lines=list(run_lines),
            )
        )

    def reset_run() -> None:
        nonlocal run_role
        run_lines.clear()
        run_bodies.clear()
        run_role = None

    for line in scanned:
        role = roles.get(line.label) if line.label is not None else None
        if role is None:
            # 未标记行（识别不出标记 / 双人之外的第三人）：不报错，但**打断**连续段（说话人未知）
            flush_run()
            reset_run()
            result.unmarked.append(
                UnmarkedLine(
                    line.line_number,
                    line.raw_line,
                    line.reason or REASON_UNMARKED_EXTRA_SPEAKER,
                )
            )
            continue

        if run_role is not None and run_role != role:
            flush_run()
            reset_run()

        run_role = role
        run_lines.append(line.line_number)
        run_bodies.append(line.body)
        if not merge_consecutive:
            flush_run()
            reset_run()

    flush_run()

    logger.info(
        "parse_chat: conversation=%s parsed=%d errors=%d unmarked=%d blank_skipped=%d"
        " seq_offset=%d merge=%s seq_range=[%s,%s]",
        conversation_id,
        len(messages),
        len(result.errors),
        len(result.unmarked),
        result.blank_lines_skipped,
        seq_offset,
        merge_consecutive,
        messages[0].seq if messages else None,
        messages[-1].seq if messages else None,
    )
    # 汇总扫描结果：messages 是局部列表（flush_run 往它 append），必须回填到 result，
    # 否则 ParseResult.messages 恒为空、import_chat 会误判 nothing_to_import。
    result.messages = messages

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
    整批都不写入，冲突以 `InsertReport.conflicts` 返回。

    只写 `messages` 的既有列；`MessageDTO.source_lines`（合并前的行号列表）**不落库**，
    `source_line` 写的是合并后消息的**首行号**（表结构未变）。

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
    解析错误（`errors`，只含「标记存在但正文为空」）、**未标记行**（`unmarked`，决策 3：
    不阻断导入、可由前端手动标注）、跳过空行数（`blank_lines_skipped`）与解析出的 `messages`。

    `seq_offset`：会话内全局序号的起点（默认 0）。**追加导入**时必须传入库内 `MAX(seq)+1`，
    否则新批次的 `message_id` 会与既有行冲突并被「拒绝整批」（`ARCHITECTURE.md` §6）。

    未标记行本就不产出消息，因此天然「跳过」；若要逐行导入（不合并连续发言），请直接调用
    `parse_chat(..., merge_consecutive=False)` 再把结果交给 `insert_messages()`。
    """
    parsed = parse_chat(text, conversation_id, seq_offset=seq_offset)

    if not parsed.messages:
        logger.info(
            "import_chat: conversation=%s 无可写入消息（errors=%d unmarked=%d）",
            conversation_id,
            len(parsed.errors),
            len(parsed.unmarked),
        )
        return ImportReport(
            status=STATUS_NOTHING_TO_IMPORT,
            inserted_count=0,
            messages=parsed.messages,
            errors=parsed.errors,
            unmarked=parsed.unmarked,
            blank_lines_skipped=parsed.blank_lines_skipped,
        )

    inserted = insert_messages(parsed.messages, connection=connection, db_path=db_path)
    return ImportReport(
        status=inserted.status,
        inserted_count=inserted.inserted_count,
        messages=parsed.messages,
        conflicts=inserted.conflicts,
        errors=parsed.errors,
        unmarked=parsed.unmarked,
        blank_lines_skipped=parsed.blank_lines_skipped,
    )