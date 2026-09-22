# TASKS.md — 任务看板

**项目：** 关系洞察系统 MVP  
**规格：** 已冻结 v0.1（2026-09-21 人工确认）  
**看板规则：** 同一时刻优先推进无阻塞的就绪任务；状态仅使用：`未开始` / `进行中` / `阻塞` / `完成` / `取消`。  
**状态更新：** 任务完成后在 `HANDOFF.md` 追加一条记录，并将本表「当前状态」改为 `完成`。

**v0.1 已确认：** Python 3.12.4；同步 FastAPI + sqlite3；文本仅 `A: 正文` / `B: 正文`；模型 `deepseek-chat`（OpenAI 兼容）；脱敏策略 α；同意为 UI 勾选写入 `consents`。

**负责工具约定：**

- **Cursor：** 规格、架构、接口契约、验收标准、集成把关  
- **Codex：** 编码实现与单元/集成测试  
- **WorkBuddy：** 环境、运行、手工验收辅助、日志与交接提醒  

---

## 总表

| 任务ID | 任务描述 | 负责工具 | 输入 | 输出 | 依赖 | 验收标准 | 当前状态 |
|--------|----------|----------|------|------|------|----------|----------|
| T-001 | 搭建 FastAPI + SQLite 项目骨架 | Codex（实现）· Cursor（目录与接口约定）· WorkBuddy（环境验证） | 本看板；`ARCHITECTURE.md` 表结构 | 可启动的 FastAPI 应用、SQLite 文件、健康检查接口、依赖清单 | 无 | 见下方 T-001 | 完成 |
| T-002 | 文本解析器：解析 A/B 说话人，生成 `message_id` | Codex · Cursor（格式规格） | 样例聊天文本；说话人规则 | `parser` 模块；`Message` 列表；解析错误报告 | T-001 | 见下方 T-002 | 完成 |
| T-003 | DeepSeek API 客户端封装 | Codex · Cursor（请求/响应 JSON Schema） | API 基址、模型名、Key 环境变量 | `DeepSeekClient`；超时/重试/错误类型；假客户端用于测试 | T-001 | 见下方 T-003 | 完成 |
| T-004 | 分批分析管道（每 50 条一批，输出 JSON 画像） | Codex · Cursor（prompt 与 schema） | 已入库消息；T-003 客户端 | 批次 `analyses` + `evidence` 行 | T-002, T-003 | 见下方 T-004 | 完成 |
| T-005 | 长期画像增量更新（新证据不覆盖旧结论，保留版本） | Codex · Cursor（合并规则） | 历史 `profile_versions` + 新批次分析 | 新版本画像；旧版本只读保留 | T-004 | 见下方 T-005 | 完成 |
| T-006 | Streamlit 前端原型（模拟数据：导入、A/B 标记、画像卡片、证据列表） | Codex · Cursor（信息架构）· WorkBuddy（界面点验） | 模拟 JSON；UI 线框文字 | `app.py`（或 `frontend/`）可演示四块界面 | 无（可与后端并行） | 见下方 T-006 | 完成 |
| T-007 | 一键删除与同意记录功能 | Codex · Cursor（隐私条款落地） | `PRIVACY.md`；会话/人物 ID | 同意写入；删除 API + UI；残留检查脚本 | T-001, T-006 | 见下方 T-007 | 完成 |
| T-008 | 集成与验收 | Cursor（主导）· Codex（修缺陷）· WorkBuddy（按清单执行） | `ACCEPTANCE.md`；已实现 T-001–T-007 | 验收记录；已知问题列表；是否达标结论 | T-001–T-007 | 见下方 T-008 | 未开始 |

---

## T-001 搭建 FastAPI + SQLite 项目骨架

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** 写代码；**Cursor** 确认目录与表字段命名；**WorkBuddy** 在本机安装依赖并启动 |
| 输入 | 已冻结的 `ARCHITECTURE.md`；Python **3.12.4** |
| 输出 | `backend/`：同步 FastAPI 入口、标准库 `sqlite3`、`init_db`、`GET /health`；根目录 `requirements.txt`；`backend/.env.example` |
| 依赖 | 无 |
| 验收标准 | ① `GET /health` 返回 200；② 启动后自动生成 SQLite，核心表 persons / messages / analyses / evidence / profile_versions 存在，并含已确认的 `consents`；③ 仓库无真实 API Key；④ HANDOFF 中有启动命令 |
| 当前状态 | 完成 |

**已确认（v0.1）：** Python 3.12.4；**同步 FastAPI**；标准库 **sqlite3**（不用 async / aiosqlite）。建表范围：五张核心表 + `consents`。

