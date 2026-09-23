"""T-005 长期画像增量更新：把 T-004 写入的批次 `analyses` 合并成新的 `profile_versions`。

铁律（`ARCHITECTURE.md` §4.6）
-----------------------------
**只 INSERT，绝不 UPDATE / DELETE 任何 `profile_versions` 行。** 修正 = 新 version；
旧版本 `snapshot_json` 必须逐字节可读且不被改写（本模块有专门的单测逐条校验）。

主入口
------
- `update_profile(conversation_id, ...)`：读最新版本 + 该会话全部 `analyses` / `evidence`，
  只把**尚未纳入过**的 `analyses`（按 `batch_index` 升序）折进画像，再写一行新版本。
  没有新批次时返回 `status=nothing_to_do`，**不写行、不升版本**。
- `merge_profile(...)`：纯函数式合并（不碰数据库），便于单测与人工复核。
- `snapshot_to_sections()` / `iter_snapshot_traits()`：把快照摊给 UI（T-006）用。

幂等与去重
----------
快照里记着 `covered_analyses`：同一批 `analyses` 重复合并不会二次累加 `sample_size`，
也不会重复升版本。追加消息后 T-004 会产出新的尾批（`batch_index` 变大），T-005 只折入新批
——既有批次不重算，与 T-004 的幂等键 `(conversation_id, batch_index)` 保持一致。

合并规则本身（四类关系、阈值、聚合方式）在 `pipeline/traits.py`，本模块只负责
「取数 → 归组 → 判定 → 组装快照 → 追加一行」。

快照结构（`snapshot_json`）
--------------------------
```json
{
  "schema_version": "1.0",
  "conversation_id": "conv-1",
  "version": 2,
  "supersedes_version": 1,
  "generated_at": "2026-09-22T10:00:00Z",
  "message_count": 120,
  "rules_version": "1.0",
  "covered_analyses": ["<analysis_id>"],
  "covered_batch_indexes": [0, 1],
  "counts": {"added": 1, "supported": 2, "weakened": 0, "revised": 1,
             "active_traits": 3, "superseded_traits": 1, "total_traits": 4},
  "traits": [
    {"trait_key": "A.request_style", "entry_key": "A.request_style@v1",
     "owner": "A", "statement": "...", "confidence": 0.58, "sample_size": 18,
     "evidence_message_ids": ["msg1", "msg2"],
     "evidence": [{"message_id": "msg1", "quote": "[手机号] ...", "speaker_role": "A"}],
     "support_count": 2, "first_version": 1, "last_updated_version": 2,
     "status": "active", "change_kind": "supported", "sources": ["<analysis_id>"]},
    {"trait_key": "B.reply_style", "entry_key": "B.reply_style@v1", "status": "superseded",
     "superseded_at_version": 2, "superseded_by": "B.reply_style@v2", "...": "..."}
  ],
  "warnings": []
}
```

`traits[].evidence.quote` 是**脱敏后**文本（策略 α，与 T-004 的 `evidence.quote` 同源）；
UI 要展示原文请回查 `messages.body`。

研究模式附加字段（`ARCHITECTURE.md` §5.1）
------------------------------------------
研究模式的 `tendencies[]` 比保守模式多出 `type` / `quote_anchors` / `counter_evidence`。
本模块把它们**原样带进 `traits[]`**（`_group_observations()` 取、`_research_entry_fields()` 折）：

- `type` / `counter_evidence`：取**最新一批**的值（本批没有就沿用旧值）；
- `quote_anchors`：各批**合并去重**（旧的在先）。`revised` 是例外——表述已被改写，
  新条目只带本批锚点，旧锚点留在同一快照里的 `superseded` 行中，两边都不丢；
- 三个字段**有值才写**：保守模式不产出这些字段，因此老数据 / 保守数据的 `traits[]`
  结构与加这个功能之前逐字节一致（不会多出空键）。

`fold_new_observations()` / `combine_observation()` 在 `pipeline/traits.py` 里只认 6 个数值字段，
所以附加字段由本模块自行折叠——这是「不改 traits.py」的前提下唯一干净的接法。
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
from llm.deepseek import iter_tendencies

from .traits import (
    CHANGE_ADDED,
    CHANGE_KINDS,
    CHANGE_REVISED,
    RULES_VERSION,
    ChangeClassification,
    classify_change,
    combine_observation,
    describe_rules,
    fold_new_observations,
    is_well_formed_trait_key,
    make_entry_key,
    merge_unique_ids,
    normalise_trait_key,
    owner_of,
)

logger = logging.getLogger(__name__)

SNAPSHOT_SCHEMA_VERSION = "1.0"

STATUS_MERGED = "completed"
STATUS_NOTHING_TO_DO = "nothing_to_do"

TRAIT_STATUS_ACTIVE = "active"
TRAIT_STATUS_SUPERSEDED = "superseded"

WARNING_MISSING_CLAIM_KEY = "结论缺少 claim_key，已跳过该条"
WARNING_BAD_TRAIT_KEY = "claim_key 不符合 A./B./dyad. 命名规范，按原样保留为 trait_key"
WARNING_EVIDENCE_MISMATCH = "result_json 的 evidence_message_ids 与 evidence 表不一致，以 evidence 表为准"
WARNING_BROKEN_ANALYSIS = "analyses.result_json 无法解析，已跳过该批次（不会计入 covered_analyses）"

_SQL_CHUNK = 500


def _utc_now() -> str:
    """ISO-8601 UTC 字符串（与 T-002/T-004 的写法一致）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _chunks(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def make_profile_id(conversation_id: str, version: int) -> str:
    """确定性版本 ID：同一 (会话, 版本号) 重复运行得到同一行，便于对账。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"profile:{conversation_id}:{int(version)}"))


def _connect(connection: Any | None, db_path: Path | None) -> tuple[Any, bool]:
    """取得连接；自建连接返回 (conn, True)，由调用方负责关闭。"""
    if connection is not None:
        return connection, False
    path = init_db(db_path)  # 幂等：CREATE TABLE IF NOT EXISTS
    return get_connection(path), True


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, tuple):
        return row[index]
    return row[key]
# ---------------------------------------------------------------- 数据模型


def _as_float(value: Any, default: float = 0.0) -> float:
    """宽松取浮点：模型偶尔给字符串或 null，不因此炸掉整次合并。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_text(value: Any) -> str:
    """宽松取字符串：非字符串或全空白一律当「没有该字段」（返回空串）。"""
    if isinstance(value, str):
        return value.strip()
    return ""


@dataclass(frozen=True)
class AnalysisRecord:
    """一行 `analyses`（T-004 的产物，本模块的输入）。"""

    id: str
    conversation_id: str
    batch_index: int
    seq_from: int
    seq_to: int
    model: str = "unknown"
    prompt_version: str = "unknown"
    created_at: str = ""
    profile: Mapping[str, Any] | None = None
    message_id_from: str | None = None
    message_id_to: str | None = None
    parse_error: str | None = None

    @property
    def is_parsed(self) -> bool:
        """`result_json` 是否成功解析为画像对象（解析失败 → 该批跳过且不计入 covered）。"""
        return isinstance(self.profile, Mapping)

    @property
    def message_count(self) -> int:
        return 0 if self.seq_to < self.seq_from else self.seq_to - self.seq_from + 1


@dataclass(frozen=True)
class EvidenceRecord:
    """一行 `evidence`：结论（`claim_key`）→ 消息（`message_id`）的绑定。"""

    id: str
    analysis_id: str
    claim_key: str
    message_id: str
    quote: str = ""
    speaker_role: str | None = None

    def as_meta(self) -> dict:
        return {"quote": self.quote, "speaker_role": self.speaker_role}


@dataclass(frozen=True)
class ProfileVersionRecord:
    """一行 `profile_versions`（**只读**：本模块永不 UPDATE / DELETE 它）。"""

    id: str
    conversation_id: str
    version: int
    snapshot: Mapping[str, Any] | None = None
    changelog: Mapping[str, Any] | None = None
    message_count: int = 0
    created_at: str = ""

    @property
    def _snapshot(self) -> Mapping[str, Any]:
        return self.snapshot if isinstance(self.snapshot, Mapping) else {}

    @property
    def covered_analyses(self) -> list[str]:
        """本版快照已经纳入的 `analyses.id`（T-005 的幂等键，见模块 docstring）。"""
        return merge_unique_ids(self._snapshot.get("covered_analyses"))

    @property
    def covered_batch_indexes(self) -> list[int]:
        values = self._snapshot.get("covered_batch_indexes")
        if not isinstance(values, (list, tuple)):
            return []
        return sorted({_as_int(value) for value in values})

    @property
    def traits(self) -> list[Mapping[str, Any]]:
        values = self._snapshot.get("traits")
        if not isinstance(values, (list, tuple)):
            return []
        return [item for item in values if isinstance(item, Mapping)]

    @property
    def active_traits(self) -> list[Mapping[str, Any]]:
        return [item for item in self.traits if item.get("status") != TRAIT_STATUS_SUPERSEDED]

@dataclass(frozen=True)
class TraitChange:
    """一条 `trait_key` 在本次合并中的变更记录（进 `changelog_json.changes`）。"""

    kind: str
    trait_key: str
    entry_key: str
    statement: str
    previous_statement: str | None = None
    confidence_before: float | None = None
    confidence_after: float = 0.0
    sample_size_before: int | None = None
    sample_size_after: int = 0
    support_count: int = 1
    evidence_message_ids: tuple[str, ...] = ()
    reason: str = ""
    revision_of: Mapping[str, Any] | None = None

    @property
    def owner(self) -> str:
        return owner_of(self.trait_key)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "trait_key": self.trait_key,
            "entry_key": self.entry_key,
            "owner": self.owner,
            "statement": self.statement,
            "previous_statement": self.previous_statement,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "sample_size_before": self.sample_size_before,
            "sample_size_after": self.sample_size_after,
            "support_count": self.support_count,
            "evidence_message_ids": list(self.evidence_message_ids),
            "reason": self.reason,
            "revision_of": dict(self.revision_of) if self.revision_of else None,
        }


