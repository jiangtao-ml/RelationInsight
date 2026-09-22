"""T-007 隐私模块：同意写入 / 一键删除 / 残留检查。

规格来源
--------
- `PRIVACY.md` §1.2：同意记录**只写**时间 / 会话 ID / 同意范围（枚举）/ 同意书文案版本号；
  禁止写聊天原文、真实姓名、证件号。
- `PRIVACY.md` §1.3：同意书文案——本模块 `CONSENT_STATEMENT` 与之一字不差；
  **不要在别处复制改写**，前端直接引用本常量（`ARCHITECTURE.md` §4.7）。
- `PRIVACY.md` §2.1–§2.3：删除范围（含 `evidence.quote` 等原文副本）、二次确认、事务删除 +
  `VACUUM`、「删不掉的部分」披露文案（见 `deletion_disclosures()`）。
- `PRIVACY.md` §4.2 日志：只允许会话 ID / 消息条数 / 批次号 / `message_id` / 错误码 / 耗时；
  **禁止** `body`、quote、含原文的完整 prompt。
- `ARCHITECTURE.md` §7：删除接口只返回**无原文回执**（时间 + 范围 + 各表行数 + 残留结论）。
- `ARCHITECTURE.md` §8：脱敏实现统一收敛到本模块（`mask_for_model()`），避免两处正则漂移。
- `TASKS.md` T-007 验收 ①–④。

设计要点
--------
1. **同意**：`record_consent()` 写 `consents` 行；「有效同意」= `granted=1` 且 `revoked_at IS NULL`；
   `require_consent()` 是分析入口的门闩（抛 `PrivacyError(kind=no_consent)` → API 403）。
2. **删除**：单事务内按外键安全顺序删 7 张表（`evidence` → … → `conversations`）；提交后
   `VACUUM`，并清理 `-wal` / `-shm` / `-journal` 临时文件。
3. **残留检查**：对 db 文件（含临时文件）做**字节级**检索，只报告「文件名 + 命中数」，
   **不回显**命中内容，也**不**把被检索的原文写进日志。
4. **审计**：删除后追加一行 JSON（时间 / 范围 / 各表行数 / 残留结论），**不含原文**。

本模块不联网、不调用模型；数据库访问一律走 `db.get_connection()`（同步 `sqlite3`）。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from db import DATA_DIR, DB_PATH, get_connection
from llm.deepseek import MASK_RULES, mask_text, mask_text_with_count

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- 同意书（唯一来源）

#: 同意书文案版本号（`PRIVACY.md` §1.2 要求记录「使用者确认勾选的版本号」）。
CONSENT_STATEMENT_VERSION = "v0.1-2026-09-21"

#: 文案出处，便于审计与人工复核。
CONSENT_STATEMENT_SOURCE = "PRIVACY.md §1.3"

#: **逐字**取自 `PRIVACY.md` §1.3（含标点）。改动必须同步改 PRIVACY.md 并升版本号。
CONSENT_STATEMENT = (
    "我确认这是我有权处理的对话；若分析涉及另一方，我已告知并获得其同意。"
    "我理解输出不是心理诊断或法律结论。"
    "我理解文本将发送至 DeepSeek API 进行分析，并受该服务商条款约束。"
    "我可以随时一键删除本地数据。"
)

#: 同意范围枚举（`PRIVACY.md` §1.2）。
SCOPE_BOTH_PARTIES = "both_parties_informed"
SCOPE_SELF_ONLY = "self_only"
VALID_SCOPES: tuple[str, ...] = (SCOPE_BOTH_PARTIES, SCOPE_SELF_ONLY)
DEFAULT_SCOPE = SCOPE_BOTH_PARTIES

#: 删除范围标识（全库删除用；见 `ARCHITECTURE.md` §7）。
SCOPE_ALL_DATA = "all_data"

# ---------------------------------------------------------------- 错误类型（→ API 4xx）

ERROR_NO_CONSENT = "no_consent"
ERROR_INVALID_SCOPE = "invalid_scope"
ERROR_INVALID_CONVERSATION_ID = "invalid_conversation_id"
ERROR_STALE_STATEMENT = "stale_consent_statement"
ERROR_CONFIRMATION_REQUIRED = "confirmation_required"
ERROR_UNKNOWN_CONVERSATION = "unknown_conversation"
ERROR_RESIDUAL_DATA = "residual_data"

DEFAULT_STATUS: dict[str, int] = {
    ERROR_NO_CONSENT: 403,
    ERROR_INVALID_SCOPE: 400,
    ERROR_INVALID_CONVERSATION_ID: 400,
    ERROR_STALE_STATEMENT: 400,
    ERROR_CONFIRMATION_REQUIRED: 400,
    ERROR_UNKNOWN_CONVERSATION: 404,
    ERROR_RESIDUAL_DATA: 500,
}


class PrivacyError(RuntimeError):
    """统一错误类型：同意缺失 / 范围非法 / 未二次确认 / 会话不存在 / 残留未清。

    约定：`detail` 与 `str(error)` **不得**包含聊天原文（只出现 ID、表名、行数、状态）。
    """

    def __init__(self, kind: str, detail: str, *, status_code: int | None = None) -> None:
        super().__init__(f"[{kind}] {detail}")
        self.kind = kind
        self.detail = detail
        self.status_code = status_code if status_code is not None else DEFAULT_STATUS.get(kind, 400)


# ---------------------------------------------------------------- 常量

#: 删除顺序（外键安全）。`conversations` 自身用 `id` 匹配，其余用 `conversation_id`。
TABLE_KEYS: tuple[tuple[str, str], ...] = (
    ("evidence", "conversation_id"),
    ("analyses", "conversation_id"),
    ("profile_versions", "conversation_id"),
    ("messages", "conversation_id"),
    ("persons", "conversation_id"),
    ("consents", "conversation_id"),
    ("conversations", "id"),
)

#: 五张业务表 + `conversations` + 同意表——验收 ② 要求删除后**均**无该范围行。
DELETED_TABLES: tuple[str, ...] = tuple(name for name, _ in TABLE_KEYS)

#: 需要一并清理的 SQLite 临时文件后缀（WAL / 共享内存 / 回滚日志）。
TEMP_SUFFIXES: tuple[str, ...] = ("-wal", "-shm", "-journal")

#: 残留检查用的最短 needle 长度：太短的串（如「好」「嗯」）会全库误命中，无判别力。
MIN_NEEDLE_CHARS = 6

#: 单次残留检查最多取多少个 needle（避免超长会话把删除流程拖慢）。
MAX_NEEDLES = 200

#: 删除审计文件（只记时间 / 范围 / 行数，永不含原文）。
AUDIT_FILE_NAME = "deletion_audit.jsonl"


def _now() -> str:
    """UTC 时间戳（秒级，ISO 8601，带 Z）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _connect(db_path: Path | None) -> tuple[sqlite3.Connection, bool]:
    """返回 `(连接, 是否本函数创建)`；调用方只在 `owned=True` 时负责关闭。"""
    if db_path is None:
        return get_connection(), True
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return get_connection(path), True