---

## T-002 文本解析器

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** 实现；**Cursor** 冻结输入格式与 `message_id` 算法 |
| 输入 | 纯文本；格式规格（v0.1 已冻结） |
| 输出 | `parse_chat(text) -> list[MessageDTO]`；无法解析行的列表；将结果写入 `messages` 的服务函数 |
| 依赖 | T-001 |
| 验收标准 | ① 每条成功消息有全局唯一 `message_id`，用已冻结算法 `uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`（`seq` 从 0 起）；② 说话人仅为 `A` 或 `B`（或绑定 `person_id`）；③ `body` 为原文完整保留；④ 空行可跳过并计数；非 `A:`/`B:` 行记入错误列表；⑤ 至少 2 个夹具样例测试通过 |
| 当前状态 | 完成 |

**已确认（v0.1）：** 第一版**只**支持行格式 `A: 正文` 与 `B: 正文`。不支持时间前缀、微信/QQ 导出。A/B 大小写 **假设** 仅接受大写 A/B（实现时写进测试）。

**已确认（2026-09-22 冻结）`message_id` 算法：** `message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`，`seq` 从 **0** 开始、按导入顺序递增；同一 `(conversation_id, seq)` 必得同一 ID。**重复导入策略：拒绝整批**——写库前先做全批存在性检查，只要有一个 `message_id` 已存在，整批不写入，并在错误报告中列出冲突 ID 与来源行号（不做部分导入、不静默跳过）。完整约定见 `ARCHITECTURE.md` §6。

**已确认（2026-09-22 拍板）：** ① `person_id` = `uuid5(NAMESPACE_URL, f"person:{conversation_id}:{role}")`，已冻结并写入 `ARCHITECTURE.md` §4.1；② 文本中含解析错误行时，**仍导入可解析成功的行**并在报告中列出错误（含行号与原因）。该策略与「`message_id` 冲突则拒绝整批」是**两条不同规则**，见 `ARCHITECTURE.md` §6。

**假设（未冻结）：** ③ `A: ` 冒号后正文为空视为解析错误。

---

## T-003 DeepSeek API 客户端封装

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** 实现；**Cursor** 提供 JSON Schema 与禁止事项写入系统提示 |
| 输入 | `DEEPSEEK_API_KEY`；`base_url`（**假设** `https://api.deepseek.com`）；模型名 **`deepseek-chat`**；OpenAI 兼容接口 |
| 输出 | `DeepSeekClient.analyze_batch(messages, schema) -> dict`；`FakeDeepSeekClient`；统一错误（401/429/5xx/超时） |
| 依赖 | T-001 |
| 验收标准 | ① Key 只从环境变量读取；② 使用 OpenAI 兼容 Chat Completions，`model=deepseek-chat`；JSON 约束方式用 `response_format={"type": "json_object"}`（2026-09-22 已确认，见 `ARCHITECTURE.md` §8）；③ 单测不打真实网，Fake 客户端可返回合法 schema；④ 日志不打印完整聊天原文（可打 `message_id` 与条数）；⑤ 发给模型的 content 为策略 α 脱敏后文本 |
| 当前状态 | 完成 |

**已确认（v0.1）：** 模型 `deepseek-chat`；OpenAI 兼容接口。

**已确认（2026-09-22 拍板）：** 请求带 `response_format={"type": "json_object"}`（服务端不支持时归为 `bad_response`，不做自动降级）；重试最多 **3** 次尝试、**1.5s 指数退避**，仅对 429 / 5xx / 超时 / 连接失败重试（401 立即失败）；单次超时 **60s**；脱敏**不扩展**，MVP 仅手机号 / 邮箱 / 身份证号 / 银行卡号 4 类。详见 `ARCHITECTURE.md` §8。

---

## T-004 分批分析管道

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** 管道；**Cursor** 定稿 prompt：只输出行为倾向 + 证据引用，禁止诊断与操控建议 |
| 输入 | 按时间/导入序排列的消息；批次大小 = 50；T-003 |
| 输出 | 每批一条 `analyses` 记录（JSON 画像片段）+ 多条 `evidence`（含 `message_id`、**脱敏后** `quote`、对应结论键） |
| 依赖 | T-002, T-003 |
| 验收标准 | ① 100 条消息产生 2 个完整批 + 处理余数规则明确；② 每条结论含证据 `message_id` 列表；写库时 ID 必须存在，`quote` 须等于该条原文经同一正则脱敏后的摘录（策略 α）；③ 缺少证据的结论不入库或标 `unverified`；④ 消息总数 &lt; 20 时管道拒绝正式分析并返回「样本不足」；⑤ 调用模型前对 `body` 脱敏，**不得**把未脱敏原文发到 API |
| 当前状态 | 完成 |

