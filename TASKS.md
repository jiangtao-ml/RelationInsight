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
| T-008 | 集成与验收 | Cursor（主导）· Codex（修缺陷）· WorkBuddy（按清单执行） | `ACCEPTANCE.md`；已实现 T-001–T-007 | 验收记录；已知问题列表；是否达标结论 | T-001–T-007 | 见下方 T-008 | 完成 |

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
| 验收标准 | ① 每条成功消息有全局唯一 `message_id`，用已冻结算法 `uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`（`seq` 为**会话内全局序号**：首段从 0 起，追加导入按 `seq_offset` 续号，见 §6）；② 说话人仅为 `A` 或 `B`（或绑定 `person_id`）；③ `body` 为原文完整保留；④ 空行可跳过并计数；非 `A:`/`B:` 行记入错误列表；⑤ 至少 2 个夹具样例测试通过 |
| 当前状态 | 完成 |

**已确认（v0.1）：** 第一版**只**支持行格式 `A: 正文` 与 `B: 正文`。不支持时间前缀、微信/QQ 导出。A/B 大小写 **假设** 仅接受大写 A/B（实现时写进测试）。

**已确认（2026-09-22 冻结）`message_id` 算法：** `message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`，`seq` 从 **0** 开始、按导入顺序递增；同一 `(conversation_id, seq)` 必得同一 ID。**重复导入策略：拒绝整批**——写库前先做全批存在性检查，只要有一个 `message_id` 已存在，整批不写入，并在错误报告中列出冲突 ID 与来源行号（不做部分导入、不静默跳过）。完整约定见 `ARCHITECTURE.md` §6。

**已确认（2026-09-23 补冻结，T-008 必须项 5 缺陷修复）`seq` 语义：** `seq` 是**会话内的全局序号**（不是「本段文本内的序号」）——`parse_chat(text, conversation_id, *, seq_offset=0)` 与 `import_chat(text, conversation_id, *, seq_offset=0, ...)` 接受 `seq_offset` 作为起点；导入端写库前取该会话 `SELECT COALESCE(MAX(seq), -1) + 1` 作为 `seq_offset`，从而实现**追加导入自动续号**。`message_id` 算法与「重复导入拒绝整批」语义**均不变**，只是把冲突检测放在**偏移之后**；同一段文本原样再导入不再报冲突（内容级去重留 v1.1）。完整约定见 `ARCHITECTURE.md` §6。

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

**遗留问题（2026-09-22，T-008 轮拍板）：** ① 撤回同意保留 `revoked_at` 行（不删除该行）→ **已确认（2026-09-22），维持现状**；② 删除后保留空库结构（只清行，不回删 `schema.sql` 定义）→ **已确认（2026-09-22），维持现状**；③ 同一会话重复授权会新增 `consents` 行（有效同意取最新一行），是否改为一会话一行（UPSERT）待定；④ 未成年人 18 岁判定标准（`PRIVACY.md` §4.1）、⑤ `PRIVACY.md` §5 DeepSeek 政策正式 URL、⑥ `DELETE /data` 是否加口令保护（`PRIVACY.md` §6）→ **三项均移入 v1.1 遗留，MVP 不做**；⑦ 残留检查不覆盖文件系统快照 / 备份 / SSD 磨损层；⑧ 审计文件不加密、`DELETE /data` 是否连带清理未定。

---

## T-008 集成与验收

| 字段 | 内容 |
|------|------|
| 负责工具 | **Cursor** 对照 `ACCEPTANCE.md` 出具是否通过；**WorkBuddy** 执行手工项；**Codex** 修复阻塞缺陷 |
| 输入 | 端到端样例文本（≥ 20 条，建议 ≥ 70 条以测批次与增量）；真实或 Fake 模型 |
| 输出 | 填写完成的验收清单；缺陷票；演示路径说明 |
| 依赖 | T-001–T-007 |
| 验收标准 | `ACCEPTANCE.md` 全部「必须」项通过；未通过项有明确豁免签字（**需人工确认**）才可标 MVP 完成 |
| 当前状态 | 完成 |

