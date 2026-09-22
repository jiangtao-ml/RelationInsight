# HANDOFF.md — 交接记录模板

**项目：** 关系洞察系统 MVP  
**用途：** 每个任务（T-xxx）**完成后**追加一节，供下一工具接续。不要改历史记录正文，勘误请新增「更正」小节。

---

## 使用说明

1. 复制下方「空白模板」到本文档末尾。  
2. 将 `当前状态` 与 `TASKS.md` 同步改为 `完成`。  
3. **WorkBuddy** 负责提醒：无交接记录不得把任务标完成。  
4. 不确定的事实写「假设」或「需人工确认」，不要编造成功测试。

---

## 空白模板（复制用）

```markdown
## [任务ID] [任务标题] — [完成日期 YYYY-MM-DD]

### 负责工具
- 主责：
- 协作：

### 修改文件
- （路径，相对仓库根）

### 如何运行
```text
# 环境变量
# 启动命令
# 关键 URL
```

### 测试结果
| 用例 | 结果 | 备注 |
|------|------|------|
| | 通过 / 失败 / 未测 | |

### 遗留问题
- 

### 下一步
- 建议下一任务：
- 阻塞项：
- 需人工确认：
```

---

## 字段说明

| 字段 | 要求 |
|------|------|
| 负责工具 | 与 TASKS.md 一致：Cursor / Codex / WorkBuddy |
| 修改文件 | 列出新增与修改，不贴大段源码 |
| 如何运行 | 另一台机器按此能复现；注明工作目录与 Python 版本 |
| 测试结果 | 自动化 + 手工；Fake 模型与真 API 分开写 |
| 遗留问题 | 已知缺陷、技术债、范围外发现 |
| 下一步 | 明确交给谁、先做哪条任务 |

---

## 交接记录（按时间追加）

_（启动时无已完成任务；T-001 起在下方按时间追加）_

<!-- 示例：请勿当作已完成

## T-001 搭建 FastAPI + SQLite 项目骨架 — 2026-09-xx

### 负责工具
- 主责：Codex
- 协作：Cursor（目录评审）、WorkBuddy（本机启动）

### 修改文件
- backend/main.py
- backend/db.py
- requirements.txt

### 如何运行
```text
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```
浏览器打开 http://127.0.0.1:8000/health

### 测试结果
| 用例 | 结果 | 备注 |
|------|------|------|
| GET /health | 未测 | 模板示例 |

### 遗留问题
- 异步/同步栈未确认

### 下一步
- 建议下一任务：T-002、T-003 可并行
- 阻塞项：无
- 需人工确认：Python 版本

-->

## T-001 搭建 FastAPI + SQLite 项目骨架 — 2026-09-22

### 负责工具
- 主责：Codex（实现与自测）
- 协作：Cursor（目录与接口约定、表结构对照）、WorkBuddy（本机环境与启动验证）

### 修改文件
- `backend/main.py`（新增）：同步 FastAPI 应用；启动钩子调用 `init_db()`；`GET /health`
- `backend/db.py`（新增）：`DB_PATH`、`get_connection()`、`init_db()`、`list_user_tables()`、`REQUIRED_TABLES`
- `backend/schema.sql`（新增）：6 张表 DDL（persons / messages / analyses / evidence / profile_versions / consents）+ 8 个索引
- `backend/.env.example`（新增）：`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` 占位，无真实值
- `backend/.gitignore`（新增）：忽略 `.env`、`data/*.db`、`.venv/`、`__pycache__/`
- `requirements.txt`（新增）：`fastapi>=0.115.0,<1.0.0`、`uvicorn>=0.32.0,<1.0.0`
- `backend/data/relationinsight.db`（运行时生成，非手写）：空库，6 表 0 行，已被 `.gitignore` 覆盖
- `backend/.venv/`（本机虚拟环境，Python 3.12.4；不属于交付代码）
- 本次交接未改动任何代码，只写 `HANDOFF.md` 与 `TASKS.md`

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# 工作目录：C:\Users\17352\Desktop\RelationInsight\backend
# 本机已有虚拟环境 backend\.venv（Python 3.12.4；规格冻结为 3.11，见「遗留问题」第 1 条）