@dataclass(frozen=True)
class MergeResult:
    """一次纯合并的产物：新快照 + 新 changelog + 变更明细（尚未落库）。"""

    conversation_id: str
    version: int
    previous_version: int | None
    snapshot: Mapping[str, Any]
    changelog: Mapping[str, Any]
    changes: tuple[TraitChange, ...] = ()

    @property
    def message_count(self) -> int:
        return _as_int(self.snapshot.get("message_count"))

    @property
    def warnings(self) -> list[str]:
        values = self.snapshot.get("warnings")
        return list(values) if isinstance(values, (list, tuple)) else []

    @property
    def change_counts(self) -> dict:
        counts = dict(self.snapshot.get("counts") or {})
        return {kind: _as_int(counts.get(kind)) for kind in CHANGE_KINDS}

    @property
    def total_changes(self) -> int:
        return sum(self.change_counts.values())

    @property
    def active_traits(self) -> list[Mapping[str, Any]]:
        return [
            item
            for item in (self.snapshot.get("traits") or [])
            if isinstance(item, Mapping) and item.get("status") != TRAIT_STATUS_SUPERSEDED
        ]

    def changes_of(self, kind: str) -> list[TraitChange]:
        return [change for change in self.changes if change.kind == kind]


@dataclass
class MergeReport:
    """`update_profile()` 的结果：状态 + 版本号 + 变更摘要 + 落库后的画像 ID。"""

    status: str
    conversation_id: str
    previous_version: int | None = None
    version: int | None = None
    message_count: int = 0
    analyses_used: int = 0
    analyses_skipped: int = 0
    change_counts: Mapping[str, int] | None = None
    changes: tuple[TraitChange, ...] = ()
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    snapshot: Mapping[str, Any] | None = None
    changelog: Mapping[str, Any] | None = None
    profile_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_MERGED

    @property
    def is_nothing_to_do(self) -> bool:
        return self.status == STATUS_NOTHING_TO_DO

    @property
    def total_changes(self) -> int:
        return sum((self.change_counts or {}).values())

    @property
    def active_traits(self) -> list[Mapping[str, Any]]:
        if not isinstance(self.snapshot, Mapping):
            return []
        return [
            item
            for item in (self.snapshot.get("traits") or [])
            if isinstance(item, Mapping) and item.get("status") != TRAIT_STATUS_SUPERSEDED
        ]

    @property
    def message(self) -> str:
        if self.status == STATUS_NOTHING_TO_DO:
            return f"没有新的分析批次：会话 {self.conversation_id} 画像仍为 v{self.previous_version or 0}，未写入新版本"
        if self.status != STATUS_MERGED:
            return f"画像更新未完成（status={self.status}）；{'；'.join(self.failures)}"
        counts = self.change_counts or {}
        detail = "、".join(f"{kind} {_as_int(counts.get(kind))}" for kind in CHANGE_KINDS)
        return f"画像已更新到 v{self.version}（上一版 v{self.previous_version}）：{detail}"

    def summary(self) -> str:
        lines = [self.message, f"覆盖消息 {self.message_count} 条，纳入批次 {self.analyses_used} 个，跳过 {self.analyses_skipped} 个"]
        for warning in self.warnings:
            lines.append(f"warning: {warning}")
        return "\n".join(lines)

