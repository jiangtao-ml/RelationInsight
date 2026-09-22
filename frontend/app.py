"""T-006 Streamlit 前端原型：文本导入 / A-B 标记 / 行为倾向卡片 / 证据列表。

设计约束（TASKS.md T-006）
--------------------------
1. **不启动 FastAPI 也能演示**：③ 画像卡片、④ 证据列表读 `frontend/fixtures/mock_profile.json`；
   ① 导入预览、② A/B 标记只用本进程内存里的示例文本 + `backend/parser.py`（纯函数，不碰数据库）。
2. 证据行展示 `message_id` + **脱敏后** quote（策略 α，见 `ARCHITECTURE.md` §4.5）。
3. 顶部有同意勾选框：文案**逐字取自 `PRIVACY.md` §1.3**（引用 `backend/privacy.py` 常量，不复制改写）；
   勾选后可 `POST /conversations/{id}/consent` 写入 `consents`；未勾选时「开始分析」按钮禁用（PRIVACY §1.1）。
   T-007 另加：主区「删除本会话」、设置页「清空全部本地数据」——两者都必须二次确认（PRIVACY.md §2.2）。
4. **不做诊断式标题**：全部文案为「行为倾向 / 可能与相处模式有关」，不出现人格标签、不做心理诊断、
   不提供操控或读心建议。

运行
----
    cd C:\\Users\\17352\\Desktop\\RelationInsight
    backend\\.venv\\Scripts\\python.exe -m streamlit run frontend/app.py

本页**不直接读写数据库**：导入 / 同意 / 分析 / 画像读取 / 删除全部走后端 HTTP API
（`RELATIONINSIGHT_API_BASE`，默认 `http://127.0.0.1:8000`）。后端离线时自动降级为只读演示——
① ② 用内存解析（不写库），③ ④ 回退到 `frontend/fixtures/mock_profile.json`，写库动作明确提示「未连接后端」。

T-008 接线（不改动 T-001–T-007 已冻结的接口契约）：

| 界面动作 | 后端调用 |
|----------|----------|
| ①「导入到数据库」 | `POST /conversations/{id}/messages:import` |
| 顶部「提交同意并写入 consents」 | `POST /conversations/{id}/consent`（T-007，已接线） |
| ②「开始分析（先验同意闸门）」 | `POST /conversations/{id}/analyze`（T-007，已接线） |
| ③ ④ 画像 / 证据 | `GET /conversations/{id}/profile`（**真实画像**；取不到才回退离线 fixture） |
| ②「删除本会话」/ 设置页「清空全部本地数据」 | `DELETE ...?confirm=true`（T-007，已接线） |

端到端自测使用 `FakeDeepSeekClient`（不调用真实 DeepSeek API）；最终验收由 WorkBuddy 按 `ACCEPTANCE.md` 执行。
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote as urlquote
from urllib.request import Request, urlopen

import streamlit as st

st.set_page_config(page_title="关系洞察 · 原型（非诊断）", layout="wide")

FRONTEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = FRONTEND_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
FIXTURE_PATH = FRONTEND_DIR / "fixtures" / "mock_profile.json"
DEFAULT_CONVERSATION_ID = "conv-demo-0001"

#: 后端 API 基址（T-007 接线用；默认本机 127.0.0.1，见 `ARCHITECTURE.md` §8「绑定默认 127.0.0.1」）。
API_BASE = os.environ.get("RELATIONINSIGHT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT_SECONDS = 3.0

#: 左侧预览用示例文本（演示 ① ② 两块）：63 条可解析消息 + 3 个空行 + 4 个错误行。
#: 内容纯属虚构；手机号 / 邮箱 / 银行卡号是占位样例，仅用于演示策略 α 脱敏。
DEMO_TEXT = """A: 周三的事我们再确认一下吧。
B: 好，你说。
A: 我这边下午三点之后都有空。
A: 周四下午我们直接去那家店，你到时候过来就行。
B: 三点吗？我可能要晚十分钟。
A: 可以，别迟到太多。
B: 好。
B: 上次也是因为我路上堵车，才晚了一会儿。
A: 嗯，那这次提前出门。
B: 行。

A: 还有件事，周末你爸妈那边要不要一起吃饭。
B: 我还没问他们，晚点回你。
A: 好，你尽快。
B: 我尽量。
A: 你每次都这样说。
B: 我确实需要先问过他们。
A: 我知道，但是时间要定下来。
B: 那我今天晚上就打电话。
A: 最好是这样，不然又要拖到下周。
B: 嗯。