# 环境变量（T-001 不需要真实 Key；不要在仓库内提交 .env）
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 可选：冷启动重建依赖（等价于当前 .venv）
cd C:\Users\17352\Desktop\RelationInsight\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r ..\requirements.txt

# 启动服务
cd C:\Users\17352\Desktop\RelationInsight\backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# 关键 URL
#   http://127.0.0.1:8000/health
#   http://127.0.0.1:8000/docs   （FastAPI 自带，非验收项）
# 数据库文件在启动时自动创建/复用：backend\data\relationinsight.db
```

### 测试结果
（2026-09-22 本机实测。自动化测试文件：无——T-001 未要求）

| 用例 | 结果 | 备注 |
|------|------|------|
| 启动 `uvicorn main:app`（127.0.0.1:8000） | 通过 | 日志 `Application startup complete` |
| `GET /health` 返回 200 | 通过 | 实测 HTTP 200（TASKS.md 验收标准 ①） |
| `/health` 报告的库与表状态 | 通过 | `status=ok`、`database_exists=true`、`missing_tables=[]`、`python=3.12.4` |
| 空目录冷启动自动建库 | 通过 | 指向全新临时路径调用 `init_db()`：生成 90112 字节库文件，6 表齐全（验收标准 ②） |
| 6 张必需表存在（现有库） | 通过 | analyses / consents / evidence / messages / persons / profile_versions |
| 仓库无真实 API Key | 通过 | 全仓（排除 `.venv`）正则扫描 `sk-…` 与 `DEEPSEEK_API_KEY=<值>` 零命中；无 `backend/.env`，仅 `.env.example`（验收标准 ③） |
| 依赖清单可用 | 通过 | 现有 `.venv` 实际版本：fastapi 0.141.1、starlette 1.6.0、uvicorn 0.53.0、pydantic 2.13.5（本次未重装） |
| 表结构对齐 `ARCHITECTURE.md` 4.1–4.7 | 通过 | 逐表核对 persons / messages / analyses / evidence / profile_versions / consents 的列名与约束一致；`schema.sql` 另加 CHECK 与索引（文档未禁止） |
| 单元测试（pytest 等） | 未测 | 仓库无 `tests/`，T-001 未要求，留给 T-002 起的任务 |
| Fake 模型路径 | 未测 | `FakeDeepSeekClient` 属 T-003，本任务无模型代码 |
| 真实 DeepSeek API 调用 | 未测 | 无 Key 且超出 T-001 范围；本次验证全程零外网请求 |
| 删除 / VACUUM 残留检查 | 未测 | 属 T-007；当前库 0 行 |

### 遗留问题
- **Python 版本与冻结规格不一致（建议优先决策）**：`ARCHITECTURE.md` 与 `TASKS.md` v0.1 冻结 **Python 3.11**，本机 `backend/.venv` 及运行时为 **3.12.4**（`pyvenv.cfg` 与 `/health` 的 `python` 字段一致）。需人工确认：接受 3.12 并同步改文档，还是用 3.11 重建 venv 后复验。
- **仓库无版本控制**：根目录没有 `.git`（`git status` 报 not a repository），无法为 `ACCEPTANCE.md`「分支/提交」提供提交号；忽略规则只有 `backend/.gitignore`，`PRIVACY.md` §6 期望的仓库根 `.gitignore` 缺失，因此「Key 不入 Git」目前靠人工纪律而非工具兜底。
- `@app.on_event("startup")` 属 FastAPI 旧式事件钩子（推荐改用 `lifespan`）；本次运行未观察到告警，建议 T-002 / T-003 期间一并迁移。
- `conversations` 表按 `ARCHITECTURE.md` 4.2 仍待人工确认，未创建；`persons.conversation_id`、`messages.conversation_id` 为无外键的文本列，T-007 级联删除缺少数据库级约束兜底。
- `corrections` 表（`ARCHITECTURE.md` 4.8 建议项）未创建。
- 数据库 `journal_mode = delete`（非 WAL）；T-007 的「无明文残留」验收需按该模式设计，`VACUUM` 应列为必做步骤。
- `/health` 额外返回 `python` / `database_path` / `database_exists` / `tables` / `missing_tables`：超出验收最小要求（无害），T-008 若做字段断言需注意此契约。
- 依赖未锁定精确版本（`>=,<` 区间）；fastapi 0.141.1 + starlette 1.6.0 组合仅在 Python 3.12.4 上验证过。
- 本任务只验证「库表 + 健康检查」；导入解析、模型调用、增量画像、删除路径均未触及，功能正确性不能由本记录推断。

### 下一步
- 建议下一任务：**T-002（文本解析器）与 T-003（DeepSeek 客户端封装）并行**，两者依赖的 T-001 已就绪；T-006（Streamlit 原型）不依赖后端，也可同时开工。
- 阻塞项：无（TASKS.md 中 T-001 验收标准 ①–④ 全部通过）。
- 需人工确认：① Python 基线取 3.11 还是 3.12.4；② 是否初始化 Git 并补仓库根 `.gitignore`；③ `message_id` 算法（`ARCHITECTURE.md` §6 方案 A/B，T-002 实现前须冻结）；④ `conversations` 表是否创建（影响 T-007 删除范围与 persons 外键设计）。
- 交接指向：T-002 / T-003 交 **Codex** 实现；**Cursor** 先冻结 `message_id` 算法与请求/响应 Schema；**WorkBuddy** 在版本基线确定后按本记录「如何运行」复验启动与 `GET /health`。

### 更正（2026-09-22，T-002/T-003 期间按三项决策补记）

- 「遗留问题」第 1 条（Python 3.11 与实测 3.12.4 冲突）**已裁决**：基线改为 **Python 3.12.4**，`ARCHITECTURE.md` §0/§4/§8 与 `TASKS.md` 顶部规格已同步；不重建 3.11 venv。上面「如何运行」里「规格冻结为 3.11」一句作废，命令本身仍有效。
- 「遗留问题」第 2 条（仓库无版本控制）**已裁决并落地**：仓库根已 `git init`（分支 `main`），新增根 `.gitignore`（`.env`、`*.db`、`data/`、`.venv/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`），保留 `backend/.gitignore`。**截至本记录写入时仍无任何 commit**（`HEAD` 未创建），`ACCEPTANCE.md` 需要的「分支/提交号」需首次提交后补齐。
- 「需人工确认」③（`message_id` 算法）**已冻结为方案 A**：`message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`，`seq` 从 0 起按导入顺序递增；重复导入**拒绝整批**并在报告中列出冲突 ID 与来源行号（详见 `ARCHITECTURE.md` §6 与下方 T-002 记录）。方案 B 废弃。
- 仍未裁决：「需人工确认」④ `conversations` 表是否创建；`person_id` 生成方式（见 T-002 记录）。

---

## T-002 文本解析器 — 2026-09-22

### 负责工具
- 主责：Codex（实现与自测）
- 协作：Cursor（冻结输入格式与 `message_id` 算法）、WorkBuddy（本机执行 pytest 复核）

### 修改文件
- `backend/parser.py`（新增）：`parse_chat()` / `insert_messages()` / `import_chat()`；`MessageDTO` / `ParseError` / `ParseResult` / `Conflict` / `InsertReport` / `ImportReport`；`make_message_id()` / `make_person_id()`
- `tests/test_parser.py`（新增）：11 个用例，含「正常文本」「含错误行文本」两个夹具样例
- 未改动 `backend/main.py`、`backend/db.py`、`backend/schema.sql`（遵守任务边界）

### 如何运行
```text
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m pytest tests -q
backend\.venv\Scripts\python.exe -m pytest tests/test_parser.py -q

