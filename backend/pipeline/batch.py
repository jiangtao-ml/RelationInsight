"""T-004 分批逻辑：每 50 条一批、样本量门闩、余数批的元数据。

规格来源
--------
- `TASKS.md` T-004：批次大小 = 50；输出「每批一条 `analyses` + 多条 `evidence`」。
- `ARCHITECTURE.md` §2.1：主路径为「消息数 ≥ 20? → 否：提示样本不足；是：分批 50 条」。
- `TASKS.md` T-004 假设：**余数 < 50 的最后一批仍调用一次模型**，样本量写入该批元数据
  （不丢弃余数、不把余数并进上一批）。

本模块只做「切批 + 校验」，不碰网络、不碰数据库，便于单测。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

BATCH_SIZE = 50
MIN_MESSAGES_FOR_ANALYSIS = 20


def field_of(item: Any, key: str, default: Any = None) -> Any:
    """按 `dict` 或属性名取值（同时接受 `MessageDTO`、`sqlite3.Row` 与 dict）。"""
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


class InsufficientSampleError(ValueError):
    """消息总数不足，拒绝做**正式**画像分析。

    `TASKS.md` T-004 验收标准 ④：消息总数 < 20 时管道拒绝正式分析并返回「样本不足」。
    """

    def __init__(self, message_count: int, minimum: int = MIN_MESSAGES_FOR_ANALYSIS) -> None:
        self.message_count = int(message_count)
        self.minimum = int(minimum)
        super().__init__(
            f"样本不足：当前仅有 {self.message_count} 条消息，正式画像分析至少需要 "
            f"{self.minimum} 条。可先补充对话或仅做原文查看；本次不生成正式画像。"
        )


@dataclass(frozen=True)
class Batch:
    """一个待分析的批次（消息按 `seq` 升序，来自同一会话）。"""

    batch_index: int
    messages: tuple[Any, ...]
    seq_from: int
    seq_to: int
    message_id_from: str
    message_id_to: str
    is_remainder: bool

    @property
    def size(self) -> int:
        return len(self.messages)

    @property
    def sample_size(self) -> int:
        """写入该批元数据的样本量（余数批即其实际条数）。"""
        return len(self.messages)

    @property
    def message_ids(self) -> list[str]:
        return [str(field_of(m, "message_id")) for m in self.messages]


@dataclass
class BatchPlan:
    """一次分析的完整切批结果。"""

    conversation_id: str | None
    batches: list[Batch] = field(default_factory=list)
    total_messages: int = 0
    batch_size: int = BATCH_SIZE

    @property
    def batch_count(self) -> int:
        return len(self.batches)

    @property
    def full_batch_count(self) -> int:
        return sum(1 for b in self.batches if not b.is_remainder)

    @property
    def remainder_batch(self) -> Batch | None:
        return next((b for b in self.batches if b.is_remainder), None)

    @property
    def remainder_size(self) -> int:
        batch = self.remainder_batch
        return batch.size if batch is not None else 0

    @property
    def message_ids(self) -> list[str]:
        return [mid for batch in self.batches for mid in batch.message_ids]

    def describe(self) -> str:
        """人可读的切批说明（进日志与报告，不含任何聊天原文）。"""
        if not self.batches:
            return f"总消息 0 条（batch_size={self.batch_size}），无可分析批次"
        parts = []
        if self.full_batch_count:
            parts.append(f"{self.full_batch_count} 个完整批（每批 {self.batch_size} 条）")
        if self.remainder_batch is not None:
            parts.append(f"1 个余数批（{self.remainder_size} 条，不足 {self.batch_size} 条，仍调用模型）")
        return f"总消息 {self.total_messages} 条 → " + " + ".join(parts)


def plan_batches(
    messages: Sequence[Any] | Any,
    *,
    batch_size: int = BATCH_SIZE,
    min_messages: int = MIN_MESSAGES_FOR_ANALYSIS,
    allow_below_minimum: bool = False,
) -> BatchPlan:
    """把消息序列切成若干批次。

    - 消息必须按 `seq` **升序**排列（否则抛 `ValueError`），保证批次边界稳定可复现。
    - `len(messages) < min_messages` 时抛 `InsufficientSampleError`（除非 `allow_below_minimum=True`，
      该开关仅供「预览草稿」等非正式路径使用）。
    - 余数批不丢弃、不合并：`< batch_size` 的最后一批照样成为独立批次，`is_remainder=True`。
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size 必须是 >= 1 的整数")
    if isinstance(min_messages, bool) or not isinstance(min_messages, int) or min_messages < 1:
        raise ValueError("min_messages 必须是 >= 1 的整数")
    if messages is None or isinstance(messages, (str, bytes, Mapping)):
        raise ValueError("messages 必须是消息序列（MessageDTO / dict 列表），不能是字符串或字典")

    items = list(messages)

    seqs: list[int] = []
    for index, item in enumerate(items):
        message_id = field_of(item, "message_id")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError(f"第 {index} 条消息缺少 message_id")
        seq = field_of(item, "seq", index)
        if isinstance(seq, bool) or not isinstance(seq, int):
            raise ValueError(f"第 {index} 条消息（{message_id}）缺少整数 seq")
        seqs.append(seq)

    for previous, current in zip(seqs, seqs[1:]):
        if current < previous:
            raise ValueError("messages 必须按 seq 升序排列（分批边界依赖导入顺序）")

    total = len(items)
    if total < min_messages and not allow_below_minimum:
        raise InsufficientSampleError(total, min_messages)

    conversation_ids = {
        field_of(item, "conversation_id") for item in items if field_of(item, "conversation_id")
    }
    conversation_id = sorted(conversation_ids)[0] if len(conversation_ids) == 1 else None

    batches: list[Batch] = []
    for start in range(0, total, batch_size):
        chunk = items[start : start + batch_size]
        is_remainder = len(chunk) < batch_size
        batches.append(
            Batch(
                batch_index=len(batches),
                messages=tuple(chunk),
                seq_from=seqs[start],
                seq_to=seqs[start + len(chunk) - 1],
                message_id_from=str(field_of(chunk[0], "message_id")),
                message_id_to=str(field_of(chunk[-1], "message_id")),
                is_remainder=is_remainder,
            )
        )

    return BatchPlan(
        conversation_id=conversation_id,
        batches=batches,
        total_messages=total,
        batch_size=batch_size,
    )