# ---------------------------------------------------------------- 读库


def load_analyses(
    conversation_id: str, *, connection: Any | None = None, db_path: Path | None = None
) -> list[AnalysisRecord]:
    """按 `batch_index` 升序读出该会话的全部 `analyses`（含 `result_json` 反序列化）。

    解析失败的批次**不丢弃**：`profile=None` + `parse_error`，由 `update_profile()` 记 warning 后跳过。
    """
    conn, owned = _connect(connection, db_path)
    try:
        rows = conn.execute(
            "SELECT id, conversation_id, batch_index, message_id_from, message_id_to, seq_from, seq_to,"
            " model, prompt_version, result_json, created_at FROM analyses"
            " WHERE conversation_id = ? ORDER BY batch_index, created_at, id",
            (conversation_id,),
        ).fetchall()
    finally:
        if owned:
            conn.close()

    records: list[AnalysisRecord] = []
    for row in rows:
        profile: Mapping[str, Any] | None = None
        parse_error: str | None = None
        raw = _row_value(row, "result_json", 9)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, Mapping):
                profile = parsed
            else:
                parse_error = f"result_json 不是 JSON 对象（{type(parsed).__name__}）"
        except (TypeError, ValueError) as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
        records.append(
            AnalysisRecord(
                id=str(_row_value(row, "id", 0)),
                conversation_id=str(_row_value(row, "conversation_id", 1)),
                batch_index=_as_int(_row_value(row, "batch_index", 2)),
                seq_from=_as_int(_row_value(row, "seq_from", 5)),
                seq_to=_as_int(_row_value(row, "seq_to", 6)),
                model=str(_row_value(row, "model", 7) or "unknown"),
                prompt_version=str(_row_value(row, "prompt_version", 8) or "unknown"),
                created_at=str(_row_value(row, "created_at", 10) or ""),
                profile=profile,
                message_id_from=_row_value(row, "message_id_from", 3),
                message_id_to=_row_value(row, "message_id_to", 4),
                parse_error=parse_error,
            )
        )
    return records


def load_evidence(
    conversation_id: str, *, connection: Any | None = None, db_path: Path | None = None
) -> dict[str, list[EvidenceRecord]]:
    """读出该会话全部 `evidence`，按 `analysis_id` 分组（引用真源，见模块 docstring）。"""
    conn, owned = _connect(connection, db_path)
    try:
        rows = conn.execute(
            "SELECT id, analysis_id, claim_key, message_id, quote, speaker_role FROM evidence"
            " WHERE conversation_id = ? ORDER BY created_at, id",
            (conversation_id,),
        ).fetchall()
    finally:
        if owned:
            conn.close()

    grouped: dict[str, list[EvidenceRecord]] = {}
    for row in rows:
        record = EvidenceRecord(
            id=str(_row_value(row, "id", 0)),
            analysis_id=str(_row_value(row, "analysis_id", 1)),
            claim_key=str(_row_value(row, "claim_key", 2)),
            message_id=str(_row_value(row, "message_id", 3)),
            quote=str(_row_value(row, "quote", 4) or ""),
            speaker_role=_row_value(row, "speaker_role", 5),
        )
        grouped.setdefault(record.analysis_id, []).append(record)
    return grouped


