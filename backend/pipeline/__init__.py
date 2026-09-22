"""T-004 分批分析管道包。

对外只需记住三个名字：

- `analyze_conversation(messages, client, ...)`：消息 → 分批 → 模型 → 校验 → 落库。
- `analyze_conversation_from_db(conversation_id, client, ...)`：同上，但消息从库里读。
- `plan_batches(messages)`：只看切批结果（不调模型、不碰库）。

典型用法（T-006/T-007 可直接照抄）::

    from llm import DeepSeekClient
    from pipeline import analyze_conversation_from_db

    report = analyze_conversation_from_db("conv-1", DeepSeekClient())
    if not report.ok:
        print(report.message)   # 例如：样本不足 / 分析中断
"""

from __future__ import annotations

from .batch import (
    BATCH_SIZE,
    MIN_MESSAGES_FOR_ANALYSIS,
    Batch,
    BatchPlan,
    InsufficientSampleError,
    plan_batches,
)
from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_system_prompt
from .run import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_SKIPPED_EXISTING,
    BATCH_STATUS_WRITTEN,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INSUFFICIENT_SAMPLE,
    QUOTE_MAX_CHARS,
    REASON_EVIDENCE_NOT_IN_BATCH,
    REASON_EVIDENCE_NOT_IN_DB,
    REASON_NO_EVIDENCE,
    STATUS_NOTHING_TO_DO,
    BatchOutcome,
    DroppedItem,
    FilteredProfile,
    PipelineReport,
    analyze_conversation,
    analyze_conversation_from_db,
    filter_profile,
    load_messages,
    make_analysis_id,
    make_evidence_id,
    normalise_quote,
    persist_batch,
)

__all__ = [
    "BATCH_SIZE",
    "MIN_MESSAGES_FOR_ANALYSIS",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "BATCH_STATUS_FAILED",
    "BATCH_STATUS_SKIPPED_EXISTING",
    "BATCH_STATUS_WRITTEN",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_INSUFFICIENT_SAMPLE",
    "QUOTE_MAX_CHARS",
    "REASON_EVIDENCE_NOT_IN_BATCH",
    "REASON_EVIDENCE_NOT_IN_DB",
    "REASON_NO_EVIDENCE",
    "STATUS_NOTHING_TO_DO",
    "Batch",
    "BatchOutcome",
    "BatchPlan",
    "DroppedItem",
    "FilteredProfile",
    "InsufficientSampleError",
    "PipelineReport",
    "analyze_conversation",
    "analyze_conversation_from_db",
    "build_system_prompt",
    "filter_profile",
    "load_messages",
    "make_analysis_id",
    "make_evidence_id",
    "normalise_quote",
    "persist_batch",
    "plan_batches",
]