**已确认（2026-09-22 拍板）：** 余数 &lt; 50 的最后一批**仍调用一次模型**，该批条数作为 `sample_size` 写入该批 `result_json.warnings`（不丢弃、不并入上一批）。  
**已确认（2026-09-22）：** 总数 &lt; 20 条**拒绝正式分析**，返回「样本不足」，**不调用模型、不写库**（不做「预览草稿」）。恰好 20 条放行（边界为 `>=`）。  
**实现记录：** `backend/pipeline/`（`batch.py` / `prompt.py` / `run.py`）；`analysis_id = uuid5(NAMESPACE_URL, f"analysis:{conversation_id}:{batch_index}")` 确定性生成，已存在的批次跳过不重算（幂等）；某批抛 `DeepSeekError` 时停止后续批次并保留已写入的批次。

**实现记录（2026-09-22 拍板补充）：** 幂等键 = `(conversation_id, batch_index)`；会话**追加**消息后**不重算**既有批次，只分析新增尾批（余数批「原地长大」也不重算）——完整约定见 `ARCHITECTURE.md` §6。

**遗留问题（2026-09-22 拍板：暂不处理）：** ③ `analyses` 表**不加**独立 `sample_size` 列（样本量仍在 `result_json.warnings`，可由 `seq_from` / `seq_to` 推导），v1.1 再考虑；④ **不加**失败批次续跑入口，MVP 保持「失败即停」，已写入的批次保留。

---

## T-005 长期画像增量更新逻辑

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** 合并算法；**Cursor** 定义结论主键（如 `trait_key`）与冲突策略 |
| 输入 | 当前最新 `profile_versions` + 新批次 `analyses`/`evidence` |
| 输出 | `profile_versions.version = 旧版 + 1` 的完整快照；变更摘要（added / supported / weakened / revised）；旧行不删 |
| 依赖 | T-004 |
| 验收标准 | ① 新增一批（或追加 20 条且分析完成）后版本号 +1；② 旧版本 JSON 仍可读取；③ 同一 `trait_key` 的历史表述仍在旧版中；新版可含 `supersedes_version` 或结论级 `revision_of`；④ 不得 `UPDATE` 覆盖旧版快照行 |
| 当前状态 | 完成 |

**实现记录（2026-09-22）：** 新增 `backend/pipeline/merge.py`（`merge_profile` 纯函数 + `persist_profile_version` / `update_profile` 落库）、`backend/pipeline/traits.py`（`trait_key` 规范化、四类变更分类、加权平均 confidence）、`tests/test_merge.py`（23 例离线单测）；`backend/pipeline/__init__.py` 增补出口。

**合并约定（2026-09-22）：** ① 幂等键 = 已覆盖批次集合（`covered_analyses` / `covered_batch_indexes`，由 `batch_index` 推导）——已合并过的批次不重复折叠，同一会话追加消息后只折叠新增尾批；无新批次时 `status=nothing_to_do` 且**不写库**。② 版本号 = 旧版 + 1；**只 INSERT** 新 `profile_versions` 行，旧行与其 `snapshot_json` 一律不改写（符合 §4.6「禁止 UPDATE」）。③ 同一 `trait_key` 再次出现：`confidence` 取加权平均、`sample_size` 累加、`evidence_message_ids` 合并去重。④ 新证据与旧结论矛盾（`revised`）时**不删旧结论**，新版另加条目并以 `revision_of` 指向旧版，旧条目标 `superseded_by` / `superseded_at_version`；`snapshot_json` 顶层含 `supersedes_version`。

**备注：** `trait_key` 直接采用 `claim_key`（如 `A.request_style`），跨批次稳定；`changelog_json` 按 added / supported / weakened / revised 分类留痕。

**遗留问题（2026-09-22 T-006 轮拍板）：**

- 证据 `quote` 折叠空白并截断到 80 字符（`QUOTE_MAX_CHARS`）——**已确认（2026-09-22）：维持现状**；只取前缀仍满足 `ARCHITECTURE.md` §4.5「脱敏后文本的子串」，要看完整原文请回查 `messages.body`。
- 本模块无并发控制：同一会话并发 `update_profile` 可能撞 `UNIQUE(conversation_id, version)`——**已确认（2026-09-22）：MVP 不加锁，单用户同步调用**，暂不处理。
- 余数批「原地长大」：不足 50 条的尾批首次分析后即固定，追加消息可能长期不进画像——**已确认（2026-09-22）：维持现状**，改由 T-006 UI 顶部常显「当前覆盖消息数 + 最新画像版本号」提示（见 `ARCHITECTURE.md` §6）。