**实现记录（2026-09-22，集成部分）：** `backend/main.py` 新增 **`POST /conversations/{id}/messages:import`**（纯文本 → T-002 `import_chat` → 写 `messages`；需要时用 `INSERT OR IGNORE` 补 `conversations` 主行；重复导入按 §6 已冻结的**方案 A 拒绝整批** → `409 duplicate_message_id` + `detail.conflicts` 列出冲突 `message_id` 与来源行号；响应体**不含原文**，解析错误只回「行号 + 原因」）与 **`GET /conversations/{id}/profile`**（读 T-005 快照：默认最新版、`?version=N` 读历史版、**只读**；无画像 → `404 no_profile`，前端据此回退离线 fixture）；`FastAPI(version="0.8.0")` 加 **CORS**，只放行本机 Streamlit 原型 `http://localhost:8501` / `http://127.0.0.1:8501`（`ARCHITECTURE.md` §8：服务仍只绑 `127.0.0.1`）。`frontend/app.py`：画像卡片由 `mock_profile.json` 改为**优先**调 `GET /conversations/{id}/profile`（离线/失败才回退 fixture 并显示失败原因），新增「导入到数据库」按钮（调 `messages:import`，展示写入条数 / seq 区间 / 错误行表 / 冲突表）与「刷新画像」按钮，并在导入 / 分析 / 删除后自动失效画像缓存；同意勾选与「删除本会话」沿用 T-007 接线（本轮确认可用）。**未改动 T-001–T-007 任何已冻结接口契约**；未新增依赖、未新增测试文件；`backend/data/relationinsight.db` 仍 7 张表 0 行。

**端到端自测（2026-09-22，全部离线，真实 HTTP + 真实页面）：** 真实 `uvicorn`（`127.0.0.1:8011`，注入临时库 + `FakeDeepSeekClient`）+ 真实 Streamlit 页面（`streamlit.testing.v1.AppTest`）走通：未同意分析 → `403 no_consent` → 导入 63 条（seq 0–62、错误行 4、空行 3）→ 勾选同意写 `consents` → 分析合并（2 批 / `analyses` 2 / `evidence` 12 / `profile_versions` v1）→ 前端读真实画像（v1、63 条、`A.request_style` 与 `B.request_style` 各 1 条）→ 二次确认删除（七表该会话计数 0、全库 0、`db`/`-wal` 字节级残留 0 命中、审计 1 行且无原文）。另用记录型 Fake 客户端验证**调用模型前脱敏**：63 条中含 PII 的 seq 28/30/44 原文只留本机 `messages.body`，实际发往模型的文本 PII 命中全为 False 且出现 `[手机号]` / `[邮箱]` / `[银行卡号]` 占位符，入库 `evidence.quote` 同样无 PII。复跑 `pytest tests -q` → **`121 passed`**（无回归）。自测脚本为临时文件，跑完即删。

**遗留问题（2026-09-22，T-008 集成部分）：** ① `PATCH /messages/{id}/speaker` **未接线**——② A/B 标记页的「改说话人」目前只影响页面展示，不回写 `messages.person_id`（T-002/T-007 未定义该接口，T-008 不新增契约；若验收要求「改完重算生效」需先补契约）；② 前端暂无画像历史版本选择器（API 侧 `?version=N` 已支持）；③ `RELATIONINSIGHT_API_BASE` 未写入 `.env.example`；④ 换端口起 Streamlit 需改 `main.py` 的 `ALLOWED_ORIGINS`；⑤ 画像缓存在 `st.session_state`，跨端改动后需点「刷新画像」；⑥ 删除审计记 `scope`（会话 ID）以支持追溯（非原文）；⑦ 续号修复后**同一段文本原样再导入不再报 409**，而是续号追加（内容重复但 `seq` 合法）——**内容级去重属 v1.1**，MVP 不做。