A: 上次说好一起去看展，最后也没去成。
B: 那次是临时加班。
A: 我没说你故意，只是觉得计划总是变。
B: 我理解你的感受。
A: 你先按我说的做，别的地方不用改。
B: 好，我尽量配合。
A: 周五之前给我答复。
B: 我记下了。
A: 我手机换号了，新号是 13812345678。
B: 我存一下。
A:我明白了
（撤回了一条消息）
A: 邮箱也换了，现在用 demo.user@example.com。
B: 收到了，我晚点回你确认。
B: 不会。
A: 别又忘了。
A: 你最近回复消息都很慢。
B: 工作比较忙。
A: 忙到什么程度？
B: 每天加班到九点多。
A: 那你还有精力回别人消息吗？
B: 你的消息我都会回，只是慢一点。
C: 这是笔误
A: 嗯，我知道。
B: 那就好。
A: 不用问了，我已经定好了。
B: 那行，我听你的。
A: 报销单我填一下，卡号是 6222021234567890123。
B: 这个别发在聊天里。
A: 我知道了，下次注意。
B: 嗯。
A: 这个周末你有安排吗？
B: 暂时没有。

A: 那去看展吧，上次没去成。
B: 好，这次尽量去。
A: 别尽量，直接定下来。
B: 好，定周六下午。
A: 两点，我买票。
B: 好，我到时候找你。
A: 别再临时改。
B: 不会改了。
A: 上次也是这么说的。
B: 这次真的不会。
A: 
A: 那我们看情况。
B: 好。
A: 我先去忙了，晚上再说。
"""

# 复用后端实现（只导入纯函数）：不启动 FastAPI，也不读写数据库。
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from parser import parse_chat

    PARSER_SOURCE = "backend/parser.py（T-002）"
except ImportError as exc:  # pragma: no cover - 仅环境不完整时触发
    st.error(f"无法导入 `backend/parser.py`：{exc}")
    st.stop()

try:
    from pipeline import QUOTE_MAX_CHARS, snapshot_to_sections

    PIPELINE_SOURCE = "backend/pipeline/merge.py（`snapshot_to_sections()`，T-005）"
except ImportError as exc:  # pragma: no cover - 仅环境不完整时触发
    st.error(
        f"无法导入 `backend/pipeline`：{exc}\n\n请用仓库自带虚拟环境运行："
        "`backend\\.venv\\Scripts\\python.exe -m streamlit run frontend/app.py`"
    )
    st.stop()

try:
    from privacy import (  # noqa: F401  (T-007：同意书文案唯一来源，前端不复制改写)
        CONSENT_STATEMENT,
        CONSENT_STATEMENT_SOURCE,
        CONSENT_STATEMENT_VERSION,
        SCOPE_BOTH_PARTIES,
        SCOPE_SELF_ONLY,
        deletion_disclosures,
    )

    PRIVACY_SOURCE = "backend/privacy.py（T-007；文案逐字取自 PRIVACY.md §1.3）"
except ImportError as exc:  # pragma: no cover - 仅环境不完整时触发
    st.error(f"无法导入 `backend/privacy.py`：{exc}")
    st.stop()

DELETION_DISCLOSURES = tuple(deletion_disclosures())
SCOPE_LABELS = {
    SCOPE_BOTH_PARTIES: "双方知情同意（both_parties_informed）",
    SCOPE_SELF_ONLY: "仅分析我自己（self_only）",
}

# ------------------------------------------------------------------ 后端 API 客户端（T-007）


@dataclass(frozen=True)
class ApiResult:
    """一次后端调用的结果；`error` 只含状态码/异常类型，**不含**聊天原文。"""

    ok: bool
    status: int | None
    payload: Any = None
    error: str | None = None


def api_request(method: str, path: str, *, payload: Mapping[str, Any] | None = None) -> ApiResult:
    """调用后端（标准库 `urllib`，同步、短超时）。离线时返回 `ok=False`，绝不抛到界面上。"""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(f"{API_BASE}{path}", data=body, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:  # noqa: S310 - 固定本机基址
            raw = response.read().decode("utf-8")
            return ApiResult(True, int(response.status), json.loads(raw) if raw else None)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"detail": raw}
        return ApiResult(False, int(exc.code), detail, f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        return ApiResult(False, None, None, f"未连接后端 {API_BASE}（{type(exc).__name__}）")


def describe_failure(result: ApiResult) -> str:
    """把失败翻译成一句人话（不回显原文；后端 `detail.message` 也不含原文）。"""
    detail = result.payload.get("detail") if isinstance(result.payload, Mapping) else None
    if isinstance(detail, Mapping):
        kind = detail.get("kind") or "error"
        message = detail.get("message") or ""
        return f"{result.error or ''} · {kind}：{message}".strip(" ·")
    if isinstance(detail, str) and detail:
        return f"{result.error or ''} · {detail}".strip(" ·")
    return result.error or "未知错误"


def set_flash(level: str, text: str) -> None:
    """把一条提示存进 session state，下次 rerun 渲染（`st.rerun()` 会丢掉当前这一轮的提示）。"""
    st.session_state["flash"] = {"level": level, "text": text}


def render_flash() -> None:
    """渲染并清空上一步留下的提示。"""
    flash = st.session_state.pop("flash", None)
    if not isinstance(flash, Mapping):
        return
    text = str(flash.get("text") or "")
    level = flash.get("level")
    if level == "success":
        st.success(text)
    elif level == "warning":
        st.warning(text)
    elif level == "error":
        st.error(text)
    else:
        st.info(text)


def perform_deletion(key: str, path: str, *, label: str) -> None:
    """执行删除（总是带 `confirm=true` 二次确认）并把**无原文回执**存入 session state。"""
    result = api_request("DELETE", f"{path}?confirm=true")
    receipts = st.session_state.setdefault("deletion_receipts", {})
    if result.ok and isinstance(result.payload, Mapping):
        receipts[key] = result.payload
        set_flash("success", str(result.payload.get("message") or f"已删除{label}"))
    else:
        receipts.pop(key, None)
        set_flash("error", f"删除未执行（{label}）：{describe_failure(result)}")
    # 删除会改变画像可见性：丢掉画像缓存后重跑，让 ③ ④ 重新读真实画像（或回退演示数据）。
    invalidate_profile_cache()
    st.rerun()


def render_deletion_receipt(key: str) -> None:
    """渲染删除回执：时间 + 范围 + 各表行数（**不**回显原文）。"""
    receipts = st.session_state.get("deletion_receipts") or {}
    receipt = receipts.get(key) if isinstance(receipts, Mapping) else None
    if not isinstance(receipt, Mapping):
        return
    with st.container(border=True):
        st.markdown(f"**删除回执** · 时间 `{receipt.get('deleted_at')}` · 范围 `{receipt.get('scope')}`")
        rows = [{"表": name, "删除行数": count} for name, count in (receipt.get("deleted_rows") or {}).items()]
        if rows:
            st.dataframe(rows, hide_index=True)
        residual = receipt.get("residual") or {}
        st.caption(
            f"VACUUM：{receipt.get('vacuumed')} · 残留检查：扫描 {len(residual.get('scanned_files') or [])} 个文件 / "
            f"{residual.get('checked_needles')} 个原文片段 → 命中 {residual.get('hits')} 次"
            f"（命中文件：{residual.get('hit_files') or '无'}）"
        )
        st.caption(
            f"审计文件：`{receipt.get('audit_path')}`（只记时间 / 范围 / 行数，不记原文）· "
            f"临时文件已清理：{receipt.get('temp_files_removed') or '无'}"
        )
        st.caption("回执与日志**均不含聊天原文**；删除成功后本页不保留任何原文副本。")


# ------------------------------------------------------------------ 工具函数


@st.cache_data(show_spinner=False)
def load_snapshot() -> dict[str, Any]:
    """读入**离线演示**画像（`frontend/fixtures/mock_profile.json`，符合 `ARCHITECTURE.md` §5 快照结构）。"""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


#: T-008：③ ④ 优先读后端真实画像（`GET /conversations/{id}/profile`），失败才回退 fixture。
PROFILE_CACHE_PREFIX = "profile_payload::"
PROFILE_SOURCE_API = "后端真实画像（`GET /conversations/{id}/profile`）"
PROFILE_SOURCE_FIXTURE = "离线演示数据（`frontend/fixtures/mock_profile.json`）"


def profile_cache_key(conversation_id: str) -> str:
    return f"{PROFILE_CACHE_PREFIX}{conversation_id}"


def fetch_profile(conversation_id: str, *, refresh: bool = False) -> ApiResult:
    """读画像接口；结果缓存在 session state，避免每次 rerun 都打后端（离线时也不会反复等超时）。"""
    key = profile_cache_key(conversation_id)
    if refresh or key not in st.session_state:
        st.session_state[key] = api_request(
            "GET", f"/conversations/{urlquote(conversation_id, safe='')}/profile"
        )
    cached = st.session_state.get(key)
    return cached if isinstance(cached, ApiResult) else ApiResult(False, None, None, "未请求")


def resolve_snapshot(conversation_id: str, *, refresh: bool = False) -> tuple[dict[str, Any], str, ApiResult]:
    """返回 (快照, 来源说明, 最近一次请求结果)：真实画像优先，取不到则回退离线 fixture。"""
    result = fetch_profile(conversation_id, refresh=refresh)
    payload = result.payload if isinstance(result.payload, Mapping) else None
    snapshot = payload.get("snapshot") if payload else None
    if result.ok and isinstance(snapshot, Mapping):
        return dict(snapshot), PROFILE_SOURCE_API, result
    return load_snapshot(), PROFILE_SOURCE_FIXTURE, result


def invalidate_profile_cache(conversation_id: str | None = None) -> None:
    """丢掉画像缓存：写库动作后（导入 / 分析 / 删除）强制下次 rerun 重新拉真实画像。"""
    for key in [
        key for key in list(st.session_state.keys()) if str(key).startswith(PROFILE_CACHE_PREFIX)
    ]:
        if conversation_id is None or str(key) == profile_cache_key(conversation_id):
            st.session_state.pop(key, None)


def person_id_for(conversation_id: str, role: str) -> str:
    """`ARCHITECTURE.md` §4.1 冻结的 `person_id` 算法（本页只用于展示，不写库）。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"person:{conversation_id}:{role}"))