---

## T-006 Streamlit 前端原型（模拟数据）

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** 实现页面；**Cursor** 定信息架构与免责声明文案；**WorkBuddy** 按点击路径点验 |
| 输入 | `fixtures/mock_profile.json` 等模拟数据；`PRIVACY.md` 摘要展示 |
| 输出 | Streamlit 应用：① 文本导入区 ② A/B 标记 ③ 画像卡片 ④ 证据列表（点击结论展开原文） |
| 依赖 | 无（模拟数据可先做）；与后端联调依赖 T-001 后的 API，属 T-008 |
| 验收标准 | ① 不启动 FastAPI 也能用模拟数据演示四块 UI；② 证据行可见 `message_id` 与 quote（脱敏）；③ **同意勾选框**：勾选后（联调时）写入 `consents`；原型阶段可先本地 state；④ 不做诊断式标题（如“自恋型”） |
| 当前状态 | 完成 |

**实现记录（2026-09-22）：** 新增 `frontend/app.py`（Streamlit 四块界面 + 顶部「覆盖消息数 / 最新版本号」 + 同意勾选框）、`frontend/fixtures/mock_profile.json`（符合 `ARCHITECTURE.md` §5 快照结构；**共 7 条条目 = 有效 6 条 + `superseded` 历史 1 条**——有效条目为 A 3 条 / B 1 条 / dyad 2 条，另 1 条为 `A.tone_intensity@v1` 的 `superseded` 历史条目）、`frontend/requirements.txt`（`streamlit>=1.31,<2`）；**未改动 `backend/` 任何文件**。①「导入预览」与 ②「A/B 标记」复用 `backend/parser.py`（不启动 FastAPI、不读写数据库）；③ 画像卡片按 `snapshot_to_sections()` 分 A / B / dyad 三栏（`openai` 等依赖缺失时回退到本地等价分组，保证纯前端环境可离线演示）；④ 证据列表用 `st.expander` 展示 `message_id` / 脱敏 `quote` / `speaker_role`。同意勾选框为本地 session state（联调时写入 `consents`，属 T-007）；页面标题与卡片文案均为「行为倾向」类，**无诊断式命名**。

---

## T-007 一键删除与同意记录

| 字段 | 内容 |
|------|------|
| 负责工具 | **Codex** API + DB 级联删除；**Cursor** 对照 `PRIVACY.md`；**WorkBuddy** 删除前后对比文件大小/行数 |
| 输入 | `consent` 记录需求；删除范围（**已确认 2026-09-22：** 以「按会话删除」（`DELETE /conversations/{id}`）为主，「清空全部本地数据」作为设置页危险操作并需二次确认） |
| 输出 | `POST /conversations/{id}/consent`（勾选写入 `consents`）；删除 API + UI；残留检查脚本 |
| 依赖 | T-001；UI 入口依赖 T-006 |
| 验收标准 | ① 无有效同意不得调用分析管道；② 删除后五张业务表及同意表无该范围行；③ WAL/临时文件不含明文残留（尽力：重建 SQLite 或 `VACUUM`）；④ 操作可审计（记下删除时间，**不**记下原文） |
| 当前状态 | 完成 |

**已确认（v0.1）：** 同意机制为 UI 勾选框，勾选后写入 `consents`。无勾选不得分析。  
**已确认（2026-09-22 T-007 轮拍板）：** 删除范围以「按会话删除」（`DELETE /conversations/{id}`）为主，「清空全部本地数据」作为危险操作放在设置页且需二次确认；同意文案**严格按 `PRIVACY.md` §1.3 落地、不自行发挥**（唯一来源 `backend/privacy.py` 的 `CONSENT_STATEMENT` / `CONSENT_STATEMENT_VERSION="v0.1-2026-09-21"`，落库只写时间 / 会话 ID / scope 枚举 / 文案版本号）。**实现取舍（仍待人工确认）：** 删除后保留空库结构（只清行）；撤回同意保留 `revoked_at` 行。  