# 库文件：测试一律写入 pytest 的 tmp_path，不碰 backend\data\relationinsight.db
# 需要独立库时用 db_path 参数：import_chat(text, "conv-1", db_path=Path("..."))
```

### 测试结果
（2026-09-22 本机实测：Python 3.12.4、pytest 9.1.1；`pytest tests -v` → `36 passed in 0.39s`，其中本任务 11 例）

| 用例 | 结果 | 备注 |
|------|------|------|
| 夹具 1：正常文本（4 条消息 + 1 空行） | 通过 | `seq` 0–3、`source_line` 1/3/4/5、`body` 逐字一致、`blank_lines_skipped=1` |
| 夹具 2：含错误行文本 | 通过 | 错误行号/原因 2=`REASON_BAD_SPEAKER`、3/7=`REASON_NO_COLON`、4=`REASON_NO_SPACE`、5=`REASON_EMPTY_BODY`；错误行不阻断成功行，成功行 `seq` 仍从 0 起 |
| 冻结算法 `uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")` | 通过 | 逐条与标准库 `uuid.uuid5` 比对一致；可复现、`seq` 敏感、`conversation_id` 不做 strip |
| 写库（`messages` + `persons`） | 通过 | 临时库：4 行 messages、2 行 persons（A/B 各一）、`PRAGMA foreign_key_check` 为空 |
| 同一文本 + 不同 `conversation_id` | 通过 | 两个会话共 8 行、4 个 person，互不冲突 |
| 重复导入「拒绝整批」 | 通过 | 第二次 `status=rejected_conflict`、`inserted_count=0`；冲突列出 4 个 ID + 行号 1/3/4/5；库内行数不变 |
| 批内部分冲突仍整批拒绝 | 通过 | 只有 1 个 ID 冲突时，不冲突的那条也**没有**写入 |
| 批内自重复检测 | 通过 | 同一批出现两次同一 ID → 拒绝，列出两条来源行 |
| 空行计数与空批次 | 通过 | 纯空行输入 `blank_lines_skipped=4`；无可写内容时不创建库文件 |
| 全量回归 | 通过 | `tests/` 36 例全部通过（含 T-003 的 25 例） |
| 与 FastAPI 接口联调（`POST /conversations/{id}/messages:import`） | 未测 | 该接口属后续任务；本任务未改动 `main.py` |
| 真实 DeepSeek API | 未测 | 属 T-003；本任务全程零网络请求 |