def role_from_person_id(conversation_id: str, person_id: str) -> str:
    for role in ("A", "B"):
        if person_id == person_id_for(conversation_id, role):
            return role
    return "?"


CHANGE_LABELS = {
    "added": "新增",
    "supported": "被支持",
    "weakened": "被削弱",
    "revised": "被修订",
}


def change_label(entry: Mapping[str, Any]) -> str:
    kind = str(entry.get("change_kind") or "")
    return CHANGE_LABELS.get(kind, kind or "—")


def render_trait_card(entry: Mapping[str, Any]) -> None:
    """一张结论卡片：statement + confidence + sample_size（验收 ③/④）。"""
    with st.container(border=True):
        superseded = entry.get("status") == "superseded"
        head = f"`{entry.get('trait_key')}`"
        if superseded:
            head += f" · 历史条目（已在 v{entry.get('superseded_at_version')} 被修订）"
        st.markdown(head)
        st.markdown(f"**{entry.get('statement') or '（无表述）'}**")
        m1, m2, m3 = st.columns(3)
        m1.metric("confidence", f"{float(entry.get('confidence') or 0.0):.2f}")
        m2.metric("sample_size", f"{int(entry.get('sample_size') or 0)}")
        m3.metric("support_count", f"{int(entry.get('support_count') or 0)}")
        revision_of = entry.get("revision_of")
        bits = [
            f"变更类型：{change_label(entry)}",
            f"首次出现：v{entry.get('first_version')}",
            f"最近更新：v{entry.get('last_updated_version')}",
            f"证据数：{len(entry.get('evidence_message_ids') or [])}",
        ]
        if isinstance(revision_of, Mapping):
            bits.append(f"修订自：{revision_of.get('entry_key')}（v{revision_of.get('version')}）")
        if superseded:
            bits.append(f"被 {entry.get('superseded_by')} 取代")
        st.caption(" · ".join(bits))
        st.caption(f"entry_key：`{entry.get('entry_key')}`（同一 trait_key 的历史条目不会被覆盖，见 §4.6）")