**实现记录（2026-09-22）：** 新增 `backend/privacy.py`（同意文案唯一来源 + 有效同意判定 `granted=1 AND revoked_at IS NULL` + 七表有序删除（`evidence` → `analyses` → `profile_versions` → `messages` → `persons` → `consents` → `conversations`，schema 无 `ON DELETE CASCADE` 故手工按序）+ `VACUUM` + 清理 `-wal`/`-shm`/`-journal` + 字节级残留检查（只报文件名与命中数）+ 只记时间与行数的 JSON 审计 `deletion_audit.jsonl`）；`backend/main.py` 新增 `POST /conversations/{id}/consent`、`DELETE /conversations/{id}`、`DELETE /data`，并把 `POST /conversations/{id}/analyze` 前置同意闸门（无有效同意 → `403 no_consent`，**调用管道前**即拒绝）；`frontend/app.py` 接线同意写入 `consents`、「删除本会话」按钮、设置页「清空全部本地数据」二次确认与删除回执展示；`tests/test_privacy.py` 新增 **28 个离线用例**（`tmp_path` 临时库 + `FakeDeepSeekClient`，零网络）；`ARCHITECTURE.md` §0/§4.7/§7/§9 同步拍板。复跑 `pytest tests -q` → **`121 passed`**。

**遗留问题（2026-09-22）：** ① 撤回同意保留 `revoked_at` 行 vs 删除该行，待人工确认；② 删除后保留空库结构（只清行）待人工确认；③ 同一会话重复授权会新增 `consents` 行（有效同意取最新一行），是否改为一会话一行（UPSERT）待定；④ `DELETE /data` 无口令保护（仅 UI 勾选 + `confirm=true`）；⑤ 残留检查不覆盖文件系统快照 / 备份 / SSD 磨损层；⑥ 审计文件不加密、`DELETE /data` 是否连带清理未定；⑦ `PRIVACY.md` §4.1 未成年人标准、§5 DeepSeek 政策 URL 未定。

---

## T-008 集成与验收

| 字段 | 内容 |
|------|------|
| 负责工具 | **Cursor** 对照 `ACCEPTANCE.md` 出具是否通过；**WorkBuddy** 执行手工项；**Codex** 修复阻塞缺陷 |
| 输入 | 端到端样例文本（≥ 20 条，建议 ≥ 70 条以测批次与增量）；真实或 Fake 模型 |
| 输出 | 填写完成的验收清单；缺陷票；演示路径说明 |
| 依赖 | T-001–T-007 |
| 验收标准 | `ACCEPTANCE.md` 全部「必须」项通过；未通过项有明确豁免签字（**需人工确认**）才可标 MVP 完成 |
| 当前状态 | 未开始 |

---

## 建议排期（非承诺）

```
并行：T-001 ──┬── T-002 ──┐
              ├── T-003 ──┴── T-004 ── T-005
并行：T-006 ─────────────────────────────┤
                    T-007（T-001 后即可部分开始）─┤
                                              T-008
```

WorkBuddy 在 T-001、T-006、T-007、T-008 必须参与运行验证。

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1 | 2026-09-21 | 启动初稿，T-001–T-008 |
| 0.1-frozen | 2026-09-21 | 写入人工确认项；T-001 开始执行 |
| 0.2 | 2026-09-22 | T-001 完成；总表与 T-001 明细的「当前状态」改为完成 |
| 0.3 | 2026-09-22 | Python 基线改 3.12.4；message_id 冻结为方案 A（重复导入拒绝整批）；T-002/T-003 实现与单测完成 |
| 0.4 | 2026-09-22 | 总表与 T-002/T-003 明细「当前状态」改为完成（交接记录见 HANDOFF.md） |
| 0.5 | 2026-09-22 | T-004 完成（总表与明细状态改「完成」）；拍板落地：person_id 冻结、conversations 建表、解析错误行与重复导入策略区分、response_format / 重试 / 超时确认、脱敏范围不扩展 |
| 0.6 | 2026-09-22 | T-005 完成（总表与明细状态改「完成」）；T-004 补「幂等键 = batch_index / 追加消息不重算既有批次」实现记录与遗留问题（不加 sample_size 列、不加续跑入口）；拍板落地：speaker_role 对 `dyad.*` 写真实说话人、证据不合法保持「丢弃 + 记录」 |
| 0.7 | 2026-09-22 | T-006 完成（总表与明细状态改「完成」并补实现记录）；T-005 遗留问题标「已确认」：`quote` 截断 80 字符维持现状、`profile_versions` 并发不加锁；拍板落地：余数批「原地长大」维持现状并在 UI 顶部提示（见 `ARCHITECTURE.md` §6） |
| 0.8 | 2026-09-22 | T-007 完成（总表与明细「当前状态」改「完成」并补实现记录与遗留问题）；T-007 明细「输入」「假设」中的待确认项据 2026-09-22 拍板改为「已确认」；拍板落地：删除范围以「按会话删除」为主 + 设置页「清空全部本地数据」危险操作与二次确认、同意文案严格按 `PRIVACY.md` §1.3 落地、不自行发挥（见 `ARCHITECTURE.md` §7 / §4.7） |
