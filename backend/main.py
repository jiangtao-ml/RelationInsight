"""RelationInsight API —— T-001 骨架 + T-007 同意闸门与一键删除（同步 FastAPI）。

T-001 保留内容（不得回归）
--------------------------
`GET /health` 的返回字段与语义不变；启动时 `init_db()` 建表；同步 FastAPI + 标准库 `sqlite3`。

T-007 新增内容
----------------
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/conversations/{id}/consent` | UI 勾选写入 `consents`（`PRIVACY.md` §1.2） |
| POST | `/conversations/{id}/analyze` | **同意闸门**：无有效同意一律 `403 no_consent`（验收 ①） |
| DELETE | `/conversations/{id}` | 按会话一键删除（主入口），必须 `?confirm=true`（验收 ②③④） |
| DELETE | `/data` | 清空本机全部数据（**危险操作，只在设置页**），必须 `?confirm=true` |

T-008 新增内容（集成接线，**不改动上面任何已冻结契约**）
--------------------------------------------------------
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/conversations/{id}/messages:import` | 纯文本 → T-002 解析 → 写 `messages`（需要时补 `conversations` / `persons` 行） |
| GET | `/conversations/{id}/profile` | 读 T-005 画像快照（默认最新版；`?version=N` 读历史版本；**只读**，不写库） |

- `message_id` 冲突（重复导入）按 §6 已冻结的**方案 A（拒绝整批）**处理 → `409 duplicate_message_id`，
  `detail.conflicts` 列出冲突 ID 与来源行号，整批一行不写。
- 另加 CORS：只放行本机 Streamlit 原型（8501），不改变「默认绑定 127.0.0.1」的约定。
- 新接口的响应体同样**不含聊天原文**：解析错误行只返回「行号 + 原因」。

约定
----
- 请求体 / 响应体**逐字不含**聊天原文（`PRIVACY.md` §4.2）；回执只含时间、范围、行数。
- 同意书文案唯一来源是 `privacy.CONSENT_STATEMENT`（逐字取自 `PRIVACY.md` §1.3），本文件不复制文案。
- 测试可通过 `app.state.db_path` 指向临时库、`app.state.audit_path` 指向临时审计文件、
  `app.state.llm_client` 注入 `FakeDeepSeekClient`（三者都只在测试里设置）。
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import privacy
from db import DB_PATH, REQUIRED_TABLES, get_connection, init_db, list_user_tables
from llm.deepseek import (
    ERROR_AUTH,
    ERROR_BAD_RESPONSE,
    ERROR_CONFIG,
    ERROR_CONNECTION,
    ERROR_MISSING_DEPENDENCY,
    ERROR_MISSING_KEY,
    ERROR_RATE_LIMIT,
    ERROR_SERVER,
    ERROR_TIMEOUT,
    DeepSeekError,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="RelationInsight", version="0.8.0")

#: T-008 CORS：只放行本机 Streamlit 原型（8501）。服务本身仍只绑 127.0.0.1（`ARCHITECTURE.md` §8），
#: 因此这条中间件只是让浏览器里的 Streamlit 页面能跨端口访问同一台机器上的 API。
ALLOWED_ORIGINS = (
    "http://localhost:8501",
    "http://127.0.0.1:8501",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#: `DeepSeekError.kind` → HTTP 状态码（上游问题一律 5xx/429，配置问题 409）。
_LLM_STATUS: dict[str, int] = {
    ERROR_MISSING_KEY: 409,
    ERROR_MISSING_DEPENDENCY: 500,
    ERROR_CONFIG: 500,
    ERROR_AUTH: 502,
    ERROR_RATE_LIMIT: 429,
    ERROR_SERVER: 502,
    ERROR_TIMEOUT: 504,
    ERROR_CONNECTION: 502,
    ERROR_BAD_RESPONSE: 502,
}


class ConsentRequest(BaseModel):
    """`POST /conversations/{id}/consent` 的请求体。"""

    granted: bool = True
    scope: str = privacy.DEFAULT_SCOPE
    statement_version: str | None = None


class AnalyzeRequest(BaseModel):
    """`POST /conversations/{id}/analyze` 的请求体。"""

    merge_profile: bool = True


class ImportRequest(BaseModel):
    """`POST /conversations/{id}/messages:import` 的请求体（T-008）。

    只收**纯文本**：整段聊天放在 `text` 里，由 T-002 解析器决定哪些行可解析；`title` 可选，
    只写进 `conversations.title`，不参与分析。
    """

    text: str = ""
    title: str | None = None


# ---------------------------------------------------------------- 内部工具


def _db_path() -> Path | None:
    """可注入的数据库路径：测试用 `app.state.db_path`；生产为 `None`（→ `db.DB_PATH`）。"""
    return getattr(app.state, "db_path", None)


def _audit_path() -> Path | None:
    """可注入的删除审计文件路径：测试用 `app.state.audit_path`；生产为 `None`（→ `backend/data/`）。"""
    return getattr(app.state, "audit_path", None)


def _privacy_failure(error: privacy.PrivacyError) -> HTTPException:
    logger.info("privacy: kind=%s status=%d", error.kind, error.status_code)
    return HTTPException(status_code=error.status_code, detail={"kind": error.kind, "message": error.detail})


def _llm_failure(error: DeepSeekError) -> HTTPException:
    status_code = _LLM_STATUS.get(error.kind, 502)
    logger.info("llm: kind=%s status=%d attempts=%d", error.kind, status_code, error.attempts)
    return HTTPException(status_code=status_code, detail={"kind": error.kind, "message": error.detail})


def _build_client():
    """生产路径：真实 DeepSeek 客户端（Key 只从环境变量读；缺失时抛 `DeepSeekError`）。"""
    from llm import DeepSeekClient

    return DeepSeekClient()


def _resolve_client():
    injected = getattr(app.state, "llm_client", None)
    return injected if injected is not None else _build_client()


def _consent_echo(record: privacy.ConsentRecord) -> dict:
    """回执里的同意摘要（只有时间 / 范围 / 版本号，无原文）。"""
    return {
        "consent_id": record.id,
        "scope": record.scope,
        "granted": bool(record.granted),
        "created_at": record.created_at,
        "statement_version": privacy.CONSENT_STATEMENT_VERSION,
    }


def _utc_now() -> str:
    """ISO-8601 UTC 字符串（与 `db` / `privacy` / `pipeline` 的写法一致）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_conversation(conn, conversation_id: str, title: str | None = None) -> bool:
    """确保 `conversations` 有该会话行（T-004 拍板建表）；`INSERT OR IGNORE`，返回是否新建。

    T-002 的 `insert_messages()` 只补 `persons` 行，会话主行由这里补；T-007 的按会话删除依赖它。
    """
    cursor = conn.execute(
        "INSERT OR IGNORE INTO conversations (id, title, status, created_at) VALUES (?, ?, 'active', ?)",
        (conversation_id, title, _utc_now()),
    )
    return max(cursor.rowcount, 0) > 0