# ------------------------------------------------------------------ 左侧栏

if "chat_text" not in st.session_state:
    st.session_state["chat_text"] = DEMO_TEXT

with st.sidebar:
    st.header("文本导入")
    st.caption("格式：`A: 正文` / `B: 正文`（大写 A/B + 英文冒号 + **恰好一个空格**）")
    conversation_id = st.text_input("会话 ID（conversation_id）", value=DEFAULT_CONVERSATION_ID)
    btn_fill, btn_clear = st.columns(2)
    if btn_fill.button("填入示例文本"):
        st.session_state["chat_text"] = DEMO_TEXT
        st.rerun()
    if btn_clear.button("清空"):
        st.session_state["chat_text"] = ""
        st.rerun()

    chat_text = st.text_area(
        "聊天文本", height=340, key="chat_text", label_visibility="collapsed"
    )
    show_superseded = st.checkbox("（③）显示已被修订的历史条目", value=False)
    st.divider()
    st.caption(f"解析：`{PARSER_SOURCE}`")
    st.caption(f"卡片切分：`{PIPELINE_SOURCE}`，quote 截断上限 {QUOTE_MAX_CHARS} 字符")
    with st.expander("隐私与边界（PRIVACY.md 摘要）"):
        st.markdown(
            "- 只处理你主动粘贴的文本；数据默认只存本机 SQLite。\n"
            "- 调用模型前对手机号 / 邮箱 / 身份证号 / 银行卡号做正则脱敏（策略 α）。\n"
            "- 日志只记 `message_id` 与条数，不记聊天原文。\n"
            "- 可一键删除会话数据（T-007）。"
        )

    st.divider()
    with st.expander("⚙️ 设置 · 危险操作（清空全部本地数据）"):
        st.caption(f"后端 API：`{API_BASE}`")
        st.caption(
            "**清空全部本地数据**会删除本机所有会话在 conversations / persons / messages / analyses / "
            "evidence / profile_versions / consents 的全部行，随后 `VACUUM` 并清理 WAL 临时文件。"
            "按 `PRIVACY.md` §2.2，该危险操作只放在设置页，**必须二次确认**。"
        )
        for line in DELETION_DISCLOSURES:
            st.caption(f"- {line}")
        delete_all_ack = st.checkbox("我理解不可恢复：清空本机全部数据", key="delete_all_ack")
        if st.button("清空全部本地数据", key="btn_delete_all", disabled=not delete_all_ack):
            perform_deletion("all_data", "/data", label="清空全部本地数据")
        render_deletion_receipt("all_data")

