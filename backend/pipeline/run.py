"""T-004 分批分析管道：取消息 → 分批 → 脱敏调用模型 → 校验证据 → 写 analyses / evidence。

规格来源
--------
- `TASKS.md` T-004 验收标准 ①–⑤（逐条对应见下方各处注释）。
- `ARCHITECTURE.md` §2.1 主路径、§4.4/4.5 表结构、§5 批次 JSON 契约、§0 策略 α。
- `HANDOFF.md` T-004 记录的「假设」一节列出本文件采用但未被规格冻结的取舍。

设计取舍（本文档刻意明确，便于复核）
------------------------------------
1. **脱敏在客户端内完成**：本模块把**原文** `MessageDTO` 交给 `client.analyze_batch()`，
   由客户端（T-003）在发送前做策略 α 正则脱敏（验收 ⑤）。本模块同时用
   `client.mask_batch()` 取到「实际会发出去的那份文本」，据此生成 `evidence.quote`，
   保证 `quote` 与发给模型的文本逐字一致（`ARCHITECTURE.md` §4.5）。
2. **证据校验双闸门**（验收 ②③）：`evidence_message_ids` 必须同时
   （a）属于本批消息、（b）存在于 `messages` 表；任一不满足即丢弃该条证据引用。
   丢弃后若某条结论不再有证据，该结论**不入库**（等价于「标 unverified」的另一种落地方式），
   并记入报告与 `result_json.warnings`。
3. **幂等**：`analysis_id` 由 `uuid5(NAMESPACE_URL, f"analysis:{conversation_id}:{batch_index}")`
   确定性生成；已存在的批次直接跳过、不重复调用模型（不覆盖旧行，`ARCHITECTURE.md` §4.6 精神）。
4. **失败即停**：某一批抛 `DeepSeekError` 时记录该批错误并**停止**后续批次（401/超时等
   系统性错误重试只会继续失败，也避免白烧额度）。已写入的前几批保留，报告 `status=failed`。
5. 本模块不创建 `conversations` 行：会话主表的写入属 API 层（`ARCHITECTURE.md` §7 `POST /conversations`）
   与 T-007，T-004 只读 `persons` 以取得 `person_id → A/B` 映射。

日志规范（`PRIVACY.md`）：只记录会话 ID、批次号、`message_id`、条数与错误类型；**不得**记录 `body`。
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from db import get_connection, init_db
from llm import DeepSeekError, validate_profile_json
from llm.deepseek import iter_tendencies
from parser import MessageDTO

from .batch import (
    BATCH_SIZE,
    MIN_MESSAGES_FOR_ANALYSIS,
    Batch,
    BatchPlan,
    InsufficientSampleError,
    field_of,
    plan_batches,
)
from .prompt import PROMPT_VERSION, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# 管道整体状态
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_INSUFFICIENT_SAMPLE = "insufficient_sample"
STATUS_NOTHING_TO_DO = "nothing_to_do"

# 单个批次状态
BATCH_STATUS_WRITTEN = "written"
BATCH_STATUS_SKIPPED_EXISTING = "skipped_existing"
BATCH_STATUS_FAILED = "failed"

# 丢弃结论/证据的原因
REASON_NO_EVIDENCE = "结论未提供任何 evidence_message_ids（无证据的结论不入库）"
REASON_EVIDENCE_NOT_IN_BATCH = "证据 message_id 不在本批消息内（不得跨批次引用）"
REASON_EVIDENCE_NOT_IN_DB = "证据 message_id 在 messages 表中不存在（禁止编造证据）"

QUOTE_MAX_CHARS = 80
_SQL_CHUNK = 500


def _utc_now() -> str:
    """ISO-8601 UTC 字符串（`ARCHITECTURE.md` §4 约定）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _chunks(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def make_analysis_id(conversation_id: str, batch_index: int) -> str:
    """确定性批次 ID：同一会话同批次重复运行得到同一行，便于幂等跳过。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"analysis:{conversation_id}:{int(batch_index)}"))


def make_evidence_id(analysis_id: str, claim_key: str, message_id: str) -> str:
    """确定性证据 ID：同一批次内同一 (结论, 消息) 只会有一行。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"evidence:{analysis_id}:{claim_key}:{message_id}"))


