"""T-005 长期画像增量更新测试：版本递增 / 旧快照逐字节不变 / 结论级修订 / 只追加不覆盖。

约定：
- 不联网：模型一律用 `llm.FakeDeepSeekClient`；数据库一律用 pytest 的 `tmp_path`，
  不触碰 `backend/data/relationinsight.db`。
- 需要「同一 trait_key 跨批次」的场景，直接复用假客户端的默认画像：它为 A / B 各产出一条
  `{role}.request_style` 结论，跨批次同键，正好用来验证 added / supported / 修订。
- 每条用例对应 TASKS.md T-005 验收标准 ①–④ 中的一项（见各 docstring）。
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_connection  # noqa: E402
from llm import FakeDeepSeekClient  # noqa: E402
from parser import MessageDTO, import_chat, insert_messages, make_message_id, make_person_id  # noqa: E402
from pipeline import (  # noqa: E402
    CHANGE_ADDED,
    CHANGE_REVISED,
    CHANGE_SUPPORTED,
    CHANGE_WEAKENED,
    STATUS_COMPLETED,
    STATUS_MERGED,
    STATUS_NOTHING_TO_DO,
    TRAIT_STATUS_ACTIVE,
    TRAIT_STATUS_SUPERSEDED,
    WARNING_BROKEN_ANALYSIS,
    AnalysisRecord,
    ProfileVersionRecord,
    analyze_conversation_from_db,
    classify_change,
    load_analyses,
    load_latest_profile,
    load_profile_versions,
    make_profile_id,
    merge_evidence_ids,
    merge_profile,
    merge_unique_ids,
    normalise_trait_key,
    snapshot_to_sections,
    statement_similarity,
    update_profile,
    weighted_average_confidence,
)

CONVERSATION_ID = "conv-merge-001"

STATEMENT_V1 = "A 通常主动开启话题。"
STATEMENT_V2_SIMILAR = "A 通常会主动开启话题。"
STATEMENT_V2_REWRITTEN = "A 在压力下会明显回避沟通，转而用冷淡回应代替直接表达。"


# ---------------------------------------------------------------- 夹具 / 工具


def number_of_lines(count: int, *, start: int = 0) -> str:
    return "\n".join(
        f"{'A' if (start + index) % 2 == 0 else 'B'}: 第{start + index:03d}条消息"
        for index in range(count)
    )


def seed_conversation(tmp_path: Path, count: int, *, conversation_id: str = CONVERSATION_ID) -> Path:
    """把 `count` 条消息经 T-002 解析器写入临时库，返回库路径。"""
    db_path = tmp_path / "relationinsight.db"
    report = import_chat(number_of_lines(count), conversation_id, db_path=db_path)
    assert report.inserted_count == count, f"夹具写入失败：{report.status}"
    return db_path


def append_messages(
    db_path: Path, count: int, *, start_seq: int, conversation_id: str = CONVERSATION_ID
) -> None:
    """追加 `count` 条消息（seq 从 `start_seq` 续号），模拟「追加消息后重新分析」。"""
    rows = [
        MessageDTO(
            message_id=make_message_id(conversation_id, start_seq + offset),
            conversation_id=conversation_id,
            person_id=make_person_id(
                conversation_id, "A" if (start_seq + offset) % 2 == 0 else "B"
            ),
            seq=start_seq + offset,
            body=f"第{start_seq + offset:03d}条消息",
            source_line=offset + 1,
        )
        for offset in range(count)
    ]
    report = insert_messages(rows, db_path=db_path)
    assert report.inserted_count == count, f"追加失败：{report.status}"


def analyze(db_path: Path, *, client=None, conversation_id: str = CONVERSATION_ID):
    """跑一遍 T-004 管道（离线）。"""
    client = FakeDeepSeekClient() if client is None else client
    report = analyze_conversation_from_db(conversation_id, client, db_path=db_path)
    assert report.status == STATUS_COMPLETED, report.message
    return report


def fetch_rows(db_path: Path, table: str, order_by: str = "rowid") -> list[tuple]:
    conn = get_connection(db_path)
    try:
        return [
            tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
        ]
    finally:
        conn.close()


def raw_snapshot(db_path: Path, version: int, conversation_id: str = CONVERSATION_ID) -> str:
    """取某版快照的**原始字符串**（用于逐字节比对，验证旧版未被改写）。"""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT snapshot_json FROM profile_versions WHERE conversation_id = ? AND version = ?",
            (conversation_id, version),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, f"v{version} 不存在"
    return row["snapshot_json"]


def entries(snapshot, *, status=None) -> list[dict]:
    traits = list(snapshot.get("traits") or [])
    if status is None:
        return traits
    return [item for item in traits if item.get("status") == status]


def entry_of(snapshot, trait_key: str, *, status: str = TRAIT_STATUS_ACTIVE) -> dict:
    for item in entries(snapshot, status=status):
        if item.get("trait_key") == trait_key:
            return item
    raise AssertionError(f"快照里没有 trait_key={trait_key} / status={status} 的条目")


def tendency(
    claim_key: str,
    statement: str,
    *,
    confidence: float = 0.6,
    sample_size: int = 20,
    evidence: tuple[str, ...] = (),
) -> dict:
    return {
        "claim_key": claim_key,
        "statement": statement,
        "confidence": confidence,
        "sample_size": sample_size,
        "evidence_message_ids": list(evidence),
    }


def make_profile(*, a=(), b=(), dyad=()) -> dict:
    """按 `ARCHITECTURE.md` §5 拼一份画像（a/b/dyad 传 tendency 列表）。"""
    return {
        "schema_version": "1.0",
        "persons": {"A": {"tendencies": list(a)}, "B": {"tendencies": list(b)}},
        "dyad": {"tendencies": list(dyad)},
        "warnings": [],
    }


def make_analysis(
    batch_index: int,
    *,
    profile: dict,
    conversation_id: str = CONVERSATION_ID,
    id_prefix: str = "an",
    seq_from: int | None = None,
    seq_to: int | None = None,
    parse_error: str | None = None,
) -> AnalysisRecord:
    start = batch_index * 50 if seq_from is None else seq_from
    end = start + 19 if seq_to is None else seq_to
    return AnalysisRecord(
        id=f"{id_prefix}-{batch_index}",
        conversation_id=conversation_id,
        batch_index=batch_index,
        seq_from=start,
        seq_to=end,
        model="deepseek-chat",
        prompt_version="t004.v1",
        profile=profile,
        parse_error=parse_error,
    )

# ---------------------------------------------------------------- 验收 ① 版本 +1


def test_first_merge_creates_version_1(tmp_path):
    """验收 ①：没有任何旧版时，第一次合并直接产出 v1（首版）。"""
    db_path = seed_conversation(tmp_path, 60)
    analyze(db_path)

    report = update_profile(CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_MERGED
    assert report.ok is True
    assert report.version == 1 and report.previous_version is None
    assert report.analyses_used == 2 and report.analyses_skipped == 0
    assert report.message_count == 60
    assert report.profile_id == make_profile_id(CONVERSATION_ID, 1)
    assert report.snapshot["version"] == 1
    assert report.snapshot["supersedes_version"] is None
    assert report.snapshot["covered_batch_indexes"] == [0, 1]
    assert report.snapshot["counts"]["added"] == 2          # A.request_style + B.request_style
    assert report.snapshot["rules_version"]

    rows = fetch_rows(db_path, "profile_versions", "version")
    assert len(rows) == 1
    assert rows[0][0] == make_profile_id(CONVERSATION_ID, 1)
    assert rows[0][2] == 1 and rows[0][5] == 60
    changelog = json.loads(rows[0][4])
    assert changelog["change_counts"]["added"] == 2
    assert changelog["previous_version"] is None
    assert changelog["rules"]["rules_version"] == report.snapshot["rules_version"]
    assert len(changelog["changes"]["added"]) == 2


def test_new_batch_bumps_version_and_keeps_old_version_readable(tmp_path):
    """验收 ①②③：追加消息 + 分析完成后版本 +1；旧版快照仍可读、且逐字节未改。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    first = update_profile(CONVERSATION_ID, db_path=db_path)
    assert first.version == 1

    v1_raw = raw_snapshot(db_path, 1)
    v1_entry = entry_of(first.snapshot, "A.request_style")

    append_messages(db_path, 40, start_seq=50)          # 50 → 90 条，尾批越界成新批次
    analyze(db_path)
    second = update_profile(CONVERSATION_ID, db_path=db_path)

    assert second.status == STATUS_MERGED
    assert second.version == 2 and second.previous_version == 1
    assert second.analyses_used == 1 and second.analyses_skipped == 1   # 只折入新增尾批
    assert second.snapshot["supersedes_version"] == 1
    assert second.snapshot["covered_batch_indexes"] == [0, 1]
    assert second.message_count == 90

    # 验收 ②：旧版快照逐字节可读、未被改写
    assert raw_snapshot(db_path, 1) == v1_raw
    old_snapshot = json.loads(raw_snapshot(db_path, 1))
    assert old_snapshot["version"] == 1
    assert entry_of(old_snapshot, "A.request_style")["statement"] == v1_entry["statement"]
    assert entry_of(old_snapshot, "A.request_style")["sample_size"] == v1_entry["sample_size"]

    # 验收 ③：新版要么沿用同一 trait_key 的旧表述，要么给出结论级 revision_of
    new_entry = entry_of(second.snapshot, "A.request_style")
    assert new_entry["trait_key"] == "A.request_style"
    assert new_entry["statement"] == v1_entry["statement"]
    assert second.change_counts[CHANGE_SUPPORTED] == 2
    assert second.change_counts[CHANGE_ADDED] == 0