def _row_to_profile_version(row: Any) -> ProfileVersionRecord:
    snapshot: Mapping[str, Any] | None = None
    try:
        parsed = json.loads(_row_value(row, "snapshot_json", 3))
        snapshot = parsed if isinstance(parsed, Mapping) else None
    except (TypeError, ValueError):
        snapshot = None
    changelog: Mapping[str, Any] | None = None
    try:
        parsed_log = json.loads(_row_value(row, "changelog_json", 4))
        changelog = parsed_log if isinstance(parsed_log, Mapping) else None
    except (TypeError, ValueError):
        changelog = None
    return ProfileVersionRecord(
        id=str(_row_value(row, "id", 0)),
        conversation_id=str(_row_value(row, "conversation_id", 1)),
        version=_as_int(_row_value(row, "version", 2)),
        snapshot=snapshot,
        changelog=changelog,
        message_count=_as_int(_row_value(row, "message_count", 5)),
        created_at=str(_row_value(row, "created_at", 6) or ""),
    )


_SELECT_PROFILE_VERSION = (
    "SELECT id, conversation_id, version, snapshot_json, changelog_json, message_count, created_at"
    " FROM profile_versions WHERE conversation_id = ?"
)


def load_profile_versions(
    conversation_id: str, *, connection: Any | None = None, db_path: Path | None = None
) -> list[ProfileVersionRecord]:
    """按 `version` 升序读出该会话的全部画像版本（用于验证「旧版逐字未改」）。"""
    conn, owned = _connect(connection, db_path)
    try:
        rows = conn.execute(f"{_SELECT_PROFILE_VERSION} ORDER BY version", (conversation_id,)).fetchall()
    finally:
        if owned:
            conn.close()
    return [_row_to_profile_version(row) for row in rows]


def load_latest_profile(
    conversation_id: str, *, connection: Any | None = None, db_path: Path | None = None
) -> ProfileVersionRecord | None:
    """取该会话最新一版画像；从未生成过则返回 `None`（首版 = v1）。"""
    conn, owned = _connect(connection, db_path)
    try:
        row = conn.execute(
            f"{_SELECT_PROFILE_VERSION} ORDER BY version DESC LIMIT 1", (conversation_id,)
        ).fetchone()
    finally:
        if owned:
            conn.close()
    return _row_to_profile_version(row) if row is not None else None


def count_covered_messages(conn: Any, conversation_id: str, analyses: Sequence[AnalysisRecord]) -> int:
    """统计这些批次的 `[seq_from, seq_to]` 真正覆盖到的**去重**消息数。"""
    ranges = [(a.seq_from, a.seq_to) for a in analyses if a.seq_to >= a.seq_from]
    if not ranges:
        return 0
    seen: set[str] = set()
    for chunk in _chunks(ranges, _SQL_CHUNK):
        where = " OR ".join(["(seq BETWEEN ? AND ?)"] * len(chunk))
        params: list[Any] = [conversation_id]
        for start, end in chunk:
            params.extend([start, end])
        rows = conn.execute(
            f"SELECT message_id FROM messages WHERE conversation_id = ? AND ({where})", params
        ).fetchall()
        seen.update(str(_row_value(row, "message_id", 0)) for row in rows)
    return len(seen)

# ---------------------------------------------------------------- 观测归组

#: 研究模式（`ARCHITECTURE.md` §5.1）在 `tendencies[]` 上追加的三个字段。
RESEARCH_TRAIT_FIELDS: tuple[str, ...] = ("type", "quote_anchors", "counter_evidence")

#: `type` 的合法取值（仅用于自查；非法值原样带过，不阻断合并）。
TRAIT_TYPE_LABELS: tuple[str, ...] = ("观察", "推断", "猜测")


def _observation_research_fields(tendency: Mapping[str, Any]) -> dict:
    """从单条 `tendency` 取研究模式的三个附加字段（缺哪个不写哪个）。"""
    fields: dict[str, Any] = {}
    label = _as_text(tendency.get("type"))
    if label:
        fields["type"] = label
    anchors = merge_unique_ids(tendency.get("quote_anchors"))
    if anchors:
        fields["quote_anchors"] = anchors
    counter = _as_text(tendency.get("counter_evidence"))
    if counter:
        fields["counter_evidence"] = counter
    return fields


def _fold_research_fields(observations: Sequence[Mapping[str, Any]]) -> dict:
    """把同一 `trait_key` 的多条观测折成一份附加字段（观测按批次升序传入）。

    - `type` / `counter_evidence`：**最新一批**的值（后写覆盖先写）；
    - `quote_anchors`：各批**合并去重**，保持首次出现顺序。
    """
    fields: dict[str, Any] = {}
    anchors: list[str] = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        label = _as_text(observation.get("type"))
        if label:
            fields["type"] = label
        counter = _as_text(observation.get("counter_evidence"))
        if counter:
            fields["counter_evidence"] = counter
        for anchor in merge_unique_ids(observation.get("quote_anchors")):
            if anchor not in anchors:
                anchors.append(anchor)
    if anchors:
        fields["quote_anchors"] = anchors
    return fields


