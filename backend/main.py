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
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel

import privacy
from db import DB_PATH, REQUIRED_TABLES, init_db, list_user_tables
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

app = FastAPI(title="RelationInsight", version="0.7.0")

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