**实现记录（2026-09-23，缺陷修复：必须项 5「追加消息后画像版本 +1」）：** WorkBuddy 最终验收 7 个必须项 6 通过 / 1 失败，唯一失败项即必须项 5，根因＝`parser.parse_chat()` 的 `seq` **恒从 0 起** → 追加导入时 `message_id` 必然与既有行冲突 → 触发 §6 方案 A「拒绝整批」→ 产品路径上无法追加。修法（**不改算法、不改方案 A 语义**）：① `backend/parser.py` 的 `parse_chat()` / `import_chat()` 新增 `seq_offset`（默认 0），`seq` 从 `seq_offset` 起递增，并对非 int / 负数早失败；② `backend/main.py::import_messages()` 写库前执行 `SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE conversation_id = ?`，把结果作为 `seq_offset` 传入，**先偏移、后检测冲突**——只有偏移后**仍**冲突才按方案 A 返回 `409`；空会话时 `seq_offset = 0`，首版行为不变。测试：新增 `tests/test_import_append.py`（2 例离线端到端：50+20 续号后画像 v1→v2 且 v1 快照未被改写；显式压回 `seq_offset=0` 时仍拒绝整批）与 `tests/test_parser.py` 2 例（`seq_offset=50` 续号且 ID 与 0–49 不重合、50+20 追加写库共 70 条），并在既有参数校验用例补 `seq_offset` 断言；`pytest tests -q` → **`125 passed`**（集成时 121 + 新增 4，零回归）。真实 HTTP 冒烟（`uvicorn 127.0.0.1:8012` + 临时库 + `FakeDeepSeekClient`，零真实 API）：导入 50（seq 0–49）→ 同意 → 分析 v1（`analyses` 1 / `evidence` 6）→ **追加导入 20 → HTTP 200、seq 50–69、conflicts 0**（旧实现此处 409）→ 再分析 → 画像 **v2**（`batch_count=2` / `analyses_written=1` / `message_count=70`）、`analyses` 2 / `evidence` 12 / `profile_versions` 2，v1 快照 sha256 前后一致；生产库 `backend/data/relationinsight.db` 仍 7 张表 0 行。

**未判验收：** 本任务只完成集成与端到端自测；`ACCEPTANCE.md` 全部「必须」项的结论与豁免签字由 **WorkBuddy / Cursor** 出具，Codex 不自行判定通过。**2026-09-23 的缺陷修复同样不自行判验收**：必须项 5 需由 WorkBuddy 重跑产品路径复验。

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
| 0.9 | 2026-09-22 | T-008 **集成部分**完成（总表与明细「当前状态」改「集成完成，待 WorkBuddy 验收」并补实现记录 / 端到端自测结果 / 遗留问题）；T-007 遗留问题 ①② 标「已确认（2026-09-22）维持现状」、未成年人标准与 DeepSeek URL 与口令三项移入 v1.1 遗留；落地：`backend/main.py` 新增 `messages:import` 与 `profile` 接口 + CORS(8501)，`frontend/app.py` 改读真实画像并接线导入 / 刷新。**未判 `ACCEPTANCE.md` 通过** |
| 1.0 | 2026-09-23 | **T-008 缺陷修复**（必须项 5「追加消息后画像版本 +1」）：`ARCHITECTURE.md` §6 补冻结「追加导入自动续号」；`parser.parse_chat()` / `import_chat()` 新增 `seq_offset`，`backend/main.py::import_messages()` 写库前取 `MAX(seq)+1` 实现续号（先偏移后检测冲突，方案 A 语义不变）；T-002 补 `seq` 语义；新增 `tests/test_import_append.py` + `tests/test_parser.py` 2 例 → `125 passed`。T-008 状态改「修复完成，待 WorkBuddy 复验必须项 5」 |
| 1.1 | 2026-09-23 | T-008 必须项 5 复验通过（WorkBuddy 走真实浏览器 7 步产品路径）；T-008 状态改「完成」；MVP 7 个必须项 7/7 通过 |
