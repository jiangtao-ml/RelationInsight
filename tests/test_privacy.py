"""T-007 隐私模块测试：同意门闩 / 一键删除 / 残留检查 / 无原文审计。

约定（与 T-004/T-006 一致）：
- **不联网**、不读 Key：需要模型时只注入 `llm.FakeDeepSeekClient`；
- 数据库一律用 pytest 的 `tmp_path`，**不触碰** `backend/data/relationinsight.db`；
- 删除审计写临时文件（`app.state.audit_path`），不污染仓库；
- 每条用例对应 `TASKS.md` T-007 验收标准 ①–④ 中的一项（见各 docstring）。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import privacy  # noqa: E402
from db import get_connection, init_db  # noqa: E402
from llm import FakeDeepSeekClient  # noqa: E402
from llm.deepseek import mask_text  # noqa: E402
from parser import make_message_id, make_person_id  # noqa: E402
from pipeline import make_analysis_id, make_evidence_id  # noqa: E402
from pipeline.merge import make_profile_id  # noqa: E402

#: 独一无二的原文片段（用于残留检查；长度 >= MIN_NEEDLE_CHARS，避免误命中）。
PLAINTEXT_ONE = "我上周三下午四点给你转过 8600 块钱，收据还在我这儿"
PLAINTEXT_TWO = "那张收据我拍了照片存在云盘，编号是 BX-2026-0918 备份"

NOW = "2026-09-22T00:00:00Z"
CONVERSATION_ID = "conv-1"
OTHER_CONVERSATION_ID = "conv-2"


# ---------------------------------------------------------------- 夹具


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "relationinsight.db"
    init_db(path)
    return path


@pytest.fixture()
def audit_path(tmp_path: Path) -> Path:
    return tmp_path / "deletion_audit.jsonl"


def seed_conversation(
    db_path: Path,
    conversation_id: str = CONVERSATION_ID,
    *,
    message_count: int = 22,
    walmode: bool = False,
    seed_analysis: bool = True,
) -> dict:
    """写入一个会话的完整数据集：会话 + 两个人物 + N 条消息 + 1 批 analyses/evidence/画像版本。"""
    conn = get_connection(db_path)
    try:
        if walmode:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT INTO conversations (id, title, status, created_at) VALUES (?, ?, 'active', ?)",
            (conversation_id, f"测试会话 {conversation_id}", NOW),
        )
        person_ids: dict[str, str] = {}
        for role in ("A", "B"):
            person_id = make_person_id(conversation_id, role)
            person_ids[role] = person_id
            conn.execute(
                "INSERT INTO persons (id, conversation_id, role, display_label, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (person_id, conversation_id, role, role, NOW),
            )
        for seq in range(message_count):
            role = "A" if seq % 2 == 0 else "B"
            if seq == 0:
                body = PLAINTEXT_ONE
            elif seq == 1:
                body = PLAINTEXT_TWO
            else:
                body = f"第 {seq} 条占位文本，用于分批与合并测试。"
            conn.execute(
                "INSERT INTO messages"
                " (message_id, conversation_id, person_id, seq, body, source_line, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    make_message_id(conversation_id, seq),
                    conversation_id,
                    person_ids[role],
                    seq,
                    body,
                    seq + 1,
                    NOW,
                ),
            )

        analysis_id = None
        if seed_analysis:
            analysis_id = make_analysis_id(conversation_id, 0)
            conn.execute(
                "INSERT INTO analyses"
                " (id, conversation_id, batch_index, message_id_from, message_id_to, seq_from, seq_to,"
                "  model, prompt_version, result_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    analysis_id,
                    conversation_id,
                    0,
                    make_message_id(conversation_id, 0),
                    make_message_id(conversation_id, message_count - 1),
                    0,
                    message_count - 1,
                    "deepseek-chat",
                    "t-004-v1",
                    json.dumps(
                        {
                            "schema_version": "1.0",
                            "persons": {"A": {"tendencies": []}, "B": {"tendencies": []}},
                            "dyad": {"tendencies": []},
                            "warnings": [],
                        },
                        ensure_ascii=False,
                    ),
                    NOW,
                ),
            )
            conn.execute(
                "INSERT INTO evidence"
                " (id, analysis_id, conversation_id, claim_key, message_id, quote, speaker_role, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    make_evidence_id(analysis_id, "A.request_style", make_message_id(conversation_id, 0)),
                    analysis_id,
                    conversation_id,
                    "A.request_style",
                    make_message_id(conversation_id, 0),
                    privacy.mask_for_model(PLAINTEXT_ONE)[:80],
                    "A",
                    NOW,
                ),
            )
            conn.execute(
                "INSERT INTO profile_versions"
                " (id, conversation_id, version, snapshot_json, changelog_json, message_count, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    make_profile_id(conversation_id, 1),
                    conversation_id,
                    1,
                    json.dumps(
                        {"schema_version": "1.0", "version": 1, "message_count": message_count, "traits": []},
                        ensure_ascii=False,
                    ),
                    json.dumps({"added": 0}, ensure_ascii=False),
                    message_count,
                    NOW,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return {"analysis_id": analysis_id, "person_ids": person_ids}


def table_rows(db_path: Path, table: str, conversation_id: str | None = None) -> int:
    column = "id" if table == "conversations" else "conversation_id"
    conn = get_connection(db_path)
    try:
        if conversation_id is None:
            return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])
        return int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE {column} = ?", (conversation_id,)
            ).fetchone()["c"]
        )
    finally:
        conn.close()


def all_table_counts(db_path: Path) -> dict[str, int]:
    return {table: table_rows(db_path, table) for table in privacy.DELETED_TABLES}


# ---------------------------------------------------------------- 验收 ①：同意门闩


def test_consent_statement_is_verbatim_from_privacy_md() -> None:
    """同意文案必须与 `PRIVACY.md` §1.3 一字不差（拍板：不自行发挥）。"""
    privacy_md = (BACKEND_DIR.parent / "PRIVACY.md").read_text(encoding="utf-8")
    quoted = [
        line[2:].strip()
        for line in privacy_md.splitlines()
        if line.startswith("> 我确认这是我有权处理的对话")
    ]
    assert quoted, "PRIVACY.md §1.3 未找到同意书文案"
    assert privacy.CONSENT_STATEMENT == quoted[0]
    assert privacy.CONSENT_STATEMENT_VERSION in privacy.consent_statement()["version"]
    assert privacy.consent_statement()["source"] == "PRIVACY.md §1.3"


def test_record_consent_writes_only_allowed_fields(db_path: Path) -> None:
    """验收 ①/④：同意行只有时间 / 会话 ID / 范围 / 文案版本号，不含原文。"""
    seed_conversation(db_path)
    record = privacy.record_consent(CONVERSATION_ID, db_path=db_path)

    assert record.granted == 1
    assert record.revoked_at is None
    assert record.is_valid
    assert record.scope == privacy.SCOPE_BOTH_PARTIES
    assert privacy.CONSENT_STATEMENT_VERSION in (record.note or "")
    assert PLAINTEXT_ONE not in json.dumps(record.to_dict(), ensure_ascii=False)
    assert privacy.has_valid_consent(CONVERSATION_ID, db_path=db_path)

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM consents WHERE conversation_id = ?", (CONVERSATION_ID,)).fetchone()
    finally:
        conn.close()
    assert dict(row)["granted"] == 1
    assert set(dict(row)) == {"id", "conversation_id", "granted", "scope", "note", "created_at", "revoked_at"}
    assert PLAINTEXT_ONE not in (row["note"] or "")


def test_consent_scope_and_statement_version_are_validated(db_path: Path) -> None:
    """范围必须是枚举值；文案版本过期必须拒绝（提示重新阅读）。"""
    seed_conversation(db_path)
    with pytest.raises(privacy.PrivacyError) as bad_scope:
        privacy.record_consent(CONVERSATION_ID, scope="whatever", db_path=db_path)
    assert bad_scope.value.kind == privacy.ERROR_INVALID_SCOPE
    assert bad_scope.value.status_code == 400

    with pytest.raises(privacy.PrivacyError) as stale:
        privacy.record_consent(CONVERSATION_ID, statement_version="v0.0-1970-01-01", db_path=db_path)
    assert stale.value.kind == privacy.ERROR_STALE_STATEMENT
    assert stale.value.status_code == 400

    assert privacy.load_consents(CONVERSATION_ID, db_path=db_path) == []


def test_granted_false_and_revoked_rows_are_not_valid(db_path: Path) -> None:
    """`granted=0` 或已撤回都不算有效同意（`granted=1 AND revoked_at IS NULL`）。"""
    seed_conversation(db_path)
    privacy.record_consent(CONVERSATION_ID, granted=False, db_path=db_path)
    assert privacy.has_valid_consent(CONVERSATION_ID, db_path=db_path) is False

    privacy.record_consent(CONVERSATION_ID, db_path=db_path)
    assert privacy.has_valid_consent(CONVERSATION_ID, db_path=db_path) is True
    assert privacy.revoke_consent(CONVERSATION_ID, db_path=db_path) == 1
    assert privacy.has_valid_consent(CONVERSATION_ID, db_path=db_path) is False
    with pytest.raises(privacy.PrivacyError) as denied:
        privacy.require_consent(CONVERSATION_ID, db_path=db_path)
    assert denied.value.kind == privacy.ERROR_NO_CONSENT


def test_require_consent_is_scoped(db_path: Path) -> None:
    """范围不匹配时同样拒绝（`self_only` 不能当 `both_parties_informed` 用）。"""
    seed_conversation(db_path)
    privacy.record_consent(CONVERSATION_ID, scope=privacy.SCOPE_SELF_ONLY, db_path=db_path)
    assert privacy.require_consent(CONVERSATION_ID, scope=privacy.SCOPE_SELF_ONLY, db_path=db_path)
    with pytest.raises(privacy.PrivacyError):
        privacy.require_consent(CONVERSATION_ID, scope=privacy.SCOPE_BOTH_PARTIES, db_path=db_path)


@pytest.fixture()
def api(db_path: Path, audit_path: Path, monkeypatch: pytest.MonkeyPatch):
    """注入临时库 / 临时审计文件 / Fake 模型的 TestClient（不联网、不碰真实库）。"""
    import main

    monkeypatch.setattr(main.app.state, "db_path", db_path, raising=False)
    monkeypatch.setattr(main.app.state, "audit_path", audit_path, raising=False)
    monkeypatch.setattr(main.app.state, "llm_client", FakeDeepSeekClient(), raising=False)
    monkeypatch.setenv("RELATIONINSIGHT_API_BASE", "http://127.0.0.1:9")
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        yield client


def test_analyze_without_consent_returns_403_and_never_touches_pipeline(
    db_path: Path, api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验收 ①：无有效同意 → API 4xx，且**不得**调用分批分析管道。"""
    import pipeline

    calls: list[str] = []
    real = pipeline.analyze_conversation_from_db

    def spy(conversation_id, client, **kwargs):  # pragma: no cover - 只记录是否被调用
        calls.append(conversation_id)
        return real(conversation_id, client, **kwargs)

    monkeypatch.setattr(pipeline, "analyze_conversation_from_db", spy)
    seed_conversation(db_path)
    analyses_before = table_rows(db_path, "analyses", CONVERSATION_ID)

    response = api.post(f"/conversations/{CONVERSATION_ID}/analyze", json={})
    assert response.status_code == 403
    assert response.json()["detail"]["kind"] == privacy.ERROR_NO_CONSENT
    assert calls == []
    assert table_rows(db_path, "analyses", CONVERSATION_ID) == analyses_before