# ------------------------------------------------------------------ 顶部：覆盖数 / 版本号 / 同意勾选

#: ③ ④ 的数据来源（T-008）：优先真实后端画像，读不到才回退 T-006 的离线 fixture。
snapshot, profile_source, profile_result = resolve_snapshot(conversation_id)
show_all = bool(show_superseded)
sections = snapshot_to_sections(snapshot, include_superseded=show_all)
all_traits = [t for t in (snapshot.get("traits") or []) if isinstance(t, Mapping)]
visible_traits = (
    all_traits
    if show_all
    else [t for t in all_traits if t.get("status") != "superseded"]
)

st.title("关系洞察 · 行为倾向归纳（原型）")
st.caption(
    "本页只呈现**可观察到的行为倾向**与对应原文证据；不做心理诊断、不给人格标签、不推测对方想法、"
    "不提供操控建议。"
)
render_flash()

top1, top2, top3 = st.columns([1, 1, 2])
top1.metric("当前覆盖消息数", f"{int(snapshot.get('message_count') or 0)} 条")
top2.metric("最新画像版本号", f"v{snapshot.get('version', '?')}")
top3.metric("画像生成时间", str(snapshot.get("generated_at") or "—"))

if profile_source == PROFILE_SOURCE_API:
    st.success(
        f"画像来源：{profile_source} · 会话 `{conversation_id}` · **v{snapshot.get('version')}** · "
        f"快照 `{snapshot.get('schema_version')}`（只读；历史版本行不会被改写，见 §4.6）"
    )
else:
    st.info(
        f"画像来源：{profile_source} · 未读到真实画像（{describe_failure(profile_result)}）。"
        "③ ④ 当前是**离线演示数据**；启动后端并走完「导入 → 同意 → 分析」后会自动切换为真实画像。"
    )

if st.button("刷新画像", key="btn_refresh_profile", help="重新调用 GET /conversations/{id}/profile"):
    st.session_state.pop(profile_cache_key(conversation_id), None)
    st.rerun()

st.caption(
    "⚠️ 「覆盖消息数」= **已经进入画像**的消息条数，不等于你导入的全部消息："
    "不足 50 条的余数批在首次分析时即固定切片，之后追加的消息不会自动并入，也不会触发重算"
    "（`ARCHITECTURE.md` §6）。所以继续粘贴新消息时，这个数字会先**停住**，直到出现新的整批。"
)
st.caption(
    f"数据来源：① ② 用左侧文本在内存里实时解析（会话 `{conversation_id}`，不写库）；"
    f"③ ④ 来源 = {profile_source}（快照会话 `{snapshot.get('conversation_id')}`，v{snapshot.get('version')}）。"
)

st.markdown("#### ① 同意（PRIVACY.md §1.3）")
consent_left, consent_right = st.columns([3, 2])
with consent_left:
    consent_granted = st.checkbox(
        "我已阅读并同意以下同意书（勾选后才可提交同意 / 开始分析）",
        key="consent_granted",
    )
    with st.container(border=True):
        st.markdown(f"> {CONSENT_STATEMENT}")
    st.caption(
        f"同意书版本 `{CONSENT_STATEMENT_VERSION}` · 唯一来源：`{PRIVACY_SOURCE}`（`{CONSENT_STATEMENT_SOURCE}`）。"
        "落库只写四项：时间 / 会话 ID / 同意范围（枚举）/ 文案版本号——不写聊天原文、姓名、证件号（PRIVACY §1.2）。"
    )
with consent_right:
    consent_scope = st.radio(
        "同意范围（PRIVACY.md §1.2 枚举）",
        options=[SCOPE_BOTH_PARTIES, SCOPE_SELF_ONLY],
        format_func=lambda value: SCOPE_LABELS.get(value, value),
        key="consent_scope",
    )
    if st.button(
        "提交同意并写入 consents",
        key="btn_submit_consent",
        disabled=not consent_granted,
        help="未勾选同意时按钮禁用（PRIVACY.md §1.1）",
    ):
        consent_result = api_request(
            "POST",
            f"/conversations/{urlquote(conversation_id, safe='')}/consent",
            payload={
                "granted": True,
                "scope": consent_scope,
                "statement_version": CONSENT_STATEMENT_VERSION,
            },
        )
        if consent_result.ok and isinstance(consent_result.payload, Mapping):
            st.session_state["consent_record"] = consent_result.payload
            st.success(
                f"已写入 `consents`：{consent_result.payload.get('created_at')} · "
                f"scope={consent_result.payload.get('scope')}"
            )
        else:
            st.warning(
                f"未写入 `consents`（{describe_failure(consent_result)}）。"
                "后端未启动时本页只能做离线演示，勾选状态不会落库。"
            )
    consent_record = st.session_state.get("consent_record")
    if isinstance(consent_record, Mapping):
        st.caption(
            f"最近一次同意：`{consent_record.get('consent_id')}` · {consent_record.get('created_at')} · "
            f"scope={consent_record.get('scope')} · 文案版本 {consent_record.get('statement_version')}"
        )
    if not consent_granted:
        st.warning("未勾选同意：**已禁用分析入口**（PRIVACY.md §1.1「未同意禁止调用分析管道」）。")