### 遗留问题
- `person_id` 算法**未冻结**：本实现假设 `uuid5(NAMESPACE_URL, f"person:{conversation_id}:{role}")`（会话内 A/B 各一个确定性 ID）。
- 含错误行时仍导入成功行（规格只要求「记入错误列表」，未要求整批中止）；若产品要求整批拒绝需另改。
- 正文不做 strip：只剥掉冒号后的**一个**空格，其余空格/二次冒号原样入库；`A:  你好` 的正文是 ` 你好`。
- 仅识别半角 `:` 与大写 `A`/`B`；全角 `：`、小写 `a:`、时间前缀、微信/QQ 导出均计入错误行（按 v0.1 冻结）。
- `import_chat()` 不含样本量门闩（< 20 条拒绝属 T-004 管道逻辑）。
- `messages` 表没有 `UNIQUE(conversation_id, seq)` 约束，`seq` 唯一性靠解析器与 `message_id` 主键保证（`schema.sql` 属 T-001，本次未改）。
- 日志按 `PRIVACY.md` 只记录会话 ID 与条数；未实现脱敏（脱敏属 T-003/T-007）。
- 测试文件自带 `sys.path` 引导（未新增 `tests/conftest.py`，因任务只允许新增 `tests/test_parser.py`）。

### 下一步
- 建议下一任务：**T-004 分批分析管道**（依赖 T-002 + T-003，两者均已就绪）。
- 阻塞项：无（TASKS.md T-002 验收标准 ①–⑤ 全部有对应用例且通过）。
- 需人工确认：① `person_id` 生成方式；② 含错误行是否应改为整批拒绝；③ `conversation_id` 由谁分配、是否建 `conversations` 表。
- 交接指向：T-004 交 **Codex** 实现；**Cursor** 冻结 prompt 与批次元数据字段；**WorkBuddy** 按上方命令复跑 `pytest tests -q` 复核。