def normalise_quote(text: str, *, limit: int = QUOTE_MAX_CHARS) -> str:
    """把脱敏后的消息正文整理成 `evidence.quote`：折叠空白 + 截断（仍是原文前缀）。

    `ARCHITECTURE.md` §4.5 允许空白规范化；截断只取前缀，故 `quote` 仍是对应文本的子串。
    """
    if not isinstance(text, str):
        raise TypeError("text 必须是字符串")
    collapsed = " ".join(text.split())
    return collapsed[:limit]


# ---------------------------------------------------------------- 数据访问


def _connect(connection: Any | None, db_path: Path | None) -> tuple[Any, bool]:
    """取得连接；自建连接返回 (conn, True)，由调用方负责关闭。"""
    if connection is not None:
        return connection, False
    path = init_db(db_path)  # 幂等：CREATE TABLE IF NOT EXISTS
    return get_connection(path), True


def _existing_message_ids(conn: Any, message_ids: Sequence[str]) -> set[str]:
    """在 messages 表里查这些 ID 是否真实存在（验收 ②「写库时校验 ID 存在」）。"""
    found: set[str] = set()
    for chunk in _chunks(list(message_ids), _SQL_CHUNK):
        placeholders = ",".join("?" * len(chunk))
        cursor = conn.execute(
            f"SELECT message_id FROM messages WHERE message_id IN ({placeholders})",
            list(chunk),
        )
        found.update(row["message_id"] if not isinstance(row, tuple) else row[0] for row in cursor.fetchall())
    return found


def _analysis_exists(conn: Any, analysis_id: str) -> bool:
    cursor = conn.execute("SELECT 1 FROM analyses WHERE id = ?", (analysis_id,))
    return cursor.fetchone() is not None


def _load_person_roles(conn: Any, conversation_id: str) -> dict[str, str]:
    """从 persons 表取 `person_id -> 'A'/'B'`，供客户端解析 `MessageDTO` 的说话人。"""
    cursor = conn.execute("SELECT id, role FROM persons WHERE conversation_id = ?", (conversation_id,))
    roles: dict[str, str] = {}
    for row in cursor.fetchall():
        person_id = row["id"] if not isinstance(row, tuple) else row[0]
        role = row["role"] if not isinstance(row, tuple) else row[1]
        roles[str(person_id)] = str(role)
    return roles