def _research_entry_fields(previous: Mapping[str, Any] | None, fresh: Mapping[str, Any]) -> dict:
    """算出条目最终要写进快照的附加字段。

    - `previous is None`（`added` / `revised`）：只看本批；
    - 否则（`supported` / `weakened`，沿用同一条目）：`type` / `counter_evidence` 用最新一批，
      本批没给就沿用旧值；`quote_anchors` 与旧锚点合并去重（旧的在先）。
    """
    baseline = previous if isinstance(previous, Mapping) else {}
    fields: dict[str, Any] = {}
    label = _as_text(fresh.get("type")) or _as_text(baseline.get("type"))
    if label:
        fields["type"] = label
    anchors = merge_unique_ids(baseline.get("quote_anchors"), fresh.get("quote_anchors"))
    if anchors:
        fields["quote_anchors"] = anchors
    counter = _as_text(fresh.get("counter_evidence")) or _as_text(baseline.get("counter_evidence"))
    if counter:
        fields["counter_evidence"] = counter
    return fields


def _group_observations(
    analyses: Sequence[AnalysisRecord],
    evidence_by_analysis: Mapping[str, Sequence[EvidenceRecord]],
) -> tuple[dict[str, list[dict]], list[str]]:
    """把若干批次里的结论按 `trait_key` 归组，产出待合并的观测列表。

    证据 ID 以 `evidence` 表为**引用真源**（`ARCHITECTURE.md` §4.5）：同一 `claim_key` 下
    表里有行就用表里的 `message_id`（顺带拿到脱敏后的 `quote` 与说话人），表里没有才退回
    `result_json` 里的列表，并把不一致记成 warning（不因此丢弃结论）。
    """
    grouped: dict[str, list[dict]] = {}
    warnings: list[str] = []

    for analysis in analyses:
        if not analysis.is_parsed:
            continue
        rows = list(evidence_by_analysis.get(analysis.id) or [])
        by_claim: dict[str, list[EvidenceRecord]] = {}
        for row in rows:
            by_claim.setdefault(row.claim_key, []).append(row)

        for where, tendency in iter_tendencies(analysis.profile or {}):
            raw_key = tendency.get("claim_key")
            if not isinstance(raw_key, str) or not raw_key.strip():
                warnings.append(f"{WARNING_MISSING_CLAIM_KEY}：analysis={analysis.id}, position={where}")
                continue
            trait_key = normalise_trait_key(raw_key)
            if not is_well_formed_trait_key(trait_key):
                warnings.append(f"{WARNING_BAD_TRAIT_KEY}：{trait_key}（analysis={analysis.id}）")

            declared = merge_unique_ids(tendency.get("evidence_message_ids"))
            table_rows = by_claim.get(raw_key) or by_claim.get(trait_key) or []
            if table_rows:
                from_table = merge_unique_ids([row.message_id for row in table_rows])
                if sorted(from_table) != sorted(declared):
                    warnings.append(
                        f"{WARNING_EVIDENCE_MISMATCH}：{trait_key}（analysis={analysis.id}）"
                    )
                evidence_ids = from_table
                meta = {row.message_id: row.as_meta() for row in table_rows}
            else:
                if declared:
                    warnings.append(
                        f"{WARNING_EVIDENCE_MISMATCH}：{trait_key}（analysis={analysis.id}）"
                    )
                evidence_ids = declared
                meta = {}

            explicit = tendency.get("revision_of")
            grouped.setdefault(trait_key, []).append(
                {
                    "statement": str(tendency.get("statement") or ""),
                    "confidence": _as_float(tendency.get("confidence"), 0.0),
                    "sample_size": _as_int(tendency.get("sample_size"), 0),
                    "evidence_message_ids": evidence_ids,
                    "evidence_meta": meta,
                    "support_count": 1,
                    "sources": [analysis.id],
                    "revision_of": dict(explicit) if isinstance(explicit, Mapping) and explicit else None,
                    # 研究模式附加字段（§5.1）：保守模式下这里是空字典，不产生多余键
                    **_observation_research_fields(tendency),
                }
            )

    return grouped, warnings


def _evidence_payload(
    evidence_ids: Sequence[str],
    meta: Mapping[str, Mapping[str, Any]] | None,
    previous: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict]:
    """按 `evidence_message_ids` 顺序拼出快照里的证据明细（`quote` 已脱敏）。"""
    lookup: dict[str, Mapping[str, Any]] = {}
    for item in previous or []:
        if isinstance(item, Mapping) and isinstance(item.get("message_id"), str):
            lookup.setdefault(str(item["message_id"]), item)
    if isinstance(meta, Mapping):
        for message_id, payload in meta.items():
            if isinstance(message_id, str) and isinstance(payload, Mapping):
                lookup[message_id] = payload

    payloads: list[dict] = []
    for message_id in evidence_ids:
        item = lookup.get(message_id) or {}
        payloads.append(
            {
                "message_id": message_id,
                "quote": str(item.get("quote") or ""),
                "speaker_role": item.get("speaker_role"),
            }
        )
    return payloads


# ---------------------------------------------------------------- 合并主体