def test_repeated_merge_without_new_batch_writes_nothing(tmp_path):
    """验收 ①：没有新批次时返回 nothing_to_do——不写行、不升版本（幂等）。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    update_profile(CONVERSATION_ID, db_path=db_path)
    before = fetch_rows(db_path, "profile_versions", "version")

    again = update_profile(CONVERSATION_ID, db_path=db_path)

    assert again.status == STATUS_NOTHING_TO_DO
    assert again.ok is False and again.is_nothing_to_do is True
    assert again.version == again.previous_version == 1
    assert again.analyses_used == 0 and again.analyses_skipped == 1
    assert fetch_rows(db_path, "profile_versions", "version") == before
    assert "没有新的分析批次" in again.message


def test_analyses_without_any_batch_is_nothing_to_do(tmp_path):
    """库里一条 analyses 都没有（例如样本不足没跑过）：不写版本行。"""
    db_path = seed_conversation(tmp_path, 25)

    report = update_profile(CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_NOTHING_TO_DO
    assert report.previous_version is None and report.version is None
    assert fetch_rows(db_path, "profile_versions") == []


def test_growing_remainder_batch_is_not_reanalyzed(tmp_path):
    """幂等键 = (conversation_id, batch_index)（ARCHITECTURE.md §6）：

    余数批在原地长大（60 → 80 条）时，batch_index=1 已存在，T-004 不重算、T-005 也就没有新批次
    ——这是「追加消息后不重算既有批次」的直接结果，改批次大小前必须先迁移已有 analyses。
    """
    db_path = seed_conversation(tmp_path, 60)
    analyze(db_path)
    update_profile(CONVERSATION_ID, db_path=db_path)

    append_messages(db_path, 20, start_seq=60)          # 60 → 80 条，批次边界不变（0-49 / 50-79）
    second_run = analyze(db_path)

    assert second_run.analyses_written == 0
    assert second_run.batches_skipped == 2
    assert update_profile(CONVERSATION_ID, db_path=db_path).status == STATUS_NOTHING_TO_DO
    assert len(fetch_rows(db_path, "profile_versions")) == 1


# ---------------------------------------------------------------- 验收 ④ 只追加


def test_profile_versions_are_append_only(tmp_path):
    """验收 ④：老行连 created_at 都一字不改；新行 id 由 (会话, 版本) 确定性生成。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    update_profile(CONVERSATION_ID, db_path=db_path)
    before = fetch_rows(db_path, "profile_versions", "version")
    raw_before = raw_snapshot(db_path, 1)

    append_messages(db_path, 40, start_seq=50)
    analyze(db_path)
    update_profile(CONVERSATION_ID, db_path=db_path)
    after = fetch_rows(db_path, "profile_versions", "version")

    assert len(after) == len(before) + 1
    assert after[: len(before)] == before
    assert raw_snapshot(db_path, 1) == raw_before
    assert [row[2] for row in after] == [1, 2]
    assert [row[0] for row in after] == [
        make_profile_id(CONVERSATION_ID, 1),
        make_profile_id(CONVERSATION_ID, 2),
    ]
    assert all(json.loads(row[3])["version"] == row[2] for row in after)