@app.on_event("startup")
def on_startup() -> None:
    init_db(_db_path())


@app.get("/health")
def health() -> dict:
    db_path = _db_path() or DB_PATH
    tables = list_user_tables(db_path)
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    db_ok = Path(db_path).exists() and not missing
    return {
        "status": "ok" if db_ok else "degraded",
        "python": sys.version.split()[0],
        "database_path": str(db_path),
        "database_exists": Path(db_path).exists(),
        "tables": tables,
        "missing_tables": missing,
    }


@app.post("/conversations/{conversation_id}/messages:import")
def import_messages(conversation_id: str, payload: ImportRequest | None = Body(default=None)) -> dict:
    """导入纯文本：T-002 解析 → 写 `messages` 表（T-008 接线）。

    契约（T-002 / §6 已冻结，不改动）：
    - 解析错误行**不阻断**导入：可解析的行照常写入，错误行按「行号 + 原因」返回（**不回显原文**）；
    - `message_id` 冲突（重复导入）→ **拒绝整批**：整批一行都不写，返回 `409 duplicate_message_id`，
      并在 `detail.conflicts` 里列出冲突 ID 与来源行号；
    - **追加导入自动续号**（2026-09-23 补冻结，§6）：写库前取该会话库内 `MAX(seq)+1` 作为
      `seq_offset`；`seq` 是会话内**全局**序号，故「补充粘贴新消息」不再与既有行冲突，
      只有偏移后**仍**冲突时才按方案 A 拒绝整批。
    """
    from parser import STATUS_REJECTED_CONFLICT, import_chat

    request = payload or ImportRequest()
    conversation_id = (conversation_id or "").strip()
    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail={"kind": privacy.ERROR_INVALID_CONVERSATION_ID, "message": "conversation_id 不能为空"},
        )
    text = request.text or ""
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail={"kind": "empty_text", "message": "没有可导入的文本：请粘贴 `A: 正文` / `B: 正文`"},
        )

    db_path = _db_path()
    init_db(db_path)  # 幂等：表不存在时先建
    conn = get_connection(db_path)
    try:
        # T-008 缺陷修复（2026-09-23，§6「追加导入自动续号」）：seq 是**会话内全局序号**，新批次的
        # 起点 = 该会话库内 MAX(seq)+1；空会话时 COALESCE(...,-1)+1 = 0，与首版行为一致。
        # 先偏移再检测冲突，故只有「偏移后仍冲突」才按方案 A 拒绝整批。
        cursor = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        seq_offset = int(cursor.fetchone()[0])
        report = import_chat(text, conversation_id, seq_offset=seq_offset, connection=conn)
        if report.status == STATUS_REJECTED_CONFLICT:
            conflicts = [
                {"message_id": conflict.message_id, "source_line": conflict.source_line}
                for conflict in report.conflicts
            ]
            logger.info(
                "import: conversation=%s rejected_conflicts=%d（整批未写入）",
                conversation_id,
                len(conflicts),
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "kind": "duplicate_message_id",
                    "message": (
                        f"重复导入被拒绝：{len(conflicts)} 个 message_id 已存在，整批未写入"
                        "（ARCHITECTURE.md §6 方案 A：拒绝整批，不做部分导入）"
                    ),
                    "conflicts": conflicts,
                },
            )
        created = _ensure_conversation(conn, conversation_id, request.title)
        conn.commit()
    finally:
        conn.close()

    parsed = list(report.messages)
    seq_from = min((message.seq for message in parsed), default=None)
    seq_to = max((message.seq for message in parsed), default=None)
    errors = [{"line_number": error.line_number, "reason": error.reason} for error in report.errors]

    if report.inserted_count:
        message = f"已写入 {report.inserted_count} 条消息（seq {seq_from}–{seq_to}）"
        if errors:
            message += f"；错误行 {len(errors)} 行未阻断导入"
    else:
        message = "没有可写入的消息：请检查格式是否为 `A: 正文` / `B: 正文`"

    logger.info(
        "import: conversation=%s inserted=%d errors=%d blank_skipped=%d seq_offset=%d",
        conversation_id,
        report.inserted_count,
        len(errors),
        report.blank_lines_skipped,
        seq_offset,
    )
    return {
        "conversation_id": conversation_id,
        "status": report.status,
        "conversation_created": created,
        "inserted_count": report.inserted_count,
        "parsed_count": len(parsed),
        "blank_lines_skipped": report.blank_lines_skipped,
        "seq_from": seq_from,
        "seq_to": seq_to,
        "message_ids": [message.message_id for message in parsed],
        "errors": errors,
        "conflicts": [],
        "message": message,
    }