def load_messages(
    conversation_id: str, *, connection: Any | None = None, db_path: Path | None = None
) -> list[MessageDTO]:
    """按 `seq` 升序读出某会话的全部消息（T-002 写入的原文）。"""
    conn, owned = _connect(connection, db_path)
    try:
        cursor = conn.execute(
            "SELECT message_id, conversation_id, person_id, seq, body, source_line"
            " FROM messages WHERE conversation_id = ? ORDER BY seq",
            (conversation_id,),
        )
        rows = cursor.fetchall()
    finally:
        if owned:
            conn.close()
    return [
        MessageDTO(
            message_id=row["message_id"],
            conversation_id=row["conversation_id"],
            person_id=row["person_id"],
            seq=row["seq"],
            body=row["body"],
            source_line=row["source_line"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------- 证据过滤


@dataclass(frozen=True)
class DroppedItem:
    """被丢弃的结论或证据引用（原因随报告一起交给使用者）。"""

    location: str
    claim_key: str
    reason: str
    detail: str = ""


@dataclass
class FilteredProfile:
    """过滤后的画像：只有「证据齐备」的结论会被保留。"""

    profile: dict
    dropped: list[DroppedItem] = field(default_factory=list)

    @property
    def evidence_pairs(self) -> list[tuple[str, str]]:
        """(claim_key, message_id) 有序去重列表。"""
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for _where, tendency in iter_tendencies(self.profile):
            claim_key = str(tendency.get("claim_key"))
            for message_id in tendency.get("evidence_message_ids") or []:
                pair = (claim_key, str(message_id))
                if pair not in seen:
                    seen.add(pair)
                    pairs.append(pair)
        return pairs


def filter_profile(
    profile: Mapping[str, Any],
    *,
    batch_message_ids: Sequence[str],
    db_message_ids: Iterable[str],
    extra_warnings: Sequence[str] = (),
) -> FilteredProfile:
    """按验收 ②③ 过滤模型返回：证据不齐的结论/引用一律不入库。"""
    in_batch = set(batch_message_ids)
    in_db = set(db_message_ids)
    dropped: list[DroppedItem] = []

    def filter_tendency(location: str, tendency: Mapping[str, Any]) -> dict | None:
        claim_key = str(tendency.get("claim_key", ""))
        raw_ids = list(tendency.get("evidence_message_ids") or [])
        if not raw_ids:
            dropped.append(DroppedItem(location, claim_key, REASON_NO_EVIDENCE))
            return None

        kept: list[str] = []
        for message_id in raw_ids:
            if message_id not in in_batch:
                dropped.append(
                    DroppedItem(location, claim_key, REASON_EVIDENCE_NOT_IN_BATCH, str(message_id))
                )
                continue
            if message_id not in in_db:
                dropped.append(
                    DroppedItem(location, claim_key, REASON_EVIDENCE_NOT_IN_DB, str(message_id))
                )
                continue
            if message_id not in kept:
                kept.append(message_id)

        if not kept:
            # 证据全被剔除 → 该结论没有可核对的原文，按「缺少证据不入库」处理
            dropped.append(DroppedItem(location, claim_key, REASON_NO_EVIDENCE))
            return None

        cleaned = dict(tendency)
        cleaned["evidence_message_ids"] = kept
        return cleaned

    def filter_block(location: str, block: Any) -> dict:
        tendencies: list[dict] = []
        if isinstance(block, Mapping):
            for tendency in block.get("tendencies") or []:
                if not isinstance(tendency, Mapping):
                    continue
                kept = filter_tendency(location, tendency)
                if kept is not None:
                    tendencies.append(kept)
        result = dict(block) if isinstance(block, Mapping) else {}
        result["tendencies"] = tendencies
        return result

    persons_in = profile.get("persons") or {}
    persons_out: dict[str, Any] = {}
    for role in ("A", "B"):
        persons_out[role] = filter_block(f"persons.{role}", persons_in.get(role))
    for role, block in (persons_in.items() if isinstance(persons_in, Mapping) else []):
        if role not in persons_out:
            persons_out[str(role)] = filter_block(f"persons.{role}", block)

    cleaned: dict[str, Any] = {
        "schema_version": profile.get("schema_version"),
        "persons": persons_out,
        "dyad": filter_block("dyad", profile.get("dyad")),
        "warnings": [str(w) for w in (profile.get("warnings") or [])],
    }
    for warning in extra_warnings:
        cleaned["warnings"].append(str(warning))
    for item in dropped:
        detail = f"（{item.detail}）" if item.detail else ""
        cleaned["warnings"].append(f"已丢弃 {item.location} / {item.claim_key}：{item.reason}{detail}")
    return FilteredProfile(profile=cleaned, dropped=dropped)


# ---------------------------------------------------------------- 报告


@dataclass(frozen=True)
class BatchOutcome:
    """单个批次的处理结果。"""

    batch_index: int
    status: str
    seq_from: int
    seq_to: int
    sample_size: int
    is_remainder: bool
    analysis_id: str | None = None
    evidence_count: int = 0
    dropped: tuple[DroppedItem, ...] = ()
    error_kind: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in (BATCH_STATUS_WRITTEN, BATCH_STATUS_SKIPPED_EXISTING)


@dataclass
class PipelineReport:
    """`analyze_conversation()` 的完整结果。"""

    status: str
    conversation_id: str | None
    total_messages: int
    batch_size: int = BATCH_SIZE
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    plan_description: str = ""
    batch_outcomes: list[BatchOutcome] = field(default_factory=list)
    analyses_written: int = 0
    evidence_written: int = 0
    batches_skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_COMPLETED

    @property
    def batch_count(self) -> int:
        return len(self.batch_outcomes)

    @property
    def dropped_count(self) -> int:
        return sum(len(outcome.dropped) for outcome in self.batch_outcomes)

    @property
    def message(self) -> str:
        """面向使用者的一句话结论（验收 ④ 要求「样本不足」可见）。"""
        if self.status == STATUS_INSUFFICIENT_SAMPLE:
            return self.warnings[0] if self.warnings else "样本不足：拒绝正式分析。"
        if self.status == STATUS_FAILED:
            return f"分析中断：{'; '.join(self.failures) or '未知错误'}（已完成的批次保留）"
        if self.status == STATUS_NOTHING_TO_DO:
            return "没有可分析的消息。"
        return (
            f"完成：{self.batch_count} 批，写入 analyses {self.analyses_written} 行 / "
            f"evidence {self.evidence_written} 行，丢弃无证据条目 {self.dropped_count} 个。"
        )

    def summary(self) -> str:
        return (
            f"[{self.status}] conversation={self.conversation_id} "
            f"messages={self.total_messages} batches={self.batch_count} "
            f"analyses={self.analyses_written} evidence={self.evidence_written} "
            f"skipped={self.batches_skipped} dropped={self.dropped_count} "
            f"failures={len(self.failures)}"
        )


# ---------------------------------------------------------------- 写库


def persist_batch(
    conn: Any,
    *,
    batch: Batch,
    filtered: FilteredProfile,
    analysis_id: str,
    conversation_id: str,
    model: str,
    prompt_version: str,
    masked_by_id: Mapping[str, str],
    speaker_by_id: Mapping[str, str | None],
    now: str | None = None,
) -> int:
    """写入 1 行 `analyses` + N 行 `evidence`（同一事务），返回 evidence 行数。"""
    created_at = now or _utc_now()
    result_json = json.dumps(filtered.profile, ensure_ascii=False, sort_keys=True)

    with conn:  # 事务：analyses 与它的 evidence 要么都成，要么都不成
        conn.execute(
            "INSERT INTO analyses (id, conversation_id, batch_index, message_id_from, message_id_to,"
            " seq_from, seq_to, model, prompt_version, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                analysis_id,
                conversation_id,
                batch.batch_index,
                batch.message_id_from,
                batch.message_id_to,
                batch.seq_from,
                batch.seq_to,
                model,
                prompt_version,
                result_json,
                created_at,
            ),
        )

        rows = [
            (
                make_evidence_id(analysis_id, claim_key, message_id),
                analysis_id,
                conversation_id,
                claim_key,
                message_id,
                normalise_quote(masked_by_id.get(message_id, "")),
                speaker_by_id.get(message_id),
                created_at,
            )
            for claim_key, message_id in filtered.evidence_pairs
        ]
        if rows:
            conn.executemany(
                "INSERT INTO evidence (id, analysis_id, conversation_id, claim_key, message_id,"
                " quote, speaker_role, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    return len(rows)


# ---------------------------------------------------------------- 主入口


def analyze_conversation(
    messages: Sequence[Any] | Iterable[Any],
    client: Any,
    *,
    conversation_id: str | None = None,
    connection: Any | None = None,
    db_path: Path | None = None,
    system_prompt: str | None = None,
    batch_size: int = BATCH_SIZE,
    min_messages: int = MIN_MESSAGES_FOR_ANALYSIS,
    person_roles: Mapping[str, str] | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> PipelineReport:
    """把消息分批送模型分析并落库（T-004 主入口）。

    验收对应：① 每 50 条一批、余数批照做并记 `sample_size`；② 写库前校验证据 ID 存在；
    ③ 没证据的结论不入库并记录；④ < `min_messages` 直接返回 `insufficient_sample`；
    ⑤ 原文交给客户端，由其在发送前脱敏。
    """
    items = list(messages or [])
    resolved_conversation_id = conversation_id or next(
        (field_of(item, "conversation_id") for item in items if field_of(item, "conversation_id")),
        None,
    )
    prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    report = PipelineReport(
        status=STATUS_NOTHING_TO_DO,
        conversation_id=resolved_conversation_id,
        total_messages=len(items),
        batch_size=batch_size,
        model=getattr(client, "model", None),
        prompt_version=prompt_version,
    )

    try:
        plan: BatchPlan = plan_batches(items, batch_size=batch_size, min_messages=min_messages)
    except InsufficientSampleError as exc:
        logger.warning(
            "analyze_conversation: conversation=%s 样本不足 count=%d min=%d → 拒绝正式分析",
            resolved_conversation_id,
            exc.message_count,
            exc.minimum,
        )
        report.status = STATUS_INSUFFICIENT_SAMPLE
        report.warnings.append(str(exc))
        return report

    report.plan_description = plan.describe()
    if report.conversation_id is None:
        report.conversation_id = plan.conversation_id
    logger.info(
        "analyze_conversation: conversation=%s %s（日志不含正文）",
        report.conversation_id,
        report.plan_description,
    )

    conn, owned = _connect(connection, db_path)
    try:
        roles: dict[str, str] = dict(person_roles or {})
        if not roles and report.conversation_id:
            roles = _load_person_roles(conn, report.conversation_id)

        batch_ids = plan.message_ids
        db_message_ids = _existing_message_ids(conn, batch_ids)
        missing_in_db = [mid for mid in batch_ids if mid not in db_message_ids]
        if missing_in_db:
            report.warnings.append(
                f"{len(missing_in_db)} 条消息不在 messages 表中（对应结论的证据会被丢弃）"
            )

        completed = True
        for batch in plan.batches:
            analysis_id = make_analysis_id(report.conversation_id, batch.batch_index)

            if _analysis_exists(conn, analysis_id):
                logger.info(
                    "analyze_conversation: 批次 %d 已存在（analysis_id=%s），跳过不重复调用模型",
                    batch.batch_index,
                    analysis_id,
                )
                report.batches_skipped += 1
                report.batch_outcomes.append(
                    BatchOutcome(
                        batch_index=batch.batch_index,
                        status=BATCH_STATUS_SKIPPED_EXISTING,
                        seq_from=batch.seq_from,
                        seq_to=batch.seq_to,
                        sample_size=batch.sample_size,
                        is_remainder=batch.is_remainder,
                        analysis_id=analysis_id,
                    )
                )
                continue

            masked = client.mask_batch(
                batch.messages, conversation_id=report.conversation_id, person_roles=roles or None
            )
            masked_by_id = {m.message_id: m.text for m in masked.messages}
            speaker_by_id = {
                str(field_of(message, "message_id")): roles.get(str(field_of(message, "person_id")))
                for message in batch.messages
            }

            try:
                profile = client.analyze_batch(
                    batch.messages,
                    prompt,
                    conversation_id=report.conversation_id,
                    person_roles=roles or None,
                    # 证据由本模块按「本批 + 库内存在」双闸门过滤（见模块 docstring 第 2 条），
                    # 因此不在客户端侧直接判死，以便把越界引用降级为「丢弃 + 记录」。
                    strict_evidence_ids=False,
                )
            except DeepSeekError as exc:
                logger.warning(
                    "analyze_conversation: 批次 %d 失败 kind=%s status=%s，停止后续批次（日志不含正文）",
                    batch.batch_index,
                    exc.kind,
                    exc.status_code,
                )
                report.failures.append(f"batch {batch.batch_index}: {exc.kind}（{exc}）")
                report.batch_outcomes.append(
                    BatchOutcome(
                        batch_index=batch.batch_index,
                        status=BATCH_STATUS_FAILED,
                        seq_from=batch.seq_from,
                        seq_to=batch.seq_to,
                        sample_size=batch.sample_size,
                        is_remainder=batch.is_remainder,
                        error_kind=exc.kind,
                        error_message=str(exc),
                    )
                )
                completed = False
                break

            filtered = filter_profile(
                profile,
                batch_message_ids=batch.message_ids,
                db_message_ids=db_message_ids,
                extra_warnings=[f"本批 sample_size={batch.sample_size}（batch_index={batch.batch_index}）"],
            )
            validate_profile_json(filtered.profile)  # 过滤后再校验一次，防过滤逻辑写坏结构

            evidence_count = persist_batch(
                conn,
                batch=batch,
                filtered=filtered,
                analysis_id=analysis_id,
                conversation_id=report.conversation_id,
                model=getattr(client, "model", "unknown"),
                prompt_version=prompt_version,
                masked_by_id=masked_by_id,
                speaker_by_id=speaker_by_id,
            )

            report.analyses_written += 1
            report.evidence_written += evidence_count
            report.batch_outcomes.append(
                BatchOutcome(
                    batch_index=batch.batch_index,
                    status=BATCH_STATUS_WRITTEN,
                    seq_from=batch.seq_from,
                    seq_to=batch.seq_to,
                    sample_size=batch.sample_size,
                    is_remainder=batch.is_remainder,
                    analysis_id=analysis_id,
                    evidence_count=evidence_count,
                    dropped=tuple(filtered.dropped),
                )
            )
            logger.info(
                "analyze_conversation: 批次 %d 完成 sample=%d evidence=%d dropped=%d",
                batch.batch_index,
                batch.sample_size,
                evidence_count,
                len(filtered.dropped),
            )
    finally:
        if owned:
            conn.close()

    report.status = STATUS_COMPLETED if completed else STATUS_FAILED
    return report


def analyze_conversation_from_db(
    conversation_id: str,
    client: Any,
    *,
    connection: Any | None = None,
    db_path: Path | None = None,
    **kwargs: Any,
) -> PipelineReport:
    """便捷入口：从库中读该会话的消息，再走 `analyze_conversation()`。"""
    messages = load_messages(conversation_id, connection=connection, db_path=db_path)
    return analyze_conversation(
        messages,
        client,
        conversation_id=conversation_id,
        connection=connection,
        db_path=db_path,
        **kwargs,
    )