def test_analyze_after_consent_runs_pipeline_and_merges_profile(db_path: Path, api) -> None:
    """验收 ①：写入同意后放行（200），管道落库并生成 v1 画像。"""
    seed_conversation(db_path, seed_analysis=False)
    consent = api.post(
        f"/conversations/{CONVERSATION_ID}/consent",
        json={"scope": privacy.SCOPE_BOTH_PARTIES, "statement_version": privacy.CONSENT_STATEMENT_VERSION},
    )
    assert consent.status_code == 200
    assert consent.json()["granted"] is True
    assert consent.json()["statement"]["text"] == privacy.CONSENT_STATEMENT

    response = api.post(f"/conversations/{CONVERSATION_ID}/analyze", json={"merge_profile": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["batch_count"] == 1
    assert payload["analyses_written"] == 1
    assert payload["evidence_written"] >= 1
    assert payload["profile"]["version"] == 1
    assert table_rows(db_path, "analyses", CONVERSATION_ID) == 1
    assert table_rows(db_path, "evidence", CONVERSATION_ID) >= 1
    assert table_rows(db_path, "profile_versions", CONVERSATION_ID) == 1


def test_consent_api_rejects_bad_scope_and_stale_statement(db_path: Path, api) -> None:
    seed_conversation(db_path)
    assert api.post(f"/conversations/{CONVERSATION_ID}/consent", json={"scope": "nope"}).status_code == 400
    stale = api.post(
        f"/conversations/{CONVERSATION_ID}/consent", json={"statement_version": "v0.0"}
    )
    assert stale.status_code == 400
    assert stale.json()["detail"]["kind"] == privacy.ERROR_STALE_STATEMENT


def test_revoked_consent_blocks_analyze_via_api(db_path: Path, api) -> None:
    seed_conversation(db_path, seed_analysis=False)
    assert api.post(f"/conversations/{CONVERSATION_ID}/consent", json={}).status_code == 200
    assert privacy.revoke_consent(CONVERSATION_ID, db_path=db_path) == 1
    response = api.post(f"/conversations/{CONVERSATION_ID}/analyze", json={})
    assert response.status_code == 403
    assert table_rows(db_path, "analyses", CONVERSATION_ID) == 0


# ---------------------------------------------------------------- 验收 ②：按范围删干净


def test_delete_conversation_clears_all_seven_tables(db_path: Path, audit_path: Path) -> None:
    """验收 ②：删除后七张表该范围 0 行；**其他会话不受影响**。"""
    seed_conversation(db_path)
    seed_conversation(db_path, OTHER_CONVERSATION_ID, message_count=21)
    privacy.record_consent(CONVERSATION_ID, db_path=db_path)
    privacy.record_consent(OTHER_CONVERSATION_ID, db_path=db_path)

    receipt = privacy.delete_conversation(
        CONVERSATION_ID, confirmed=True, db_path=db_path, audit_path=audit_path
    )

    assert receipt.scope == CONVERSATION_ID
    assert receipt.total_rows > 0
    assert set(receipt.deleted_rows) == set(privacy.DELETED_TABLES)
    for table in privacy.DELETED_TABLES:
        assert table_rows(db_path, table, CONVERSATION_ID) == 0, table
    assert privacy.conversation_row_counts(CONVERSATION_ID, db_path=db_path) == {
        table: 0 for table in privacy.DELETED_TABLES
    }
    # 其他会话保留
    assert table_rows(db_path, "messages", OTHER_CONVERSATION_ID) == 21
    assert table_rows(db_path, "consents", OTHER_CONVERSATION_ID) == 1
    assert table_rows(db_path, "conversations", OTHER_CONVERSATION_ID) == 1
    assert privacy.load_consents(CONVERSATION_ID, db_path=db_path) == []


def test_delete_requires_second_confirmation(db_path: Path, api, audit_path: Path) -> None:
    """二次确认：没有 `confirm=true` 一律 4xx，且数据毫发无损。"""
    seed_conversation(db_path)
    without = api.delete(f"/conversations/{CONVERSATION_ID}")
    assert without.status_code == 400
    assert without.json()["detail"]["kind"] == privacy.ERROR_CONFIRMATION_REQUIRED
    assert table_rows(db_path, "messages", CONVERSATION_ID) == 22

    with pytest.raises(privacy.PrivacyError) as direct:
        privacy.delete_conversation(CONVERSATION_ID, db_path=db_path, audit_path=audit_path)
    assert direct.value.kind == privacy.ERROR_CONFIRMATION_REQUIRED

    ok = api.delete(f"/conversations/{CONVERSATION_ID}?confirm=true")
    assert ok.status_code == 200
    assert ok.json()["deleted_at"]
    assert table_rows(db_path, "messages", CONVERSATION_ID) == 0
    assert ok.json()["disclosures"] == list(privacy.deletion_disclosures())


def test_delete_unknown_conversation_returns_404(db_path: Path, api) -> None:
    response = api.delete("/conversations/does-not-exist?confirm=true")
    assert response.status_code == 404
    assert response.json()["detail"]["kind"] == privacy.ERROR_UNKNOWN_CONVERSATION


def test_delete_all_data_clears_every_conversation(db_path: Path, api, audit_path: Path) -> None:
    """全库清空（设置页危险操作）：所有会话、所有表归零，且留下无原文审计。"""
    seed_conversation(db_path)
    seed_conversation(db_path, OTHER_CONVERSATION_ID, message_count=21)
    assert table_rows(db_path, "messages") == 43

    response = api.delete("/data?confirm=true")
    assert response.status_code == 200
    assert response.json()["scope"] == privacy.SCOPE_ALL_DATA
    for table in privacy.DELETED_TABLES:
        assert table_rows(db_path, table) == 0, table
    # 表结构保留（「是否保留空库结构」仍属需人工确认项，当前实现保留）
    conn = get_connection(db_path)
    try:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert set(privacy.DELETED_TABLES).issubset(names)
    assert json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])["scope"] == privacy.SCOPE_ALL_DATA