@app.get("/conversations/{conversation_id}/profile")
def get_profile(conversation_id: str, version: int | None = None) -> dict:
    """读该会话的画像快照（T-005 产物）：默认最新版，`?version=N` 读历史版本。

    `ARCHITECTURE.md` §4.6 规定 `profile_versions` 只追加、旧行不改写，所以这里**只读**。
    没有画像时返回 `404 no_profile`——前端据此回退到离线 fixture 演示（T-006 的离线路径）。
    """
    from pipeline import load_latest_profile, load_profile_versions

    conversation_id = (conversation_id or "").strip()
    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail={"kind": privacy.ERROR_INVALID_CONVERSATION_ID, "message": "conversation_id 不能为空"},
        )

    db_path = _db_path()
    init_db(db_path)
    if version is None:
        record = load_latest_profile(conversation_id, db_path=db_path)
    else:
        record = next(
            (item for item in load_profile_versions(conversation_id, db_path=db_path) if item.version == version),
            None,
        )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "kind": "no_profile",
                "message": (
                    f"会话 {conversation_id} 还没有画像版本（先导入消息 → 同意 → 分析）"
                    if version is None
                    else f"会话 {conversation_id} 不存在 v{version} 画像版本"
                ),
            },
        )

    logger.info("profile: conversation=%s version=%d", conversation_id, record.version)
    return {
        "conversation_id": conversation_id,
        "version": record.version,
        "profile_id": record.id,
        "created_at": record.created_at,
        "message_count": record.message_count,
        "snapshot": dict(record.snapshot or {}),
        "changelog": dict(record.changelog or {}),
    }