st.markdown("#### ② 分析（先过同意闸门）")
analyze_left, analyze_right = st.columns([2, 3])
with analyze_left:
    if st.button(
        "开始分析（先验同意闸门）",
        key="btn_analyze",
        disabled=not consent_granted,
        help="无有效同意时按钮禁用；后端也会返回 403 no_consent",
    ):
        analyze_result = api_request(
            "POST",
            f"/conversations/{urlquote(conversation_id, safe='')}/analyze",
            payload={"merge_profile": True},
        )
        if analyze_result.ok and isinstance(analyze_result.payload, Mapping):
            st.session_state["analyze_result"] = analyze_result.payload
            set_flash("success", str(analyze_result.payload.get("message") or "分析完成"))
        else:
            st.session_state.pop("analyze_result", None)
            set_flash("error", f"分析未执行：{describe_failure(analyze_result)}")
        # 分析会写 analyses / evidence，并在 merge_profile 时追加新版本：丢掉画像缓存后重跑，
        # 让 ③ ④ 立刻读到新版真实画像。
        invalidate_profile_cache(conversation_id)
        st.rerun()
with analyze_right:
    st.caption(
        "闸门在后端：`POST /conversations/{id}/analyze` 先查 `consents`（有效同意 = `granted=1` 且 `revoked_at IS NULL`），"
        "无有效同意返回 `403 no_consent`，**不触碰分批管道与模型客户端**；按钮禁用只是 UI 层阻止。"
    )
    analyzed = st.session_state.get("analyze_result")
    if isinstance(analyzed, Mapping):
        st.caption(
            f"最近一次分析：status=`{analyzed.get('status')}` · 批次 {analyzed.get('batch_count')} · "
            f"analyses {analyzed.get('analyses_written')} 行 · evidence {analyzed.get('evidence_written')} 行 · "
            f"版本 v{(analyzed.get('profile') or {}).get('version', '—')}"
        )

st.markdown("#### ③ 删除本会话（不可恢复）")
with st.expander(f"删除会话 `{conversation_id}` 的本地数据", expanded=False):
    st.caption(
        "删除范围：该会话在 conversations / persons / messages / analyses / evidence / profile_versions / consents "
        "的全部行（含 `evidence.quote` 等原文副本）；随后 `VACUUM` 并清理 `-wal` / `-shm` / `-journal`；"
        "回执与日志只记时间 / 范围 / 行数，**不记原文**。"
    )
    for line in DELETION_DISCLOSURES:
        st.caption(f"- {line}")
    delete_conversation_ack = st.checkbox(
        "我理解不可恢复（这是二次确认，PRIVACY.md §2.2）", key="delete_conversation_ack"
    )
    if st.button(
        "删除本会话",
        key="btn_delete_conversation",
        disabled=not delete_conversation_ack,
    ):
        perform_deletion(
            "conversation",
            f"/conversations/{urlquote(conversation_id, safe='')}",
            label=f"会话 {conversation_id}",
        )
    render_deletion_receipt("conversation")

# ------------------------------------------------------------------ 解析（内存，不写库）

result = parse_chat(chat_text, conversation_id)
seq_by_message_id = {message.message_id: message.seq for message in result.messages}
message_rows: list[dict[str, Any]] = []
for message in result.messages:
    role = role_from_person_id(conversation_id, message.person_id)
    message_rows.append(
        {
            "seq": message.seq,
            "源行号": message.source_line,
            "说话人": role,
            "message_id": message.message_id,
            "person_id": message.person_id,
            "正文": message.body,
        }
    )

tab1, tab2, tab3, tab4 = st.tabs(["① 导入预览", "② A/B 标记", "③ 画像卡片", "④ 证据列表"])
# ------------------------------------------------------------------ ① 导入预览