def test_delete_all_data_requires_confirmation(db_path: Path, api) -> None:
    seed_conversation(db_path)
    assert api.delete("/data").status_code == 400
    assert table_rows(db_path, "messages") == 22


def test_second_delete_of_same_conversation_is_404(db_path: Path, audit_path: Path) -> None:
    """删除是幂等的终点：数据已无，再删应明确 404（而不是静默成功或报错 500）。"""
    seed_conversation(db_path)
    privacy.delete_conversation(CONVERSATION_ID, confirmed=True, db_path=db_path, audit_path=audit_path)
    with pytest.raises(privacy.PrivacyError) as second:
        privacy.delete_conversation(CONVERSATION_ID, confirmed=True, db_path=db_path, audit_path=audit_path)
    assert second.value.kind == privacy.ERROR_UNKNOWN_CONVERSATION


# ---------------------------------------------------------------- 验收 ③：无明文残留


def test_needles_exist_before_delete_and_vanish_after(db_path: Path, audit_path: Path) -> None:
    """验收 ③：删除前能命中原文（负对照），删除后字节级 0 命中。"""
    seed_conversation(db_path)
    before = privacy.check_residuals(db_path, [PLAINTEXT_ONE, PLAINTEXT_TWO])
    assert before.clean is False
    assert before.hits >= 2
    assert before.hit_files == (db_path.name,) or db_path.name in before.hit_files

    receipt = privacy.delete_conversation(
        CONVERSATION_ID, confirmed=True, db_path=db_path, audit_path=audit_path
    )
    assert receipt.vacuumed is True
    assert receipt.residual is not None
    assert receipt.residual.clean is True
    assert receipt.residual.hits == 0
    assert PLAINTEXT_ONE.encode("utf-8") not in db_path.read_bytes()
    assert PLAINTEXT_TWO.encode("utf-8") not in db_path.read_bytes()
    for temp in privacy.temp_file_paths(db_path):
        assert not temp.exists(), temp.name