def test_merge_accumulates_sample_size_and_merges_evidence(tmp_path):
    """验收 ③：同一 trait_key 跨批次 → confidence 加权平均、sample_size 累加、证据合并去重。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    first = update_profile(CONVERSATION_ID, db_path=db_path)
    a1 = entry_of(first.snapshot, "A.request_style")

    append_messages(db_path, 40, start_seq=50)
    analyze(db_path)
    second = update_profile(CONVERSATION_ID, db_path=db_path)
    a2 = entry_of(second.snapshot, "A.request_style")

    assert a2["entry_key"] == a1["entry_key"]            # supported → 沿用同一条目
    assert a2["first_version"] == 1 and a2["last_updated_version"] == 2
    assert a2["sample_size"] == a1["sample_size"] + 20   # 新批次里 A 占 20 条
    assert set(a1["evidence_message_ids"]) < set(a2["evidence_message_ids"])
    assert len(a2["evidence_message_ids"]) == len(set(a2["evidence_message_ids"]))
    assert a2["support_count"] > a1["support_count"]
    v1_snapshot = json.loads(raw_snapshot(db_path, 1))
    assert entry_of(v1_snapshot, "A.request_style")["sample_size"] == a1["sample_size"]

    # 第二次合并没有新批次 → 不再累加（幂等）
    third = update_profile(CONVERSATION_ID, db_path=db_path)
    assert third.status == STATUS_NOTHING_TO_DO
    assert entry_of(load_latest_profile(CONVERSATION_ID, db_path=db_path).snapshot, "A.request_style")[
        "sample_size"
    ] == a2["sample_size"]


def test_evidence_quotes_and_speaker_roles_survive_merge(tmp_path):
    """验收 ③：证据明细（脱敏 quote + 真实说话人）在合并后仍在，且顺序与 id 列表一致。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    first = update_profile(CONVERSATION_ID, db_path=db_path)
    a1 = entry_of(first.snapshot, "A.request_style")

    assert [item["message_id"] for item in a1["evidence"]] == a1["evidence_message_ids"]
    assert a1["evidence"] and all(item["speaker_role"] == "A" for item in a1["evidence"])
    assert all(item["quote"] for item in a1["evidence"])