def merge_profile(
    *,
    conversation_id: str,
    version: int,
    analyses: Sequence[AnalysisRecord],
    evidence_by_analysis: Mapping[str, Sequence[EvidenceRecord]] | None = None,
    previous: ProfileVersionRecord | None = None,
    message_count: int = 0,
    now: str | None = None,
    extra_warnings: Sequence[str] = (),
    carried_analyses: Sequence[AnalysisRecord] = (),
) -> MergeResult:
    """纯函数：把 `analyses` 折进旧画像，返回**一份新快照**（不碰数据库、不改旧快照）。

    合并规则见 `traits.py`；本函数只负责「判定归属 → 装配快照 → 记 changelog」。
    旧版 `snapshot_json` 不会被读取以外的任何操作影响（`entries` 全部是深一层的拷贝）。
    """
    generated_at = now or _utc_now()
    version = _as_int(version)
    previous_version = previous.version if previous is not None else None
    grouped, warnings = _group_observations(analyses, evidence_by_analysis or {})
    warnings = [*extra_warnings, *warnings]

    entries: dict[str, dict] = {}
    order: list[str] = []
    active_by_trait: dict[str, str] = {}
    if previous is not None:
        for trait in previous.traits:
            entry_key = str(trait.get("entry_key") or "")
            if not entry_key or entry_key in entries:
                continue
            entries[entry_key] = dict(trait)
            order.append(entry_key)
            trait_key = str(trait.get("trait_key") or "")
            if trait_key and trait.get("status") != TRAIT_STATUS_SUPERSEDED:
                active_by_trait.setdefault(trait_key, entry_key)

    changes: list[TraitChange] = []
    for trait_key in sorted(grouped):
        observation = fold_new_observations(grouped[trait_key])
        # `fold_new_observations()` 只认 6 个数值字段，附加字段在这里单独折一份（§5.1）
        research = _fold_research_fields(grouped[trait_key])
        old_entry_key = active_by_trait.get(trait_key)
        old_entry = entries.get(old_entry_key) if old_entry_key else None
        old_view = (
            {
                "statement": old_entry.get("statement"),
                "confidence": old_entry.get("confidence"),
                "sample_size": old_entry.get("sample_size"),
                # 旧证据必须在 combine_observation 里参与合并去重，否则每次增量都会丢掉历史证据
                "evidence_message_ids": old_entry.get("evidence_message_ids"),
                "support_count": old_entry.get("support_count"),
            }
            if old_entry is not None
            else None
        )

        classification = classify_change(old_view, observation)
        kind = classification.kind

        if kind == CHANGE_REVISED:
            new_entry_key = make_entry_key(trait_key, version)
            explicit = observation.get("revision_of")
            revision_of: Mapping[str, Any] | None = None
            if isinstance(explicit, Mapping) and explicit:
                revision_of = dict(explicit)
            if old_entry is not None:
                revision_of = revision_of or {
                    "version": _as_int(
                        old_entry.get("last_updated_version") or old_entry.get("first_version")
                    ),
                    "entry_key": old_entry_key,
                    "trait_key": trait_key,
                    "statement": old_entry.get("statement"),
                    "confidence": old_entry.get("confidence"),
                    "sample_size": old_entry.get("sample_size"),
                }
                # 旧条目**留在同一快照内**并标 superseded；旧版本快照完全不动
                old_entry["status"] = TRAIT_STATUS_SUPERSEDED
                old_entry["superseded_at_version"] = version
                old_entry["superseded_by"] = new_entry_key
            evidence_ids = merge_unique_ids(observation.get("evidence_message_ids"))
            entry = {
                "trait_key": trait_key,
                "entry_key": new_entry_key,
                "owner": owner_of(trait_key),
                "statement": str(observation.get("statement") or ""),
                "confidence": _as_float(observation.get("confidence")),
                "sample_size": _as_int(observation.get("sample_size")),
                "evidence_message_ids": evidence_ids,
                "evidence": _evidence_payload(evidence_ids, observation.get("evidence_meta")),
                "support_count": _as_int(observation.get("support_count"), 1) or 1,
                "first_version": version,
                "last_updated_version": version,
                "status": TRAIT_STATUS_ACTIVE,
                "change_kind": kind,
                "sources": merge_unique_ids(observation.get("sources")),
                "revision_of": revision_of,
            }
            # 表述已改写：新条目只带本批锚点（旧锚点留在同一快照的 superseded 行里）
            entry.update(_research_entry_fields(None, research))
            entries[new_entry_key] = entry
            order.append(new_entry_key)
            active_by_trait[trait_key] = new_entry_key
        else:
            combined = combine_observation(old_view, observation, kind=kind)
            if old_entry is None:
                new_entry_key = make_entry_key(trait_key, version)
                explicit = observation.get("revision_of")
                entry = {
                    "trait_key": trait_key,
                    "entry_key": new_entry_key,
                    "owner": owner_of(trait_key),
                    "statement": combined["statement"],
                    "confidence": combined["confidence"],
                    "sample_size": combined["sample_size"],
                    "evidence_message_ids": combined["evidence_message_ids"],
                    "evidence": _evidence_payload(
                        combined["evidence_message_ids"], observation.get("evidence_meta")
                    ),
                    "support_count": combined["support_count"],
                    "first_version": version,
                    "last_updated_version": version,
                    "status": TRAIT_STATUS_ACTIVE,
                    "change_kind": kind,
                    "sources": merge_unique_ids(observation.get("sources")),
                    "revision_of": dict(explicit) if isinstance(explicit, Mapping) and explicit else None,
                }
                entry.update(_research_entry_fields(None, research))
                entries[new_entry_key] = entry
                order.append(new_entry_key)
                active_by_trait[trait_key] = new_entry_key
            else:
                # supported / weakened：**表述保持旧版**（历史表述不静默漂移），只动数值与证据
                old_entry.update(
                    {
                        "statement": combined["statement"],
                        "confidence": combined["confidence"],
                        "sample_size": combined["sample_size"],
                        "evidence_message_ids": combined["evidence_message_ids"],
                        "support_count": combined["support_count"],
                        "last_updated_version": version,
                        "status": TRAIT_STATUS_ACTIVE,
                        "change_kind": kind,
                        "sources": merge_unique_ids(
                            old_entry.get("sources"), observation.get("sources")
                        ),
                    }
                )
                old_entry["evidence"] = _evidence_payload(
                    combined["evidence_message_ids"],
                    observation.get("evidence_meta"),
                    old_entry.get("evidence"),
                )
                # supported / weakened：type 与 counter_evidence 取最新一批，锚点合并去重（§5.1）
                old_entry.update(_research_entry_fields(old_entry, research))
                entry = old_entry
                new_entry_key = str(old_entry_key)

        changes.append(
            TraitChange(
                kind=kind,
                trait_key=trait_key,
                entry_key=new_entry_key,
                statement=str(entry.get("statement") or ""),
                previous_statement=str(old_view["statement"]) if old_view is not None else None,
                confidence_before=_as_float(old_view["confidence"]) if old_view is not None else None,
                confidence_after=_as_float(entry.get("confidence")),
                sample_size_before=_as_int(old_view["sample_size"]) if old_view is not None else None,
                sample_size_after=_as_int(entry.get("sample_size")),
                support_count=_as_int(entry.get("support_count"), 1),
                evidence_message_ids=tuple(entry.get("evidence_message_ids") or ()),
                reason=classification.reason,
                revision_of=entry.get("revision_of") if isinstance(entry.get("revision_of"), Mapping) else None,
            )
        )

    counts = {kind: sum(1 for change in changes if change.kind == kind) for kind in CHANGE_KINDS}
    traits = [entries[entry_key] for entry_key in order]
    counts["active_traits"] = sum(
        1 for trait in traits if trait.get("status") != TRAIT_STATUS_SUPERSEDED
    )
    counts["superseded_traits"] = sum(
        1 for trait in traits if trait.get("status") == TRAIT_STATUS_SUPERSEDED
    )
    counts["total_traits"] = len(traits)

    previous_batches = previous.covered_batch_indexes if previous is not None else []
    fresh_batches = sorted({_as_int(a.batch_index) for a in [*carried_analyses, *analyses]})
    covered_batches = sorted(set(previous_batches) | set(fresh_batches))
    covered = merge_unique_ids(
        previous.covered_analyses if previous is not None else [],
        [a.id for a in carried_analyses],
        [a.id for a in analyses],
    )

    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "conversation_id": conversation_id,
        "version": version,
        "supersedes_version": previous_version,
        "generated_at": generated_at,
        "message_count": _as_int(message_count),
        "rules_version": RULES_VERSION,
        "covered_analyses": covered,
        "covered_batch_indexes": covered_batches,
        "counts": counts,
        "traits": traits,
        "warnings": warnings,
    }
    changelog = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "previous_version": previous_version,
        "version": version,
        "generated_at": generated_at,
        "message_count": _as_int(message_count),
        "based_on_analyses": [a.id for a in analyses],
        "batch_indexes": sorted({_as_int(a.batch_index) for a in analyses}),
        "change_counts": dict(counts),
        "rules": describe_rules(),
        "changes": {
            kind: [change.as_dict() for change in changes if change.kind == kind]
            for kind in CHANGE_KINDS
        },
        "warnings": warnings,
    }
    return MergeResult(
        conversation_id=conversation_id,
        version=version,
        previous_version=previous_version,
        snapshot=snapshot,
        changelog=changelog,
        changes=tuple(changes),
    )