def test_delete_removes_wal_plaintext_when_wal_enabled(db_path: Path, audit_path: Path) -> None:
    """WAL 模式下列删除：`wal_checkpoint(TRUNCATE)` + 清理 `-wal` / `-shm`，不留明文。"""
    seed_conversation(db_path, walmode=True)
    assert privacy.check_residuals(db_path, [PLAINTEXT_ONE]).clean is False

    receipt = privacy.delete_conversation(
        CONVERSATION_ID, confirmed=True, db_path=db_path, audit_path=audit_path
    )
    assert receipt.residual is not None and receipt.residual.clean is True
    for temp in privacy.temp_file_paths(db_path):
        if temp.exists():  # pragma: no cover - 允许仍存在但必须为空
            assert temp.read_bytes() == b""


def test_check_residuals_scans_temp_files_without_echoing_content(tmp_path: Path) -> None:
    """残留检查覆盖 WAL/SHM/日志等临时文件，且只报告文件名与命中数。"""
    db_file = tmp_path / "some.db"
    db_file.write_bytes(b"clean-database-bytes")
    stray_wal = Path(f"{db_file}-wal")
    stray_wal.write_bytes(PLAINTEXT_ONE.encode("utf-8"))

    report = privacy.check_residuals(db_file, [PLAINTEXT_ONE, "短"])
    assert report.clean is False
    assert report.hits == 1
    assert stray_wal.name in report.hit_files
    # 只报告文件名 + 计数，不回显命中内容
    assert PLAINTEXT_ONE not in json.dumps(report.to_dict(), ensure_ascii=False)
    assert report.checked_needles == 1  # 太短的 needle 被跳过