# ---------------------------------------------------------------- 验收 ②/④ 直接查库


def test_load_helpers_read_back_what_was_written(tmp_path):
    """落库后 `load_profile_versions()` / `load_latest_profile()` / `load_analyses()` 能读回。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    report = update_profile(CONVERSATION_ID, db_path=db_path)

    versions = load_profile_versions(CONVERSATION_ID, db_path=db_path)
    latest = load_latest_profile(CONVERSATION_ID, db_path=db_path)
    analyses = load_analyses(CONVERSATION_ID, db_path=db_path)

    assert [item.version for item in versions] == [1]
    assert latest is not None and latest.version == 1
    assert latest.covered_analyses == report.snapshot["covered_analyses"]
    assert [item.batch_index for item in analyses] == [0]
    assert all(item.is_parsed for item in analyses)
    assert load_latest_profile("other-conversation", db_path=db_path) is None

# ---------------------------------------------------------------- 纯函数：合并规则

def _previous_from(result, version: int) -> ProfileVersionRecord:
    """把 `merge_profile()` 的结果包成一个「库里读出来的」旧版记录。"""
    return ProfileVersionRecord(
        id=make_profile_id(CONVERSATION_ID, version),
        conversation_id=CONVERSATION_ID,
        version=version,
        snapshot=result.snapshot,
        changelog=result.changelog,
        message_count=result.message_count,
        created_at="2026-09-22T00:00:00Z",
    )


def test_supported_keeps_historical_statement_and_blends_confidence():
    """验收 ③：supported 只动数值与证据，**不改写历史表述**。"""
    first = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=1,
        analyses=[
            make_analysis(
                0,
                profile=make_profile(
                    a=[tendency("A.request_style", STATEMENT_V1, confidence=0.5, sample_size=40, evidence=("m-1",))]
                ),
            )
        ],
        message_count=40,
    )
    second = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=2,
        analyses=[
            make_analysis(
                1,
                profile=make_profile(
                    a=[tendency("A.request_style", STATEMENT_V2_SIMILAR, confidence=0.45, sample_size=10, evidence=("m-2",))]
                ),
            )
        ],
        previous=_previous_from(first, 1),
        message_count=50,
    )

    assert second.change_counts == {CHANGE_ADDED: 0, CHANGE_SUPPORTED: 1, CHANGE_WEAKENED: 0, CHANGE_REVISED: 0}
    entry = entry_of(second.snapshot, "A.request_style")
    assert entry["statement"] == STATEMENT_V1                    # 历史表述不漂移
    assert entry["confidence"] == 0.49                           # (0.5*40 + 0.45*10) / 50
    assert entry["sample_size"] == 50
    assert entry["evidence_message_ids"] == ["m-1", "m-2"]
    assert entry["first_version"] == 1 and entry["last_updated_version"] == 2
    assert entry_of(first.snapshot, "A.request_style")["statement"] == STATEMENT_V1


def test_weakened_merge_lowers_confidence_without_new_entry():
    """weakened：表述相似但置信度显著下滑 → 沿用条目、置信度被拉低（不新增 revision）。"""
    first = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=1,
        analyses=[make_analysis(0, profile=make_profile(a=[tendency("A.request_style", STATEMENT_V1, confidence=0.8, sample_size=40, evidence=("m-1",))]))],
        message_count=40,
    )
    frozen = deepcopy(first.snapshot)

    second = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=2,
        analyses=[make_analysis(1, profile=make_profile(a=[tendency("A.request_style", STATEMENT_V2_SIMILAR, confidence=0.3, sample_size=10, evidence=("m-2",))]))],
        previous=_previous_from(first, 1),
        message_count=50,
    )

    assert second.change_counts[CHANGE_WEAKENED] == 1
    entry = entry_of(second.snapshot, "A.request_style")
    assert entry["entry_key"] == "A.request_style@v1"
    assert entry["statement"] == STATEMENT_V1
    assert entry["confidence"] == 0.7                            # (0.8*40 + 0.3*10) / 50
    assert entry["evidence_message_ids"] == ["m-1", "m-2"]
    assert second.snapshot["counts"]["superseded_traits"] == 0
    assert first.snapshot == frozen                                # 旧快照对象未被就地改写


def test_revision_adds_entry_and_records_revision_of():
    """验收 ③：结论被改写 → 新增带 revision_of 的条目，旧条目留档标 superseded。"""
    first = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=1,
        analyses=[make_analysis(0, profile=make_profile(a=[tendency("A.request_style", STATEMENT_V1, confidence=0.6, sample_size=20, evidence=("m-1", "m-2"))]))],
        message_count=20,
    )
    frozen = deepcopy(first.snapshot)

    second = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=2,
        analyses=[make_analysis(1, profile=make_profile(a=[tendency("A.request_style", STATEMENT_V2_REWRITTEN, confidence=0.7, sample_size=20, evidence=("m-3",))]))],
        previous=_previous_from(first, 1),
        message_count=40,
    )

    assert second.change_counts[CHANGE_REVISED] == 1
    assert second.snapshot["supersedes_version"] == 1
    assert second.snapshot["counts"]["active_traits"] == 1
    assert second.snapshot["counts"]["superseded_traits"] == 1
    assert [item["entry_key"] for item in second.snapshot["traits"]] == [
        "A.request_style@v1",
        "A.request_style@v2",
    ]

    old = entry_of(second.snapshot, "A.request_style", status=TRAIT_STATUS_SUPERSEDED)
    new = entry_of(second.snapshot, "A.request_style", status=TRAIT_STATUS_ACTIVE)
    assert old["statement"] == STATEMENT_V1
    assert old["superseded_at_version"] == 2 and old["superseded_by"] == "A.request_style@v2"
    assert new["entry_key"] == "A.request_style@v2"
    assert new["first_version"] == 2 and new["last_updated_version"] == 2
    assert new["statement"] == STATEMENT_V2_REWRITTEN
    assert new["revision_of"]["entry_key"] == "A.request_style@v1"
    assert new["revision_of"]["statement"] == STATEMENT_V1
    assert new["revision_of"]["version"] == 1

    assert first.snapshot == frozen                               # 旧快照不被就地改写
    assert entry_of(first.snapshot, "A.request_style")["status"] == TRAIT_STATUS_ACTIVE
    revised = second.changelog["changes"][CHANGE_REVISED][0]
    assert revised["previous_statement"] == STATEMENT_V1
    assert revised["revision_of"]["entry_key"] == "A.request_style@v1"
    assert revised["evidence_message_ids"] == ["m-3"]


def test_covered_analyses_union_is_deduped():
    """`covered_analyses` 是并集：同一批次被重复折入也不会出现两次（幂等的基础）。"""
    analyses = [make_analysis(0, profile=make_profile(a=[tendency("A.request_style", STATEMENT_V1)]))]
    first = merge_profile(
        conversation_id=CONVERSATION_ID, version=1, analyses=analyses, message_count=20
    )
    second = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=2,
        analyses=[make_analysis(1, profile=make_profile(a=[tendency("A.request_style", STATEMENT_V1)]))],
        previous=_previous_from(first, 1),
        message_count=40,
        carried_analyses=analyses,
    )

    assert second.snapshot["covered_analyses"] == ["an-0", "an-1"]
    assert second.snapshot["covered_batch_indexes"] == [0, 1]
    assert second.snapshot["message_count"] == 40
    assert second.changelog["based_on_analyses"] == ["an-1"]


def test_snapshot_to_sections_splits_by_owner():
    """快照按 A / B / dyad / other 分栏（T-006 直接用）。"""
    result = merge_profile(
        conversation_id=CONVERSATION_ID,
        version=1,
        analyses=[
            make_analysis(
                0,
                profile=make_profile(
                    a=[tendency("A.request_style", STATEMENT_V1)],
                    b=[tendency("B.reply_style", "B 的回复通常偏简短。")],
                    dyad=[tendency("dyad.conflict_escalation", "话题在分歧后容易升级。")],
                ),
            )
        ],
        message_count=20,
    )

    sections = snapshot_to_sections(result.snapshot)
    assert [item["trait_key"] for item in sections["A"]] == ["A.request_style"]
    assert [item["trait_key"] for item in sections["B"]] == ["B.reply_style"]
    assert [item["trait_key"] for item in sections["dyad"]] == ["dyad.conflict_escalation"]
    assert sections["other"] == []
    assert result.snapshot["counts"]["active_traits"] == 3

# ---------------------------------------------------------------- 坏数据 / 越界

def test_broken_result_json_is_skipped_with_warning(tmp_path):
    """`result_json` 解析不了的批次：记 warning 后跳过，且**不计入** covered_analyses。"""
    db_path = seed_conversation(tmp_path, 50)
    analyze(db_path)
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("UPDATE analyses SET result_json = ?", ("{不是合法 JSON",))
    finally:
        conn.close()

    report = update_profile(CONVERSATION_ID, db_path=db_path)

    assert report.status == STATUS_NOTHING_TO_DO
    assert report.warnings and any(WARNING_BROKEN_ANALYSIS in item for item in report.warnings)
    assert fetch_rows(db_path, "profile_versions") == []


def test_broken_batch_is_not_recorded_as_covered(tmp_path):
    """坏批次不进 covered_analyses：修好后再跑仍会被纳入（不会漏账）。"""
    db_path = seed_conversation(tmp_path, 100)
    analyze(db_path)
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("UPDATE analyses SET result_json = ? WHERE batch_index = 1", ("null",))
    finally:
        conn.close()

    first = update_profile(CONVERSATION_ID, db_path=db_path)

    assert first.status == STATUS_MERGED and first.version == 1
    assert first.analyses_used == 1 and first.analyses_skipped == 0
    broken = [item.id for item in load_analyses(CONVERSATION_ID, db_path=db_path) if not item.is_parsed]
    assert len(broken) == 1
    assert not set(first.snapshot["covered_analyses"]) & set(broken)
    assert first.snapshot["covered_batch_indexes"] == [0]

    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("UPDATE analyses SET result_json = ? WHERE batch_index = 1", (json.dumps(make_profile(a=[tendency("A.request_style", STATEMENT_V1)]), ensure_ascii=False),))
    finally:
        conn.close()

    second = update_profile(CONVERSATION_ID, db_path=db_path)

    assert second.version == 2 and second.analyses_used == 1
    assert set(second.snapshot["covered_analyses"]) == set(first.snapshot["covered_analyses"]) | set(broken)


def test_update_profile_rejects_analyses_from_another_conversation(tmp_path):
    """防串会话：传入别的会话的 analyses 直接拒绝，不写任何行。"""
    db_path = seed_conversation(tmp_path, 50)
    foreign = make_analysis(
        0,
        profile=make_profile(a=[tendency("A.request_style", STATEMENT_V1)]),
        conversation_id="conv-other-999",
    )

    with pytest.raises(ValueError):
        update_profile(CONVERSATION_ID, db_path=db_path, analyses=[foreign])

    assert fetch_rows(db_path, "profile_versions") == []


def test_profile_versions_written_by_two_conversations_stay_separate(tmp_path):
    """同一个库里两个会话各自升版本，互不影响。"""
    db_path = seed_conversation(tmp_path, 25, conversation_id="conv-a")
    import_chat(number_of_lines(25), "conv-b", db_path=db_path)
    analyze(db_path, conversation_id="conv-a")
    analyze(db_path, conversation_id="conv-b")

    first_a = update_profile("conv-a", db_path=db_path)
    first_b = update_profile("conv-b", db_path=db_path)

    assert (first_a.version, first_b.version) == (1, 1)
    assert first_a.profile_id != first_b.profile_id
    assert load_latest_profile("conv-a", db_path=db_path).snapshot["conversation_id"] == "conv-a"
    assert load_latest_profile("conv-b", db_path=db_path).snapshot["conversation_id"] == "conv-b"
    assert len(fetch_rows(db_path, "profile_versions")) == 2


# ---------------------------------------------------------------- traits 纯函数


def test_classify_change_covers_four_kinds():
    assert classify_change(None, {"statement": STATEMENT_V1, "confidence": 0.5}).kind == CHANGE_ADDED
    assert (
        classify_change(
            {"statement": STATEMENT_V1, "confidence": 0.5},
            {"statement": STATEMENT_V2_SIMILAR, "confidence": 0.45},
        ).kind
        == CHANGE_SUPPORTED
    )
    assert (
        classify_change(
            {"statement": STATEMENT_V1, "confidence": 0.8},
            {"statement": STATEMENT_V1, "confidence": 0.3},
        ).kind
        == CHANGE_WEAKENED
    )
    assert (
        classify_change(
            {"statement": STATEMENT_V1, "confidence": 0.7},
            {"statement": STATEMENT_V2_REWRITTEN, "confidence": 0.7},
        ).kind
        == CHANGE_REVISED
    )
    # 否定翻转（「总会」→「很少」）也算 weakened，而不是 revised
    assert (
        classify_change(
            {"statement": "A 总会主动回应。", "confidence": 0.6},
            {"statement": "A 很少主动回应。", "confidence": 0.5},
        ).kind
        == CHANGE_WEAKENED
    )
    # 模型显式声明 revision_of → 直接 revised
    explicit = classify_change(
        {"statement": STATEMENT_V1, "confidence": 0.7},
        {"statement": STATEMENT_V1, "confidence": 0.7, "revision_of": {"entry_key": "A.request_style@v1"}},
    )
    assert explicit.kind == CHANGE_REVISED
    assert explicit.as_dict()["kind"] == CHANGE_REVISED
    assert "reason" in explicit.as_dict()


def test_weighted_average_confidence_prefers_sample_size():
    assert (
        weighted_average_confidence(
            [{"confidence": 0.8, "sample_size": 40}, {"confidence": 0.3, "sample_size": 10}]
        )
        == 0.7
    )
    assert (
        weighted_average_confidence(
            [
                {"confidence": 0.6, "evidence_message_ids": ["a", "b"]},
                {"confidence": 0.3, "evidence_message_ids": ["c"]},
            ]
        )
        == 0.5
    )
    assert weighted_average_confidence([]) == 0.0


def test_merge_unique_ids_and_evidence_alias_keep_first_seen_order():
    assert merge_unique_ids(["a", "b"], ["b", "c"]) == ["a", "b", "c"]
    assert merge_evidence_ids(["m-2"], ["m-1", "m-2"]) == ["m-2", "m-1"]
    assert merge_unique_ids(None) == []
    assert merge_unique_ids("not-a-list") == []
    assert merge_unique_ids(["a", "", None, "a", "b"]) == ["a", "b"]


def test_trait_key_normalisation_is_conservative():
    assert normalise_trait_key("  A.request_style ") == "A.request_style"
    assert normalise_trait_key("A. request_style") == "A.request_style"
    assert normalise_trait_key("A.RequestStyle") == "A.RequestStyle"     # 不折叠大小写
    with pytest.raises(TypeError):
        normalise_trait_key(None)


def test_statement_similarity_is_symmetric_and_thresholded():
    assert statement_similarity(STATEMENT_V1, STATEMENT_V2_SIMILAR) > 0.5
    assert statement_similarity(STATEMENT_V1, STATEMENT_V2_REWRITTEN) < 0.5
    assert statement_similarity("A 通常在压力下沉默。", "A，通常在压力下沉默。") == 1.0
    assert statement_similarity(STATEMENT_V1, STATEMENT_V2_SIMILAR) == statement_similarity(
        STATEMENT_V2_SIMILAR, STATEMENT_V1
    )