# ---------------------------------------------------------------- 落库


def persist_profile_version(conn: Any, result: MergeResult, *, now: str | None = None) -> str:
    """把合并结果写成**一行新的** `profile_versions`，返回该行 `id`。

    `ARCHITECTURE.md` §4.6：只 INSERT。本函数里没有、也不允许出现 UPDATE / DELETE。
    """
    profile_id = make_profile_id(result.conversation_id, result.version)
    with conn:
        conn.execute(
            "INSERT INTO profile_versions"
            " (id, conversation_id, version, snapshot_json, changelog_json, message_count, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                profile_id,
                result.conversation_id,
                _as_int(result.version),
                json.dumps(result.snapshot, ensure_ascii=False, sort_keys=True),
                json.dumps(result.changelog, ensure_ascii=False, sort_keys=True),
                result.message_count,
                now or _utc_now(),
            ),
        )
    return profile_id


def update_profile(
    conversation_id: str,
    *,
    connection: Any | None = None,
    db_path: Path | None = None,
    analyses: Sequence[AnalysisRecord] | None = None,
    evidence_by_analysis: Mapping[str, Sequence[EvidenceRecord]] | None = None,
    previous: ProfileVersionRecord | None = None,
    now: str | None = None,
) -> MergeReport:
    """主入口：读旧版 + 读该会话全部 `analyses` → 只折入新批次 → 追加一行新版本。

    幂等（`ARCHITECTURE.md` §6）：已经出现在上一版 `snapshot.covered_analyses` 里的批次不再重算，
    因此重复调用不会重复累加 `sample_size`、也不会重复升版本；没有新批次时返回
    `status=nothing_to_do` 且**不写任何行**。日志只记会话 ID、版本号、批次号与条数，不含正文。
    """
    conn, owned = _connect(connection, db_path)
    try:
        loaded_from_db = analyses is None
        all_analyses = list(analyses) if analyses is not None else load_analyses(conversation_id, connection=conn)
        evidence_map = (
            dict(evidence_by_analysis)
            if evidence_by_analysis is not None
            else load_evidence(conversation_id, connection=conn)
        )
        if previous is None:
            previous = load_latest_profile(conversation_id, connection=conn)

        mismatched = [a.id for a in all_analyses if a.conversation_id != conversation_id]
        if mismatched:
            raise ValueError(
                f"analyses 属于其它会话，已拒绝合并：{mismatched[:3]}（共 {len(mismatched)} 条）"
            )

        covered_before = set(previous.covered_analyses) if previous is not None else set()
        fresh: list[AnalysisRecord] = []
        skipped: list[AnalysisRecord] = []
        warnings: list[str] = []
        for analysis in all_analyses:
            if not analysis.is_parsed:
                warnings.append(
                    f"{WARNING_BROKEN_ANALYSIS}：analysis={analysis.id}"
                    f"（batch_index={analysis.batch_index}, {analysis.parse_error}）"
                )
                continue
            if analysis.id in covered_before:
                skipped.append(analysis)
                continue
            fresh.append(analysis)

        previous_version = previous.version if previous is not None else None
        if not fresh:
            logger.info(
                "update_profile: 会话 %s 没有新批次（已覆盖 %d 个），沿用 v%s",
                conversation_id,
                len(skipped),
                previous_version,
            )
            return MergeReport(
                status=STATUS_NOTHING_TO_DO,
                conversation_id=conversation_id,
                previous_version=previous_version,
                version=previous_version,
                message_count=previous.message_count if previous is not None else 0,
                analyses_used=0,
                analyses_skipped=len(skipped),
                change_counts={kind: 0 for kind in CHANGE_KINDS},
                changes=(),
                warnings=warnings,
                snapshot=previous.snapshot if previous is not None else None,
                changelog=previous.changelog if previous is not None else None,
                profile_id=previous.id if previous is not None else None,
            )

        version = (previous_version or 0) + 1
        if loaded_from_db:
            by_id = {analysis.id: analysis for analysis in all_analyses}
            covered_ids = merge_unique_ids(
                previous.covered_analyses if previous is not None else [],
                [a.id for a in fresh],
            )
            message_count = count_covered_messages(
                conn, conversation_id, [by_id[i] for i in covered_ids if i in by_id]
            )
        else:
            message_count = (previous.message_count if previous is not None else 0) + count_covered_messages(
                conn, conversation_id, fresh
            )

        result = merge_profile(
            conversation_id=conversation_id,
            version=version,
            analyses=fresh,
            evidence_by_analysis=evidence_map,
            previous=previous,
            message_count=message_count,
            now=now,
            extra_warnings=warnings,
            carried_analyses=skipped,
        )
        profile_id = persist_profile_version(conn, result, now=now)
    finally:
        if owned:
            conn.close()

    logger.info(
        "update_profile: 会话 %s 由 v%s 升到 v%d（新批次 %d 个，跳过 %d 个，覆盖消息 %d 条）",
        conversation_id,
        previous_version,
        result.version,
        len(fresh),
        len(skipped),
        result.message_count,
    )
    return MergeReport(
        status=STATUS_MERGED,
        conversation_id=conversation_id,
        previous_version=result.previous_version,
        version=result.version,
        message_count=result.message_count,
        analyses_used=len(fresh),
        analyses_skipped=len(skipped),
        change_counts=result.change_counts,
        changes=result.changes,
        warnings=list(result.warnings),
        snapshot=result.snapshot,
        changelog=result.changelog,
        profile_id=profile_id,
    )


# ---------------------------------------------------------------- 快照读取


def iter_snapshot_traits(
    snapshot: Mapping[str, Any] | None, *, include_superseded: bool = False
) -> list[Mapping[str, Any]]:
    """取快照里的条目（默认只给 active；`include_superseded=True` 连历史条目一起给）。"""
    if not isinstance(snapshot, Mapping):
        return []
    traits = snapshot.get("traits")
    if not isinstance(traits, (list, tuple)):
        return []
    result = []
    for item in traits:
        if not isinstance(item, Mapping):
            continue
        if not include_superseded and item.get("status") == TRAIT_STATUS_SUPERSEDED:
            continue
        result.append(item)
    return result


def snapshot_to_sections(
    snapshot: Mapping[str, Any] | None, *, include_superseded: bool = False
) -> dict[str, list[Mapping[str, Any]]]:
    """按归属（A / B / dyad / other）切分快照条目，供 UI（T-006）分栏展示。"""
    sections: dict[str, list[Mapping[str, Any]]] = {"A": [], "B": [], "dyad": [], "other": []}
    for item in iter_snapshot_traits(snapshot, include_superseded=include_superseded):
        owner = owner_of(item.get("trait_key"))
        sections.get(owner, sections["other"]).append(item)
    return sections