with tab1:
    c1, c2, c3 = st.columns(3)
    c1.metric("可解析消息", f"{len(result.messages)} 条")
    c2.metric("错误行", f"{len(result.errors)} 行")
    c3.metric("空行跳过", f"{result.blank_lines_skipped} 行")
    st.caption("`seq` 只对**可解析成功**的行从 0 递增（§6）；空行跳过且不计入错误行。")
    if message_rows:
        st.dataframe(message_rows, hide_index=True)
    else:
        st.info("左侧还没有可解析的消息。格式：`A: 正文` / `B: 正文`。")
    st.subheader("错误行列表")
    if result.errors:
        st.dataframe(
            [
                {"行号": error.line_number, "原始行": error.raw_line, "原因": error.reason}
                for error in result.errors
            ],
            hide_index=True,
        )
        st.caption("按 T-002 策略：**可解析的行照常导入 + 列出错误行**（只有 `message_id` 冲突才拒绝整批，见 §6）。")
    else:
        st.success("没有错误行：全部可解析。")

    st.divider()
    st.markdown("#### 写入数据库（T-008 接线）")
    st.caption(
        "`POST /conversations/{id}/messages:import`：把左侧文本按 T-002 规则解析后写入本机 `messages` 表"
        "（需要时同时补 `conversations` / `persons` 行）。重复导入时 `message_id` 冲突 → **拒绝整批**（§6 方案 A），"
        "整批一行都不写。**调用模型前的脱敏发生在分析阶段**，同意闸门只管分析入口（PRIVACY.md §1.1）。"
    )
    if st.button(
        "导入到数据库",
        key="btn_import",
        disabled=not message_rows,
        help="先把文本写进本机 SQLite；之后勾选同意才能开始分析",
    ):
        import_result = api_request(
            "POST",
            f"/conversations/{urlquote(conversation_id, safe='')}/messages:import",
            payload={"text": chat_text},
        )
        st.session_state["import_result"] = {
            "ok": import_result.ok,
            "status": import_result.status,
            "payload": import_result.payload if isinstance(import_result.payload, Mapping) else None,
            "failure": None if import_result.ok else describe_failure(import_result),
        }
        if import_result.ok and isinstance(import_result.payload, Mapping):
            set_flash("success", str(import_result.payload.get("message") or "已写入 messages"))
        else:
            set_flash("error", f"导入未执行：{describe_failure(import_result)}")
        invalidate_profile_cache(conversation_id)
        st.rerun()

    import_outcome = st.session_state.get("import_result")
    if isinstance(import_outcome, Mapping):
        with st.container(border=True):
            outcome_payload = import_outcome.get("payload")
            if import_outcome.get("ok") and isinstance(outcome_payload, Mapping):
                st.markdown(
                    f"**最近一次导入** · status `{outcome_payload.get('status')}` · 写入 "
                    f"{outcome_payload.get('inserted_count')} 条 · seq {outcome_payload.get('seq_from')}–"
                    f"{outcome_payload.get('seq_to')} · 错误行 {len(outcome_payload.get('errors') or [])} 行 · "
                    f"空行跳过 {outcome_payload.get('blank_lines_skipped')} 行"
                )
                error_rows = outcome_payload.get("errors") or []
                if error_rows:
                    st.dataframe(error_rows, hide_index=True)
            else:
                st.markdown(f"**最近一次导入** · 失败：{import_outcome.get('failure')}")
                conflicts = outcome_payload.get("conflicts") if isinstance(outcome_payload, Mapping) else None
                if conflicts:
                    st.warning("冲突的 `message_id`（按 §6 方案 A，整批未写入）：")
                    st.dataframe(conflicts, hide_index=True)

# ------------------------------------------------------------------ ② A/B 标记

with tab2:
    st.caption(
        "逐个确认说话人（另一种写法：把整段文本当作 A 或 B 发出）。这里的改动只影响**本页展示**：`person_id` 与证据行的 "
        "`speaker_role` 会跟着变；写库接口 `PATCH /messages/{id}/speaker` 本轮 T-008 **未接线**，本页不改数据库。"
    )
    if not result.messages:
        st.session_state["speaker_overrides"] = {}
        st.info("左侧还没有可解析的消息。")
    else:
        original_roles = {row["seq"]: row["说话人"] for row in message_rows}
        overrides: dict[int, str] = {}
        with st.container(height=460, border=True):
            for row in message_rows:
                seq = int(row["seq"])
                col_left, col_mid, col_right = st.columns([2, 6, 1])
                col_left.caption(f"seq {seq} · 行 {row['源行号']}")
                col_left.caption(f"`{row['message_id']}`")
                col_mid.markdown(row["正文"])
                picked = col_right.selectbox(
                    "说话人",
                    options=["A", "B"],
                    index=0 if row["说话人"] == "A" else 1,
                    key=f"speaker_{row['message_id']}",
                    label_visibility="collapsed",
                )
                if picked != original_roles.get(seq):
                    overrides[seq] = str(picked)
        st.session_state["speaker_overrides"] = overrides
        if overrides:
            st.warning(
                f"已修改 {len(overrides)} 条消息的说话人："
                + "、".join(f"seq {seq} → {role}" for seq, role in sorted(overrides.items()))
            )
            st.caption("③④ 的证据若命中这些 `message_id`，`speaker_role` 会同步显示为改后的说话人。")
        else:
            st.success("当前说话人与解析结果一致。")