@app.post("/conversations/{conversation_id}/consent")
def grant_consent(conversation_id: str, payload: ConsentRequest | None = Body(default=None)) -> dict:
    """记录同意（勾选写入 `consents`）；文案版本号随行落库。"""
    request = payload or ConsentRequest()
    try:
        record = privacy.record_consent(
            conversation_id,
            scope=request.scope,
            granted=request.granted,
            statement_version=request.statement_version or privacy.CONSENT_STATEMENT_VERSION,
            db_path=_db_path(),
        )
    except privacy.PrivacyError as error:
        raise _privacy_failure(error) from error
    echo = _consent_echo(record)
    echo["statement"] = privacy.consent_statement()
    return echo


@app.post("/conversations/{conversation_id}/analyze")
def analyze(conversation_id: str, payload: AnalyzeRequest | None = Body(default=None)) -> dict:
    """分析入口：**先验同意**（无有效同意 → `403`），再走分批管道并按需合并画像。"""
    from pipeline import analyze_conversation_from_db, update_profile

    request = payload or AnalyzeRequest()
    try:
        consent = privacy.require_consent(conversation_id, db_path=_db_path())
    except privacy.PrivacyError as error:
        raise _privacy_failure(error) from error

    try:
        client = _resolve_client()
        report = analyze_conversation_from_db(conversation_id, client, db_path=_db_path())
    except DeepSeekError as error:
        raise _llm_failure(error) from error

    result: dict = {
        "conversation_id": conversation_id,
        "consent": _consent_echo(consent),
        "status": report.status,
        "message": report.message,
        "total_messages": report.total_messages,
        "batch_count": report.batch_count,
        "analyses_written": report.analyses_written,
        "evidence_written": report.evidence_written,
        "batches_skipped": report.batches_skipped,
        "dropped_count": report.dropped_count,
        "model": report.model,
        "prompt_version": report.prompt_version,
        "warnings": list(report.warnings),
        "failures": list(report.failures),
    }

    if request.merge_profile and report.ok:
        merged = update_profile(conversation_id, db_path=_db_path())
        result["profile"] = {
            "status": merged.status,
            "version": merged.version,
            "previous_version": merged.previous_version,
            "message_count": merged.message_count,
            "change_counts": dict(merged.change_counts or {}),
            "warnings": list(merged.warnings),
            "failures": list(merged.failures),
        }
    return result


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, confirm: bool = False) -> dict:
    """一键删除该会话（七张表该范围行 + `VACUUM` + 残留检查 + 无原文回执）。"""
    try:
        receipt = privacy.delete_conversation(
            conversation_id, confirmed=confirm, db_path=_db_path(), audit_path=_audit_path()
        )
    except privacy.PrivacyError as error:
        raise _privacy_failure(error) from error
    payload = receipt.to_dict()
    payload["disclosures"] = list(privacy.deletion_disclosures())
    return payload


@app.delete("/data")
def delete_all_data(confirm: bool = False) -> dict:
    """清空本机全部数据（危险操作，UI 只放在设置页；必须 `?confirm=true`）。"""
    try:
        receipt = privacy.delete_all_data(confirmed=confirm, db_path=_db_path(), audit_path=_audit_path())
    except privacy.PrivacyError as error:
        raise _privacy_failure(error) from error
    payload = receipt.to_dict()
    payload["disclosures"] = list(privacy.deletion_disclosures())
    return payload