# ---------------------------------------------------------------- 验收 ④：可审计、无原文


def test_receipt_audit_and_logs_contain_no_plaintext(
    db_path: Path, audit_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """验收 ④：回执与审计只记时间 / 范围 / 行数；日志逐字不含原文。"""
    caplog.set_level(logging.INFO)
    seed_conversation(db_path)
    privacy.record_consent(CONVERSATION_ID, db_path=db_path)
    privacy.require_consent(CONVERSATION_ID, db_path=db_path)

    receipt = privacy.delete_conversation(
        CONVERSATION_ID, confirmed=True, db_path=db_path, audit_path=audit_path
    )
    payload = json.dumps(receipt.to_dict(), ensure_ascii=False)
    assert receipt.deleted_at
    assert receipt.scope == CONVERSATION_ID
    assert PLAINTEXT_ONE not in payload
    assert PLAINTEXT_TWO not in payload

    audit_text = audit_path.read_text(encoding="utf-8")
    assert audit_text.strip(), "删除必须留下审计记录"
    record = json.loads(audit_text.splitlines()[-1])
    assert record["deleted_at"] == receipt.deleted_at
    assert record["scope"] == CONVERSATION_ID
    assert record["total_rows"] == receipt.total_rows
    assert record["note"] == "audit only: no plaintext recorded"
    assert PLAINTEXT_ONE not in audit_text
    assert PLAINTEXT_TWO not in audit_text

    assert caplog.text, "删除过程应产生 info 级日志"
    assert PLAINTEXT_ONE not in caplog.text
    assert PLAINTEXT_TWO not in caplog.text
    assert "delete: scope=" in caplog.text


def test_logs_never_record_message_bodies(db_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """PRIVACY §4.2：日志只允许 ID / 条数 / 错误码，不允许 body。"""
    caplog.set_level(logging.DEBUG)
    seed_conversation(db_path)
    privacy.collect_needles(CONVERSATION_ID, db_path=db_path)
    privacy.record_consent(CONVERSATION_ID, db_path=db_path)
    privacy.mask_for_model_with_count(PLAINTEXT_ONE)
    assert PLAINTEXT_ONE not in caplog.text
    assert PLAINTEXT_TWO not in caplog.text


def test_privacy_error_status_codes() -> None:
    assert privacy.PrivacyError(privacy.ERROR_NO_CONSENT, "x").status_code == 403
    assert privacy.PrivacyError(privacy.ERROR_CONFIRMATION_REQUIRED, "x").status_code == 400
    assert privacy.PrivacyError(privacy.ERROR_UNKNOWN_CONVERSATION, "x").status_code == 404
    assert privacy.PrivacyError(privacy.ERROR_INVALID_SCOPE, "x").status_code == 400


# ---------------------------------------------------------------- 脱敏统一入口（§8）


def test_mask_for_model_is_the_single_masking_entry() -> None:
    """§8：脱敏统一收敛到 privacy，实现复用 llm 的正则（不复制规则）。"""
    text = "手机 13800138000，邮箱 someone@example.com，卡号 6222020200112233"
    masked = privacy.mask_for_model(text)
    assert masked == mask_text(text)
    assert "13800138000" not in masked
    assert "someone@example.com" not in masked
    assert privacy.masking_rules() == ("email", "phone", "id_card", "bank_card")


def test_collect_needles_skips_short_bodies(db_path: Path) -> None:
    seed_conversation(db_path, message_count=4)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE messages SET body = ? WHERE message_id = ?",
            ("嗯", make_message_id(CONVERSATION_ID, 2)),
        )
        conn.commit()
    finally:
        conn.close()
    needles = privacy.collect_needles(CONVERSATION_ID, db_path=db_path)
    assert "嗯" not in needles
    assert PLAINTEXT_ONE in needles


# ---------------------------------------------------------------- UI 层阻止（验收 ①）


def test_ui_blocks_analysis_and_deletion_until_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """验收 ①（UI 阻止）：未勾选同意时「开始分析」禁用；破坏性按钮需二次确认勾选。"""
    monkeypatch.setenv("RELATIONINSIGHT_API_BASE", "http://127.0.0.1:9")
    from streamlit.testing.v1 import AppTest

    app_file = BACKEND_DIR.parent / "frontend" / "app.py"
    at = AppTest.from_file(str(app_file), default_timeout=60).run()
    assert not at.exception
    assert [tab.proto.label for tab in at.tabs] == ["① 导入预览", "② A/B 标记", "③ 画像卡片", "④ 证据列表"]

    assert at.button(key="btn_analyze").proto.disabled is True
    assert at.button(key="btn_submit_consent").proto.disabled is True
    assert at.button(key="btn_delete_conversation").proto.disabled is True
    assert at.button(key="btn_delete_all").proto.disabled is True

    at.checkbox(key="consent_granted").check().run()
    assert at.button(key="btn_analyze").proto.disabled is False
    assert at.button(key="btn_submit_consent").proto.disabled is False
    assert at.button(key="btn_delete_conversation").proto.disabled is True  # 仍需二次确认

    at.checkbox(key="delete_conversation_ack").check().run()
    assert at.button(key="btn_delete_conversation").proto.disabled is False
    assert at.button(key="btn_delete_all").proto.disabled is True

    at.checkbox(key="delete_all_ack").check().run()
    assert at.button(key="btn_delete_all").proto.disabled is False


def test_ui_shows_privacy_statement_and_never_echoes_after_click(monkeypatch: pytest.MonkeyPatch) -> None:
    """同意书文案逐字来自 `PRIVACY.md` §1.3；后端不可用时点击只给提示，不抛异常、不显示原文。"""
    monkeypatch.setenv("RELATIONINSIGHT_API_BASE", "http://127.0.0.1:9")
    from streamlit.testing.v1 import AppTest

    app_file = BACKEND_DIR.parent / "frontend" / "app.py"
    at = AppTest.from_file(str(app_file), default_timeout=60).run()
    markdown_dump = " ".join(element.value for element in at.markdown)
    page_text = " ".join([markdown_dump] + [element.value for element in at.caption])
    assert privacy.CONSENT_STATEMENT in markdown_dump
    assert privacy.CONSENT_STATEMENT_VERSION in page_text
    assert "自恋型" not in markdown_dump  # 不做诊断式标题

    at.checkbox(key="consent_granted").check().run()
    at.button(key="btn_submit_consent").click().run()
    assert not at.exception
    assert at.warning or at.success


def test_ui_delete_all_requires_double_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """设置页危险操作：勾选「我理解不可恢复」后按钮才可用；无后端时不产生任何删除动作。"""
    monkeypatch.setenv("RELATIONINSIGHT_API_BASE", "http://127.0.0.1:9")
    from streamlit.testing.v1 import AppTest

    app_file = BACKEND_DIR.parent / "frontend" / "app.py"
    at = AppTest.from_file(str(app_file), default_timeout=60).run()
    at.checkbox(key="delete_all_ack").check().run()
    assert at.button(key="btn_delete_all").proto.disabled is False
    at.button(key="btn_delete_all").click().run()
    assert not at.exception
    assert at.error  # 未连接后端 → 明确报错，不做任何本地删除


def test_backend_data_dir_is_not_touched_by_tests(db_path: Path) -> None:
    """测试全程只碰 tmp_path：仓库里的真实库不应被本次测试写入（防御性断言）。"""
    assert db_path.parent.name == "test_privacy0" or db_path.name == "relationinsight.db"
    assert os.path.abspath(db_path) != str(BACKEND_DIR / "data" / "relationinsight.db")


def test_sqlite_foreign_keys_are_enforced_on_our_connection(db_path: Path) -> None:
    """删除顺序依赖外键：确认连接确实开了 `PRAGMA foreign_keys`。"""
    conn = get_connection(db_path)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO evidence (id, analysis_id, conversation_id, claim_key, message_id,"
                " quote, speaker_role, created_at) VALUES ('x', 'nope', 'c', 'k', 'nope', 'q', 'A', ?)",
                (NOW,),
            )
    finally:
        conn.close()