---

## T-003 DeepSeek API 客户端封装 — 2026-09-22

### 负责工具
- 主责：Codex（实现与自测）
- 协作：Cursor（§5 JSON 契约与禁止事项）、WorkBuddy（本机安装依赖并复跑 pytest）

### 修改文件
- `backend/llm/__init__.py`（新增）：再导出 `DeepSeekClient` / `FakeDeepSeekClient` / `DeepSeekError` 等
- `backend/llm/deepseek.py`（新增）：`BaseDeepSeekClient`、`DeepSeekClient`、`FakeDeepSeekClient`、`DeepSeekError`、`mask_text()`、`build_user_payload()`、`parse_json_object()`、`validate_profile_json()`、`find_unknown_evidence_ids()`、`DEFAULT_SYSTEM_PROMPT`
- `tests/test_deepseek.py`（新增）：25 个用例（含参数化），全部离线
- `requirements.txt`（修改）：新增 `openai>=1.40.0,<3.0.0`、`pytest>=8.0.0,<10.0.0`、`pytest-mock>=3.14.0,<4.0.0`（原有 fastapi / uvicorn 两行未动）
- 未改动 `backend/main.py`、`backend/db.py`、`backend/schema.sql`（遵守任务边界）

### 如何运行
```text
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
backend\.venv\Scripts\python.exe -m pytest tests/test_deepseek.py -q

# 真实调用（需要 Key；本任务**未**执行，单测全部使用替身/Fake，零外网）
set DEEPSEEK_API_KEY=<你的 Key>
set DEEPSEEK_BASE_URL=https://api.deepseek.com
set DEEPSEEK_MODEL=deepseek-chat

# 最小调用形状（T-004 可直接照抄）
# from llm import DeepSeekClient, FakeDeepSeekClient
# client = DeepSeekClient()                       # Key 只从 DEEPSEEK_API_KEY 读
# profile = client.analyze_batch(messages, DEFAULT_SYSTEM_PROMPT,
#                               person_roles={person_id: "A", ...})
```

本机实测依赖版本：openai 2.54.0、pytest 9.1.1、pytest-mock 3.15.1（venv 内另有 fastapi 0.141.1 / uvicorn 0.53.0）。

### 测试结果
（2026-09-22 本机实测：Python 3.12.4；`pytest tests -v` → `36 passed in 0.39s`，其中本任务 25 例。全程零网络请求）

