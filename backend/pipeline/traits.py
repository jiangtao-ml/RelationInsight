"""T-005 trait（结论主键）定义与冲突策略。

规格来源
--------
- `TASKS.md` T-005：`trait_key` 使用 `claim_key`（如 `A.request_style`），跨批次稳定；
  新证据与旧结论的关系分四类：added / supported / weakened / revised；
  同一 `trait_key` 多次出现时 confidence 取加权平均、sample_size 累加、证据合并去重；
  新证据与旧结论矛盾时不删旧结论，新增一条 `revision_of` 指向旧版。
- `ARCHITECTURE.md` §4.6：`profile_versions` 只追加、不 UPDATE；修正 = 新 version。
- `ARCHITECTURE.md` §5：单批 `result_json` 的 `claim_key` 是结论主键（T-004 已按此落库）。

本模块只放**纯函数与常量**：判定规则、相似度、加权平均、证据合并。不碰数据库、不碰网络，
便于单测与人工复核。

合并规则（T-005 冻结）
----------------------
| 关系 | 触发条件 | 处理 |
|------|----------|------|
| added | 旧画像里没有该 `trait_key` | 采用本批数值与表述，`first_version` = 本版 |
| supported | 表述相似且置信度未明显下滑 | 加权平均 / 累加 / 去重；**表述保持旧版**（历史表述不发生静默漂移） |
| weakened | 表述相似但置信度显著下滑，或出现否定翻转 | 同 supported 的数值规则（加权平均自然下滑）；表述保持旧版 |
| revised | 表述明显改写，或模型显式给出 `revision_of` | 新条目采用本批数值与表述；旧条目**留在同一快照内**标 `superseded`，旧版本快照不动 |

阈值（`RULES_VERSION` 随阈值或规则变化一起升版本）：

- `SUPPORT_SIMILARITY_THRESHOLD = 0.5`：`statement` 归一化后的字符相似度 ≥ 该值即视为「同一结论的继续」。
- `WEAKEN_CONFIDENCE_DROP = 0.15`：新置信度比旧值低 0.15 及以上 → weakened。

要点：`revised` 是**唯一**会替换表述的关系；`supported` / `weakened` 只动数值与证据。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence

# ------------------------------------------------------------------ trait_key

#: `trait_key` 的规范形状：`A.xxx` / `B.xxx` / `dyad.xxx`，小写 + 下划线分词。
TRAIT_KEY_PATTERN = re.compile(r"^(?:A|B|dyad)\.[a-z0-9]+(?:_[a-z0-9]+)*$")

_WHITESPACE = re.compile(r"\s+")

#: 四类变更（`TASKS.md` T-005 指定词表，顺序即 changelog 的键顺序）。
CHANGE_ADDED = "added"
CHANGE_SUPPORTED = "supported"
CHANGE_WEAKENED = "weakened"
CHANGE_REVISED = "revised"
CHANGE_KINDS: tuple[str, ...] = (CHANGE_ADDED, CHANGE_SUPPORTED, CHANGE_WEAKENED, CHANGE_REVISED)

#: 合并规则版本；写进 `profile_versions.changelog_json.rules_version`。
#: 阈值变化或判定逻辑变化时必须升版本，便于区分「结论变化」与「规则变化」。
RULES_VERSION = "1.0"

SUPPORT_SIMILARITY_THRESHOLD = 0.5
WEAKEN_CONFIDENCE_DROP = 0.15

#: 否定词表：用于识别「同一结论但被推翻表述」（如「总会回应」→「很少回应」）。
NEGATION_MARKERS: tuple[str, ...] = (
    "很少",
    "从不",
    "几乎不",
    "未曾",
    "没有",
    "较少",
    "避免",
    "拒绝",
    "不再",
)

#: 结论归属（`dyad.*` 表示只对这段关系成立、不专属于某一方）。
TRAIT_OWNERS: tuple[str, ...] = ("A", "B", "dyad")


def normalise_trait_key(claim_key: Any) -> str:
    """把模型给的 `claim_key` 规范成 `trait_key`。

    只做两件事：去掉首尾空白、删掉内部空白（模型偶尔会写成 `A. request_style`）。
    **不做大小写折叠**：`A.RequestStyle` 与 `A.request_style` 视为两个键——
    宁可多留一条可疑结论，也不静默把两条不同的结论合并。
    """
    if not isinstance(claim_key, str):
        raise TypeError("claim_key 必须是字符串")
    return _WHITESPACE.sub("", claim_key.strip())


def is_well_formed_trait_key(trait_key: Any) -> bool:
    """是否符合 `A.xxx` / `B.xxx` / `dyad.xxx` 命名规范（不合规不丢弃，只记 warning）。"""
    return bool(isinstance(trait_key, str) and TRAIT_KEY_PATTERN.match(trait_key))


def owner_of(trait_key: Any) -> str:
    """取结论归属：`A` / `B` / `dyad`；无法判定时返回 `unknown`。"""
    text = trait_key if isinstance(trait_key, str) else ""
    if "." not in text:
        return "unknown"
    prefix = text.split(".", 1)[0]
    return prefix if prefix in TRAIT_OWNERS else "unknown"


def is_dyad_trait(trait_key: Any) -> bool:
    return owner_of(trait_key) == "dyad"


def make_entry_key(trait_key: str, first_version: int) -> str:
    """快照内条目的稳定标识。

    同一 `trait_key` 被 `revised` 后会得到新的 `entry_key`（`A.x@v3`），
    从而与新条目并存、互不覆盖——这是「不删除旧结论」的落地方式。
    """
    if isinstance(first_version, bool) or not isinstance(first_version, int) or first_version < 1:
        raise ValueError("first_version 必须是 >= 1 的整数")
    return f"{trait_key}@v{first_version}"


# ------------------------------------------------------------------ 表述相似度

_STATEMENT_NOISE = re.compile(r"[\s，。、；：！？,.!?;:\u201c\u201d\u2018\u2019（）()\[\]【】《》—\-~·…]+")


def normalise_statement(text: Any) -> str:
    """去掉空白与标点，只留下可比对的字面（中文按字比）。"""
    if not isinstance(text, str):
        return ""
    return _STATEMENT_NOISE.sub("", text.strip())


def statement_similarity(left: Any, right: Any) -> float:
    """两条表述的相似度（0~1，字符级）。空串一律视为 0.0。"""
    a, b = normalise_statement(left), normalise_statement(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return round(SequenceMatcher(None, a, b).ratio(), 4)


def negation_markers(text: Any) -> frozenset[str]:
    body = text if isinstance(text, str) else ""
    return frozenset(marker for marker in NEGATION_MARKERS if marker in body)


def has_negation_flip(old_statement: Any, new_statement: Any) -> bool:
    """新表述与旧表述的否定词集合不同（多出或少了否定）→ 视为被削弱。"""
    return bool(negation_markers(new_statement) ^ negation_markers(old_statement))


# ------------------------------------------------------------------ 数值工具


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def confidence_weight(observation: Mapping[str, Any]) -> int:
    """加权平均的权重：优先 `sample_size`，其次证据条数，兜底 1。"""
    sample_size = _as_int(observation.get("sample_size"), 0)
    if sample_size > 0:
        return sample_size
    evidence = observation.get("evidence_message_ids") or ()
    if not isinstance(evidence, (str, bytes)) and isinstance(evidence, Sequence) and len(evidence) > 0:
        return len(evidence)
    return 1


def weighted_average_confidence(observations: Sequence[Mapping[str, Any]]) -> float:
    """按 `confidence_weight()` 加权的置信度平均；权重全为 0 时退化为算术平均。"""
    items = [o for o in observations if isinstance(o, Mapping)]
    if not items:
        return 0.0
    pairs = [(_as_float(o.get("confidence"), 0.0), confidence_weight(o)) for o in items]
    total = sum(weight for _confidence, weight in pairs)
    if total <= 0:
        return round(sum(confidence for confidence, _weight in pairs) / len(pairs), 4)
    return round(sum(confidence * weight for confidence, weight in pairs) / total, 4)


def merge_unique_ids(*groups: Iterable[Any] | None) -> list[str]:
    """合并去重，保持首次出现顺序（旧的在先）；非字符串与空串被忽略。"""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if group is None or isinstance(group, (str, bytes)):
            continue
        for item in group:
            if isinstance(item, str) and item and item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


#: 领域内的别名：合并证据 `message_id` 列表。
merge_evidence_ids = merge_unique_ids


# ------------------------------------------------------------------ 变更判定


@dataclass(frozen=True)
class ChangeClassification:
    """一条新观测与旧结论的关系判定结果。"""

    kind: str
    reason: str
    similarity: float | None = None

    @property
    def is_new(self) -> bool:
        return self.kind == CHANGE_ADDED

    @property
    def is_revision(self) -> bool:
        return self.kind == CHANGE_REVISED

    def as_dict(self) -> dict:
        payload = {"kind": self.kind, "reason": self.reason}
        if self.similarity is not None:
            payload["statement_similarity"] = self.similarity
        return payload


def classify_change(
    old: Mapping[str, Any] | None,
    new: Mapping[str, Any],
    *,
    similarity_threshold: float = SUPPORT_SIMILARITY_THRESHOLD,
    weaken_drop: float = WEAKEN_CONFIDENCE_DROP,
) -> ChangeClassification:
    """判定新观测相对旧结论属于 added / supported / weakened / revised 中的哪一类。

    `old=None` 表示旧画像里没有该 `trait_key`；`new` 需含 `statement` 与 `confidence`，
    若带非空 `revision_of` 则直接判为 revised（模型显式声明修订）。
    """
    if old is None:
        return ChangeClassification(CHANGE_ADDED, "旧画像中没有该 trait_key，作为新增结论")

    if new.get("revision_of"):
        return ChangeClassification(CHANGE_REVISED, "模型显式给出了 revision_of，按修订处理")

    similarity = statement_similarity(old.get("statement"), new.get("statement"))
    if similarity < similarity_threshold:
        return ChangeClassification(
            CHANGE_REVISED,
            f"表述相似度 {similarity} < {similarity_threshold}，视为结论被改写",
            similarity,
        )

    old_confidence = _as_float(old.get("confidence"), 0.0)
    new_confidence = _as_float(new.get("confidence"), 0.0)
    if new_confidence <= old_confidence - weaken_drop:
        return ChangeClassification(
            CHANGE_WEAKENED,
            f"置信度由 {old_confidence} 降到 {new_confidence}（跌幅 ≥ {weaken_drop}），视为被削弱",
            similarity,
        )

    if has_negation_flip(old.get("statement"), new.get("statement")):
        return ChangeClassification(
            CHANGE_WEAKENED, "新表述出现否定翻转（如「总会」→「很少」），视为被削弱", similarity
        )

    return ChangeClassification(
        CHANGE_SUPPORTED, f"表述相似度 {similarity} 且置信度未明显下滑，视为获得新证据支持", similarity
    )


# ------------------------------------------------------------------ 数值合并


def fold_new_observations(observations: Sequence[Mapping[str, Any]]) -> dict:
    """把**本次合并要纳入**的同一 `trait_key` 的多条观测先并成一条。

    多条观测可能来自同一批次内的重复结论，也可能来自多个待合并批次：
    confidence 按权重求平均、sample_size 累加、证据合并去重、`support_count` 计数。
    表述取**最后一条**（按批次升序排列后的最新表述）；若其中任一条显式声明了
    `revision_of`，则以该条为准并置 `explicit_revision=True`。
    """
    items = [o for o in observations if isinstance(o, Mapping)]
    if not items:
        raise ValueError("observations 不能为空")

    explicit = [o for o in items if o.get("revision_of")]
    chosen = explicit[-1] if explicit else items[-1]

    return {
        "statement": str(chosen.get("statement") or ""),
        "confidence": weighted_average_confidence(items),
        "sample_size": sum(_as_int(o.get("sample_size"), 0) for o in items),
        "evidence_message_ids": merge_unique_ids(*[o.get("evidence_message_ids") for o in items]),
        "support_count": sum(_as_int(o.get("support_count"), 1) or 1 for o in items),
        "sources": merge_unique_ids(*[o.get("sources") for o in items]),
        "explicit_revision": bool(explicit),
        "revision_of": dict(explicit[-1].get("revision_of")) if explicit else None,
        "evidence_meta": _merge_evidence_meta(items),
    }


def _merge_evidence_meta(items: Sequence[Mapping[str, Any]]) -> dict[str, dict]:
    """合并各观测携带的证据元数据（quote / speaker_role），同一 message_id 先到先得。"""
    merged: dict[str, dict] = {}
    for item in items:
        meta = item.get("evidence_meta") or {}
        if not isinstance(meta, Mapping):
            continue
        for message_id, payload in meta.items():
            if isinstance(message_id, str) and message_id and message_id not in merged:
                merged[message_id] = dict(payload) if isinstance(payload, Mapping) else {}
    return merged


def combine_observation(
    old: Mapping[str, Any] | None,
    new: Mapping[str, Any],
    *,
    kind: str,
    support_count: int | None = None,
) -> dict:
    """把一条新观测折进旧条目（added / supported / weakened 三类共用）。

    - `old is None`（added）：直接采用新观测的表述与数值。
    - 否则：confidence 加权平均、sample_size 累加、证据合并去重、`support_count` 累加，
      **表述保持旧版**——表述只在 `revised` 时替换（见 `classify_change`）。
    """
    new_evidence = new.get("evidence_message_ids")
    new_sample_size = _as_int(new.get("sample_size"), 0)
    new_confidence = _as_float(new.get("confidence"), 0.0)
    new_support = _as_int(support_count if support_count is not None else new.get("support_count"), 1) or 1

    if old is None:
        return {
            "statement": str(new.get("statement") or ""),
            "confidence": round(new_confidence, 4),
            "sample_size": new_sample_size,
            "evidence_message_ids": merge_unique_ids(new_evidence),
            "support_count": new_support,
        }

    return {
        "statement": str(old.get("statement") or ""),
        "confidence": weighted_average_confidence([old, new]),
        "sample_size": _as_int(old.get("sample_size"), 0) + new_sample_size,
        "evidence_message_ids": merge_unique_ids(old.get("evidence_message_ids"), new_evidence),
        "support_count": _as_int(old.get("support_count"), 0) + new_support,
    }


def describe_rules() -> dict:
    """规则摘要（进 changelog，便于事后解释「为什么这条被判成 revised」）。"""
    return {
        "rules_version": RULES_VERSION,
        "support_similarity_threshold": SUPPORT_SIMILARITY_THRESHOLD,
        "weaken_confidence_drop": WEAKEN_CONFIDENCE_DROP,
        "change_kinds": list(CHANGE_KINDS),
        "confidence_aggregation": "weighted_average_by_sample_size",
        "sample_size_aggregation": "sum",
        "evidence_aggregation": "merge_unique_ids",
        "statement_replaced_only_on": CHANGE_REVISED,
        "negation_markers": list(NEGATION_MARKERS),
    }