# ------------------------------------------------------------------ ③ 画像卡片

with tab3:
    st.caption(
        "按 `snapshot_to_sections()` 分 A / B / dyad 三栏（归属取自 `trait_key` 前缀）；"
        "每张卡片显示 statement、confidence、sample_size。"
    )
    col_a, col_b, col_c = st.columns(3)
    for column, owner, title in (
        (col_a, "A", "A 的行为倾向"),
        (col_b, "B", "B 的行为倾向"),
        (col_c, "dyad", "双方互动（dyad）"),
    ):
        with column:
            st.subheader(title)
            items = sections.get(owner) or []
            if not items:
                st.caption("暂无结论。")
            for entry in items:
                render_trait_card(entry)

    for entry in sections.get("other") or []:
        render_trait_card(entry)

    counts = snapshot.get("counts") or {}
    st.divider()
    change_bits = [
        f"{CHANGE_LABELS.get(key, key)} {counts[key]}"
        for key in ("added", "supported", "weakened", "revised")
        if key in counts
    ]
    st.caption(
        "本版变更计数：" + " · ".join(change_bits)
        + f" · 有效条目 {counts.get('active_traits', '—')}"
        + f" · 历史条目 {counts.get('superseded_traits', '—')}"
    )
    for warning in snapshot.get("warnings") or []:
        st.warning(str(warning))

# ------------------------------------------------------------------ ④ 证据列表

with tab4:
    current_overrides = dict(st.session_state.get("speaker_overrides") or {})
    st.caption(
        "每条结论可展开：`message_id` + **脱敏后** quote + speaker_role（§4.5）。"
        f"quote 为策略 α 脱敏后的前缀（最多 {QUOTE_MAX_CHARS} 字符）；要看完整原文，请用 `message_id` 回查 `messages.body`。"
    )
    if not visible_traits:
        st.info("没有可展示的结论。")
    for entry in visible_traits:
        with st.expander(
            f"{entry.get('trait_key')} — {entry.get('statement')}", expanded=False
        ):
            st.caption(
                f"entry_key：`{entry.get('entry_key')}` · 状态：{entry.get('status')} · "
                f"变更类型：{change_label(entry)} · "
                f"confidence {float(entry.get('confidence') or 0.0):.2f} · "
                f"sample_size {int(entry.get('sample_size') or 0)}"
            )
            evidence_rows: list[dict[str, Any]] = []
            for item in entry.get("evidence") or []:
                if not isinstance(item, Mapping):
                    continue
                message_id = str(item.get("message_id") or "")
                seq = seq_by_message_id.get(message_id)
                role = item.get("speaker_role")
                effective = current_overrides.get(seq, role) if seq is not None else role
                note = "" if str(effective) == str(role) else f"（② 标记：由 {role} 改为 {effective}）"
                evidence_rows.append(
                    {
                        "message_id": message_id,
                        "seq": str(seq) if seq is not None else "—（不在当前示例文本中）",
                        "quote（脱敏后）": item.get("quote") or "",
                        "speaker_role": f"{effective or '—'}{note}",
                    }
                )
            if evidence_rows:
                st.dataframe(evidence_rows, hide_index=True)
            else:
                st.warning("该结论没有可用证据（T-004 规定：无证据的结论不入库）。")

# ------------------------------------------------------------------ 免责声明

st.divider()
st.caption(
    "**免责声明：**本原型只归纳**可观察到的行为倾向**并给出原文证据，**不是心理诊断、不是人格标签、"
    "不推测对方动机或想法（不读心）、不提供操控或 PUA 建议**；结论可能出错，请以原文为准。"
)
st.caption(
    "数据默认只存本机；调用模型前按策略 α 对手机号 / 邮箱 / 身份证号 / 银行卡号脱敏；"
    "「删除本会话」与设置页「清空全部本地数据」均需二次确认，删除后 `VACUUM` 并做残留检查（T-007）。"
    "T-008 已完成前后端接线（导入 / 同意 / 分析 / 画像 / 删除）；端到端自测用 `FakeDeepSeekClient`，"
    "**未调用真实 DeepSeek API**，最终验收由 WorkBuddy 按 `ACCEPTANCE.md` 执行。"
)
with st.expander("删除**删不掉**的部分（PRIVACY.md §2.3，必须披露）"):
    for line in DELETION_DISCLOSURES:
        st.markdown(f"- {line}")
    st.caption(
        "删除成功后本应用给出无原文回执（时间 + 范围 + 各表行数 + 残留检查结论），并追加一条同样无原文的审计记录。"
    )