def _begin(conn: sqlite3.Connection) -> bool:
    """尽量开一个显式事务；调用方已开事务时复用（返回 False）。"""
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
        return True
    return False


# ---------------------------------------------------------------- 脱敏（统一入口）


def mask_for_model(text: str) -> str:
    """策略 α 脱敏的**唯一入口**（`ARCHITECTURE.md` §8）。

    实现直接复用 `llm.deepseek.mask_text`：只替换手机号 / 邮箱 / 身份证号 / 银行卡号 4 类，
    不复制正则，避免两处漂移。`messages.body` 恒存原文，只有发给模型/写入 `evidence.quote`
    的文本走本函数。
    """
    return mask_text(text)


def mask_for_model_with_count(text: str) -> tuple[str, int]:
    """同 `mask_for_model()`，额外返回替换处数（用于统计，不用于日志回显原文）。"""
    return mask_text_with_count(text)


def masking_rules() -> tuple[str, ...]:
    """当前生效的脱敏规则名（供 UI/文档展示，如 `phone` / `email` / `id_card` / `bank_card`）。"""
    return tuple(name for name, _pattern, _placeholder in MASK_RULES)


# ---------------------------------------------------------------- 同意


@dataclass(frozen=True)
class ConsentRecord:
    """`consents` 表的一行（**不含**原文；`note` 只记文案版本号与范围）。"""

    id: str
    conversation_id: str
    granted: int
    scope: str | None
    note: str | None
    created_at: str
    revoked_at: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.granted == 1 and not self.revoked_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "granted": bool(self.granted),
            "scope": self.scope,
            "note": self.note,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
            "valid": self.is_valid,
        }


