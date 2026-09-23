"""T-008 缺陷修复的端到端用例（离线）：追加导入自动续号 → 分析 → 画像版本 +1。

对应 WorkBuddy 验收「必须项 5」的产品路径（此前失败）：
    导入 50 条 → 同意 → 分析（画像 v1）→ **追加** 20 条（自动续号 seq 50–69）→ 再分析 → 画像 v2

约定（与 `tests/test_privacy.py` 一致）：
- 不联网、不读 Key：模型一律用 `llm.FakeDeepSeekClient`；
- 数据库与审计文件都用 `tmp_path`，不触碰 `backend/data/`。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import privacy  # noqa: E402
from llm import FakeDeepSeekClient  # noqa: E402

CONVERSATION_ID = "conv-append-0001"


def bulk_text(count: int, *, start: int = 0) -> str:
    """生成 count 行合法的 `A: …` / `B: …` 文本（start 只影响正文编号，便于肉眼核对）。"""
    return "\n".join(
        f"{'A' if (start + index) % 2 == 0 else 'B'}: 第{start + index + 1}条消息"
        for index in range(count)
    )


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "relationinsight_append.db"


@pytest.fixture()
def audit_path(tmp_path: Path) -> Path:
    return tmp_path / "deletion_audit.jsonl"


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


def _seqs(db_path: Path) -> list[int]:
    conn = sqlite3.connect(db_path)
    try:
        return [row[0] for row in conn.execute("SELECT seq FROM messages ORDER BY seq")]
    finally:
        conn.close()


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def test_append_import_continues_seq_then_profile_version_bumps(db_path: Path, api) -> None:
    """必须项 5：同一会话追加消息后能再次分析，且画像版本 +1（旧版本快照不改写）。"""
    # ── 1) 首段导入 50 条：seq 0–49，正好 1 个完整批 ──
    first = api.post(f"/conversations/{CONVERSATION_ID}/messages:import", json={"text": bulk_text(50)})
    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert first_payload["status"] == "inserted"
    assert first_payload["inserted_count"] == 50
    assert (first_payload["seq_from"], first_payload["seq_to"]) == (0, 49)
    assert first_payload["conflicts"] == []
    assert first_payload["errors"] == []
    assert _count(db_path, "messages") == 50

    consent = api.post(
        f"/conversations/{CONVERSATION_ID}/consent",
        json={
            "scope": privacy.SCOPE_BOTH_PARTIES,
            "statement_version": privacy.CONSENT_STATEMENT_VERSION,
        },
    )
    assert consent.status_code == 200

    analyzed = api.post(f"/conversations/{CONVERSATION_ID}/analyze", json={"merge_profile": True})
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["profile"]["version"] == 1
    assert analyzed.json()["batch_count"] == 1
    v1_before = api.get(f"/conversations/{CONVERSATION_ID}/profile?version=1").json()

    # ── 2) 追加导入 20 条：**不带** seq_offset 的客户端调用由后端自动续号到 50–69 ──
    appended = api.post(
        f"/conversations/{CONVERSATION_ID}/messages:import",
        json={"text": bulk_text(20, start=50)},
    )
    assert appended.status_code == 200, appended.text
    appended_payload = appended.json()
    assert appended_payload["status"] == "inserted"
    assert appended_payload["inserted_count"] == 20
    assert (appended_payload["seq_from"], appended_payload["seq_to"]) == (50, 69)
    assert appended_payload["conflicts"] == []  # 旧实现会在这里返回 409
    assert _seqs(db_path) == list(range(70))
    assert len(set(appended_payload["message_ids"])) == 20

    # ── 3) 再分析：batch 0 幂等跳过，只分析新增尾批；画像升到 v2 ──
    again = api.post(f"/conversations/{CONVERSATION_ID}/analyze", json={"merge_profile": True})
    assert again.status_code == 200, again.text
    again_payload = again.json()
    assert again_payload["status"] == "completed"
    assert again_payload["batch_count"] == 2
    assert again_payload["analyses_written"] == 1  # 只有新尾批写入；batch 0 不重算
    assert again_payload["profile"]["version"] == 2

    # ── 4) 旧版本可读且未被改写；最新版覆盖 70 条 ──
    v1_after = api.get(f"/conversations/{CONVERSATION_ID}/profile?version=1").json()
    assert v1_after == v1_before
    assert json.dumps(v1_after["snapshot"], sort_keys=True) == json.dumps(
        v1_before["snapshot"], sort_keys=True
    )

    latest = api.get(f"/conversations/{CONVERSATION_ID}/profile").json()
    assert latest["version"] == 2
    assert latest["message_count"] == 70
    assert _count(db_path, "profile_versions") == 2
    assert _count(db_path, "analyses") == 2
    assert _count(db_path, "messages") == 70


def test_conflict_after_offset_still_rejects_the_whole_batch(db_path: Path, api) -> None:
    """回归：续号 ≠ 永不冲突。**偏移后**仍撞上既有 message_id 时，依旧按 §6 方案 A 拒绝整批。"""
    text = bulk_text(50)
    assert api.post(f"/conversations/{CONVERSATION_ID}/messages:import", json={"text": text}).status_code == 200

    # 显式把起点压回 0（模拟旧客户端 / 外部写入造成错位）：解析出的 seq 0–49 与已在库的行逐条相撞
    import parser

    report = parser.import_chat(text, CONVERSATION_ID, seq_offset=0, db_path=db_path)

    assert report.status == parser.STATUS_REJECTED_CONFLICT
    assert report.rejected is True
    assert report.inserted_count == 0
    assert len(report.conflicts) == 50
    assert [conflict.source_line for conflict in report.conflicts] == list(range(1, 51))
    assert _count(db_path, "messages") == 50  # 整批一行未写