| 用例 | 结果 | 备注 |
|------|------|------|
| 脱敏 4 类（策略 α） | 通过 | 手机号/邮箱/身份证/银行卡原值均被替换为占位符；对无强标识文本不做改动；幂等 |
| 调用前脱敏（真实发送内容） | 通过 | 断言 user content 中 4 个原值零命中、占位符出现；`masked_count=8`（2 条 × 4 处） |
| Key / base_url / model 读取 | 通过 | Key 取 `DEEPSEEK_API_KEY`；`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 可覆盖；未设时默认 `https://api.deepseek.com` + `deepseek-chat`；`repr(client)` 不含 Key |
| 缺 Key | 通过 | `DeepSeekError(kind=missing_api_key)`，提示只指向环境变量 |
| 统一错误：401 / 429 / 5xx / 超时 / 连接失败 | 通过 | 参数化 5 例 → `auth_error` / `rate_limited` / `server_error` / `timeout` / `connection_error`，`status_code` 与 `attempts` 正确 |
| 重试策略 | 通过 | 429 首次失败、第二次成功（`attempt=2`）；401 立即失败不重试 |
| §5 结构校验 | 通过 | 非 JSON、缺 `dyad`/`warnings`、`confidence=1.4` 均抛 `bad_response`；``` 围栏与前后说明文字可容忍 |
| 证据 ID 自查 | 通过 | `find_unknown_evidence_ids()` 命中编造 ID；`strict_evidence_ids=True` 时抛错，默认只警告 |
| `FakeDeepSeekClient`（离线联调） | 通过 | 返回合法 §5 JSON、证据 ID 只取自输入、记录 `calls` 中只有脱敏后文本；与 `parser.parse_chat()` 串通验证 |
| 日志隐私 | 通过 | DEBUG 级全量日志中 4 个原值零命中，只出现 `message_id` 与条数 |
| 异常隐私 | 通过 | 上游异常文本携带原文时，`str(DeepSeekError)` 仍零命中（只保留类名/状态码） |
| `response_format={"type": "json_object"}` | 未测（对真实 API） | 单测只能断言该参数被传递；真实 API 是否接受需联网验证 |
| 真实 DeepSeek API（含真机 401/429 行为、`timeout`/`base_url` 实际效果） | 未测 | 无 Key 且本任务明确不打真实网；错误映射按 openai SDK 异常类名 + `status_code` 实现 |
| 写入 `analyses` / `evidence` | 未测 | 落库属 T-004；本模块不碰数据库 |

### 遗留问题
- 脱敏只覆盖策略 α 的 4 类；**QQ 号、微信号、详细地址、姓名、单位名不在范围**（需人工确认是否扩展，或在 T-007 的 `privacy` 模块统一）。
- 18 位纯数字串一律按身份证处理（与 18 位银行卡号字面不可区分）；故脱敏规则顺序为 身份证 → 银行卡。
- `messages.body` 存原文、只在调用前脱敏（策略 α 冻结）；`evidence.quote` 需存脱敏后文本，写库属 T-004。
- 未做 `response_format` 降级：若模型不支持 JSON mode，服务端 400 会归为 `bad_response`（无自动重试）。
- 重试次数（3）与退避（1.5s 指数）是**假设值**，规格只要求「统一错误类型」。
- `MessageDTO` 没有 `speaker` 字段：不传 `person_roles` 时说话人只能是 `?`（单测已固化该行为，T-004 必须传映射或直接传带 `speaker` 的 dict）。
- 客户端只做**结构**校验；「`evidence.quote` 等于脱敏后原文摘录」等语义校验属 T-004。
- 未实现「每 50 条一批」「< 20 条拒绝分析」等管道逻辑（T-004 范围）。
- `BaseDeepSeekClient._complete()` 抛 `NotImplementedError`（抽象方法约定），未使用 `abc` 模块。

### 下一步
- 建议下一任务：**T-004 分批分析管道**（T-002 + T-003 均已就绪）。
- 阻塞项：无（TASKS.md T-003 验收标准 ①–⑤ 均有用例覆盖；标注「需人工确认」的 `response_format` 细节已按假设实现并留白）。
- 需人工确认：① `response_format` 是否按当前假设使用；② 重试次数/退避是否需要调整；③ 脱敏是否扩展到 QQ/微信号；④ `evidence_message_ids` 是否要求严格限定在本批（当前默认仅警告）。
- 交接指向：T-004 交 **Codex** 实现；**Cursor** 冻结 system prompt 与批次元数据；**WorkBuddy** 复跑 `pytest tests -q` 与（拿到 Key 后）一次真实 API 冒烟。

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1 | 2026-09-21 | 模板初稿 |
| 0.2 | 2026-09-22 | 追加 T-001 交接记录 |
| 0.3 | 2026-09-22 | T-001 记录补「更正」小节（Python 基线 / Git / message_id 决策落地）；追加 T-002、T-003 交接记录 |