@dataclass(frozen=True)
class _Row:
    """`sqlite3.Row` → dict 的最小包装，避免各处重复写 `dict(row)`。"""

    data: dict[str, Any]


def consent_statement() -> dict[str, str]:
    """返回同意书文案（逐字取自 `PRIVACY.md` §1.3）+ 版本号 + 出处。"""
    return {
        "text": CONSENT_STATEMENT,
        "version": CONSENT_STATEMENT_VERSION,
        "source": CONSENT_STATEMENT_SOURCE,
    }


def consent_note(*, scope: str, statement_version: str = CONSENT_STATEMENT_VERSION) -> str:
    """`consents.note` 的内容：只记文案版本号与范围，**不**记原文。"""
    return f"statement_version={statement_version}; scope={scope}"


def make_consent_id(conversation_id: str, created_at: str, scope: str) -> str:
    """确定性 ID（与 message_id / person_id 同一风格），便于重复导入时幂等去重。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"consent:{conversation_id}:{scope}:{created_at}"))


def _validate_conversation_id(conversation_id: str) -> str:
    value = (conversation_id or "").strip()
    if not value:
        raise PrivacyError(ERROR_INVALID_CONVERSATION_ID, "conversation_id 不能为空")
    return value


def _validate_scope(scope: str) -> str:
    if scope not in VALID_SCOPES:
        raise PrivacyError(
            ERROR_INVALID_SCOPE,
            f"scope 必须是 {list(VALID_SCOPES)} 之一（见 PRIVACY.md §1.2）",
        )
    return scope


def record_consent(
    conversation_id: str,
    *,
    scope: str = DEFAULT_SCOPE,
    granted: bool = True,
    statement_version: str = CONSENT_STATEMENT_VERSION,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> ConsentRecord:
    """把 UI 勾选写入 `consents`（`PRIVACY.md` §1.2）。

    - 只写：时间 / 会话 ID / 范围 / 文案版本号（进 `note`）。
    - `granted=False` 时写一行「未同意」记录后立即 `revoked_at` 标记（保持历史可审计）。
    """
    conversation_id = _validate_conversation_id(conversation_id)
    scope = _validate_scope(scope)
    if statement_version != CONSENT_STATEMENT_VERSION:
        raise PrivacyError(
            ERROR_STALE_STATEMENT,
            "同意书文案版本已更新，请重新阅读并勾选最新文案"
            f"（当前版本 {CONSENT_STATEMENT_VERSION}）",
        )

    created_at = _now()
    record = ConsentRecord(
        id=make_consent_id(conversation_id, created_at, scope),
        conversation_id=conversation_id,
        granted=1 if granted else 0,
        scope=scope,
        note=consent_note(scope=scope, statement_version=statement_version),
        created_at=created_at,
        revoked_at=None if granted else created_at,
    )

    conn, owned = _connect(db_path) if connection is None else (connection, False)
    try:
        if owned:
            _begin(conn)
        conn.execute(
            "INSERT OR REPLACE INTO consents"
            " (id, conversation_id, granted, scope, note, created_at, revoked_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.conversation_id,
                record.granted,
                record.scope,
                record.note,
                record.created_at,
                record.revoked_at,
            ),
        )
        if owned:
            conn.commit()
    finally:
        if owned:
            conn.close()

    logger.info(
        "record_consent: conversation=%s scope=%s granted=%d statement_version=%s",
        conversation_id,
        scope,
        record.granted,
        statement_version,
    )
    return record


def revoke_consent(
    conversation_id: str,
    *,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> int:
    """撤回同意（`PRIVACY.md` §1.4）：写 `revoked_at`，保留行以便回看同意历史。"""
    conversation_id = _validate_conversation_id(conversation_id)
    conn, owned = _connect(db_path) if connection is None else (connection, False)
    try:
        if owned:
            _begin(conn)
        cursor = conn.execute(
            "UPDATE consents SET revoked_at = ?"
            " WHERE conversation_id = ? AND granted = 1 AND revoked_at IS NULL",
            (_now(), conversation_id),
        )
        changed = cursor.rowcount or 0
        if owned:
            conn.commit()
    finally:
        if owned:
            conn.close()
    logger.info("revoke_consent: conversation=%s rows=%d", conversation_id, changed)
    return changed


def load_consents(
    conversation_id: str,
    *,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> list[ConsentRecord]:
    """按时间升序读取该会话的同意行。"""
    conversation_id = _validate_conversation_id(conversation_id)
    conn, owned = _connect(db_path) if connection is None else (connection, False)
    try:
        rows = conn.execute(
            "SELECT id, conversation_id, granted, scope, note, created_at, revoked_at"
            " FROM consents WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()
    finally:
        if owned:
            conn.close()
    return [
        ConsentRecord(
            id=row["id"],
            conversation_id=row["conversation_id"],
            granted=row["granted"],
            scope=row["scope"],
            note=row["note"],
            created_at=row["created_at"],
            revoked_at=row["revoked_at"],
        )
        for row in rows
    ]


def has_valid_consent(
    conversation_id: str,
    *,
    scope: str | None = None,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> bool:
    """有效同意 = 至少一行 `granted=1` 且 `revoked_at IS NULL`。"""
    conversation_id = (conversation_id or "").strip()
    if not conversation_id:
        return False
    if scope is not None:
        _validate_scope(scope)
    conn, owned = _connect(db_path) if connection is None else (connection, False)
    try:
        sql = (
            "SELECT COUNT(*) AS c FROM consents"
            " WHERE conversation_id = ? AND granted = 1 AND revoked_at IS NULL"
        )
        params: list[Any] = [conversation_id]
        if scope is not None:
            sql += " AND scope = ?"
            params.append(scope)
        row = conn.execute(sql, params).fetchone()
        return bool(row["c"])
    finally:
        if owned:
            conn.close()


def require_consent(
    conversation_id: str,
    *,
    scope: str | None = None,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> ConsentRecord:
    """分析入口门闩（验收 ①）：无有效同意则抛 `PrivacyError(no_consent)` → API `403`。"""
    conversation_id = _validate_conversation_id(conversation_id)
    for record in load_consents(conversation_id, connection=connection, db_path=db_path):
        if record.is_valid and (scope is None or record.scope == scope):
            logger.info(
                "require_consent: conversation=%s scope=%s -> ok (consent_id=%s)",
                conversation_id,
                record.scope,
                record.id,
            )
            return record
    logger.info("require_consent: conversation=%s -> denied (no valid consent)", conversation_id)
    raise PrivacyError(
        ERROR_NO_CONSENT,
        "该会话没有有效同意（consents 中无 granted=1 且未撤回的行）；"
        "按 PRIVACY.md §1.1 不得调用分析管道",
    )


# ---------------------------------------------------------------- 删除


@dataclass(frozen=True)
class ResidualReport:
    """残留检查结论：只报告「文件名 + 命中数」，**不含**命中内容。"""

    clean: bool
    checked_needles: int
    scanned_files: tuple[str, ...]
    hit_files: tuple[str, ...]
    hits: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "checked_needles": self.checked_needles,
            "scanned_files": list(self.scanned_files),
            "hit_files": list(self.hit_files),
            "hits": self.hits,
        }


@dataclass(frozen=True)
class DeletionReceipt:
    """删除回执（`PRIVACY.md` §2.2 / `ARCHITECTURE.md` §7）：时间 + 范围，**不回显原文**。"""

    scope: str
    deleted_at: str
    deleted_rows: dict[str, int] = field(default_factory=dict)
    vacuumed: bool = False
    temp_files_removed: tuple[str, ...] = ()
    residual: ResidualReport | None = None
    audit_path: str | None = None

    @property
    def total_rows(self) -> int:
        return sum(self.deleted_rows.values())

    @property
    def message(self) -> str:
        tables = "、".join(f"{name} {count}" for name, count in self.deleted_rows.items())
        if self.scope == SCOPE_ALL_DATA:
            head = "已清空本机全部数据"
        else:
            head = f"已删除会话 {self.scope} 的本地数据"
        vacuum = "VACUUM 已执行" if self.vacuumed else "VACUUM 未执行"
        clean = "残留检查通过（0 命中）" if (self.residual and self.residual.clean) else "残留检查未通过"
        return f"{head}（{self.deleted_at}）：{tables}；{vacuum}；{clean}。"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "deleted_at": self.deleted_at,
            "deleted_rows": dict(self.deleted_rows),
            "total_rows": self.total_rows,
            "vacuumed": self.vacuumed,
            "temp_files_removed": list(self.temp_files_removed),
            "residual": self.residual.to_dict() if self.residual else None,
            "audit_path": self.audit_path,
            "message": self.message,
        }


def temp_file_paths(db_path: Path) -> tuple[Path, ...]:
    path = Path(db_path)
    return tuple(Path(f"{path}{suffix}") for suffix in TEMP_SUFFIXES)


def check_residuals(
    db_path: Path,
    needles: Iterable[str],
    *,
    min_chars: int = MIN_NEEDLE_CHARS,
    extra_paths: Sequence[Path] = (),
) -> ResidualReport:
    """字节级残留检查：确认已删原文片段在 db 文件（含 WAL/SHM/日志）**0 命中**。

    - 只返回文件名与命中数；**不**返回命中片段、**不**记录被检索的原文。
    - needle 短于 `min_chars` 时跳过（无判别力，避免误报）。
    """
    path = Path(db_path)
    seen: set[str] = set()
    cleaned: list[str] = []
    for needle in needles:
        text = (needle or "").strip()
        if len(text) < min_chars or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    payloads = [text.encode("utf-8") for text in cleaned]

    candidates: list[Path] = [path]
    for extra in temp_file_paths(path):
        candidates.append(extra)
    candidates.extend(Path(p) for p in extra_paths)

    scanned: list[str] = []
    hit_files: list[str] = []
    hits = 0
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        data = candidate.read_bytes()
        found = sum(data.count(payload) for payload in payloads)
        scanned.append(candidate.name)
        if found:
            hit_files.append(candidate.name)
            hits += found
    return ResidualReport(
        clean=hits == 0,
        checked_needles=len(payloads),
        scanned_files=tuple(scanned),
        hit_files=tuple(hit_files),
        hits=hits,
    )


def collect_needles(
    conversation_id: str | None,
    *,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
    min_chars: int = MIN_NEEDLE_CHARS,
    limit: int = MAX_NEEDLES,
) -> tuple[str, ...]:
    """取删除前用于残留校验的原文片段（仅在内存中使用，**不**写日志、**不**落库）。

    `conversation_id=None` 表示全库（`DELETE /data`）。
    """
    conn, owned = _connect(db_path) if connection is None else (connection, False)
    try:
        if conversation_id is None:
            rows = conn.execute("SELECT body FROM messages ORDER BY seq ASC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT body FROM messages WHERE conversation_id = ? ORDER BY seq ASC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
    finally:
        if owned:
            conn.close()
    needles: list[str] = []
    for row in rows:
        body = (row["body"] or "").strip()
        if len(body) >= min_chars:
            needles.append(body)
    return tuple(needles)


def _cleanup_temp_files(db_path: Path) -> tuple[str, ...]:
    """删除 `-wal` / `-shm` / `-journal`（已关闭连接后调用；失败不致命）。"""
    removed: list[str] = []
    for candidate in temp_file_paths(db_path):
        try:
            if candidate.exists():
                candidate.unlink()
                removed.append(candidate.name)
        except OSError:  # pragma: no cover - 文件被占用时跳过，残留检查会如实报告
            logger.warning("delete: 临时文件无法删除 path=%s", candidate.name)
    return tuple(removed)


def _table_counts(conn: sqlite3.Connection, conversation_id: str | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table, column in TABLE_KEYS:
        if conversation_id is None:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
        else:
            row = conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE {column} = ?", (conversation_id,)
            ).fetchone()
        counts[table] = int(row["c"])
    return counts


def _delete_rows(conn: sqlite3.Connection, conversation_id: str | None) -> dict[str, int]:
    counts = _table_counts(conn, conversation_id)
    for table, column in TABLE_KEYS:
        if conversation_id is None:
            conn.execute(f"DELETE FROM {table}")
        else:
            conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (conversation_id,))
    return counts


def write_audit(receipt: DeletionReceipt, audit_path: Path | None = None) -> str:
    """追加一条**无原文**审计记录：时间 / 范围 / 各表行数 / 残留结论。"""
    path = Path(audit_path) if audit_path is not None else (DATA_DIR / AUDIT_FILE_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "delete",
        "deleted_at": receipt.deleted_at,
        "scope": receipt.scope,
        "deleted_rows": dict(receipt.deleted_rows),
        "total_rows": receipt.total_rows,
        "vacuumed": receipt.vacuumed,
        "temp_files_removed": list(receipt.temp_files_removed),
        "residual_clean": bool(receipt.residual.clean) if receipt.residual else None,
        "note": "audit only: no plaintext recorded",
    }
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)


def _delete_scope(
    conversation_id: str | None,
    *,
    confirmed: bool,
    needles: Iterable[str] | None,
    connection: sqlite3.Connection | None,
    db_path: Path | None,
    audit_path: Path | None,
    vacuum: bool,
) -> DeletionReceipt:
    if not confirmed:
        raise PrivacyError(
            ERROR_CONFIRMATION_REQUIRED,
            "删除必须二次确认（勾选「我理解不可恢复」后带 confirm=true 再调用；见 PRIVACY.md §2.2）",
        )

    resolved_db_path = Path(db_path) if db_path is not None else DB_PATH
    conn = connection if connection is not None else get_connection(resolved_db_path)
    owned = connection is None
    try:
        if conversation_id is not None:
            exists = conn.execute(
                "SELECT COUNT(*) AS c FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()["c"]
            rows_present = any(_table_counts(conn, conversation_id).values())
            if not exists and not rows_present:
                raise PrivacyError(
                    ERROR_UNKNOWN_CONVERSATION, f"会话不存在或已被删除：{conversation_id}"
                )

        if needles is None:
            needles = collect_needles(conversation_id, connection=conn)
        needles = tuple(needles)

        _begin(conn)
        deleted_rows = _delete_rows(conn, conversation_id)
        if owned:
            conn.commit()

        vacuumed = False
        if vacuum:
            try:
                conn.execute("VACUUM")
                vacuumed = True
            except sqlite3.Error as exc:  # pragma: no cover - 磁盘/权限异常
                logger.warning("delete: VACUUM 失败 kind=%s", type(exc).__name__)
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:  # pragma: no cover - 非 WAL 模式或无 WAL 文件
                pass
        if owned:
            conn.commit()
    finally:
        if owned:
            conn.close()

    temp_removed: tuple[str, ...] = ()
    residual: ResidualReport | None = None
    if owned:
        temp_removed = _cleanup_temp_files(resolved_db_path)
        residual = check_residuals(resolved_db_path, needles)

    scope = conversation_id if conversation_id is not None else SCOPE_ALL_DATA
    receipt = DeletionReceipt(
        scope=scope,
        deleted_at=_now(),
        deleted_rows=deleted_rows,
        vacuumed=vacuumed,
        temp_files_removed=temp_removed,
        residual=residual,
    )
    audit_file = write_audit(receipt, audit_path)
    receipt = DeletionReceipt(
        scope=receipt.scope,
        deleted_at=receipt.deleted_at,
        deleted_rows=receipt.deleted_rows,
        vacuumed=receipt.vacuumed,
        temp_files_removed=receipt.temp_files_removed,
        residual=receipt.residual,
        audit_path=audit_file,
    )
    logger.info(
        "delete: scope=%s deleted_at=%s total_rows=%d vacuumed=%s residual_clean=%s",
        receipt.scope,
        receipt.deleted_at,
        receipt.total_rows,
        receipt.vacuumed,
        receipt.residual.clean if receipt.residual else None,
    )
    return receipt


def delete_conversation(
    conversation_id: str,
    *,
    confirmed: bool = False,
    needles: Iterable[str] | None = None,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
    audit_path: Path | None = None,
    vacuum: bool = True,
) -> DeletionReceipt:
    """按会话一键删除（验收 ②③④，UI 主入口「删除本会话」）。

    - 单事务删 7 张表该会话的行；提交后 `VACUUM` + 清理临时文件；
    - 残留检查：确认已删原文片段在 db 文件里 0 命中；
    - 返回**无原文回执**，并追加一条无原文审计。
    """
    conversation_id = _validate_conversation_id(conversation_id)
    return _delete_scope(
        conversation_id,
        confirmed=confirmed,
        needles=needles,
        connection=connection,
        db_path=db_path,
        audit_path=audit_path,
        vacuum=vacuum,
    )


def delete_all_data(
    *,
    confirmed: bool = False,
    needles: Iterable[str] | None = None,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
    audit_path: Path | None = None,
    vacuum: bool = True,
) -> DeletionReceipt:
    """清空本机全部数据（危险操作，只放在设置页；`PRIVACY.md` §2.2）。

    保留空库结构（表与索引不删）——「是否保留空库结构」仍属**需人工确认**项，
    当前实现取「保留」（便于下次直接使用，且不含任何原文）。
    """
    return _delete_scope(
        None,
        confirmed=confirmed,
        needles=needles,
        connection=connection,
        db_path=db_path,
        audit_path=audit_path,
        vacuum=vacuum,
    )


def deletion_disclosures() -> tuple[str, ...]:
    """`PRIVACY.md` §2.3「删不掉的部分」——UI 必须用短句披露。"""
    return (
        "已发送给 DeepSeek 的请求可能被服务商按其政策留存，本应用无法远程擦除。",
        "你自己导出的 Markdown / JSON 文件需自行销毁。",
        "备份与系统还原点超出本应用的控制范围。",
    )


def conversation_row_counts(
    conversation_id: str,
    *,
    connection: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> dict[str, int]:
    """该会话在 7 张表中的行数（删除前后对比 / 验收 ② 用）。"""
    conversation_id = _validate_conversation_id(conversation_id)
    conn, owned = _connect(db_path) if connection is None else (connection, False)
    try:
        return _table_counts(conn, conversation_id)
    finally:
        if owned:
            conn.close()


__all__ = [
    "AUDIT_FILE_NAME",
    "CONSENT_STATEMENT",
    "CONSENT_STATEMENT_SOURCE",
    "CONSENT_STATEMENT_VERSION",
    "DEFAULT_SCOPE",
    "DELETED_TABLES",
    "ERROR_CONFIRMATION_REQUIRED",
    "ERROR_INVALID_CONVERSATION_ID",
    "ERROR_INVALID_SCOPE",
    "ERROR_NO_CONSENT",
    "ERROR_RESIDUAL_DATA",
    "ERROR_STALE_STATEMENT",
    "ERROR_UNKNOWN_CONVERSATION",
    "MAX_NEEDLES",
    "MIN_NEEDLE_CHARS",
    "SCOPE_ALL_DATA",
    "SCOPE_BOTH_PARTIES",
    "SCOPE_SELF_ONLY",
    "TABLE_KEYS",
    "VALID_SCOPES",
    "ConsentRecord",
    "DeletionReceipt",
    "PrivacyError",
    "ResidualReport",
    "check_residuals",
    "collect_needles",
    "consent_note",
    "consent_statement",
    "conversation_row_counts",
    "delete_all_data",
    "delete_conversation",
    "deletion_disclosures",
    "has_valid_consent",
    "load_consents",
    "make_consent_id",
    "mask_for_model",
    "mask_for_model_with_count",
    "masking_rules",
    "record_consent",
    "require_consent",
    "revoke_consent",
    "temp_file_paths",
    "write_audit",
]