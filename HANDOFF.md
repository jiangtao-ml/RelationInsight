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

## T-004 分批分析管道 — 2026-09-22

### 负责工具
- 主责：**Codex**（实现与自测）
- 协作：**Cursor**（system prompt 与批次元数据定稿、§5 schema 对照）；**WorkBuddy**（复跑测试、核对库文件行数）

### 修改文件
- `backend/pipeline/__init__.py`（新增）：包出口；对外只有 `analyze_conversation` / `analyze_conversation_from_db` / `plan_batches` 三个名字
- `backend/pipeline/batch.py`（新增）：`BATCH_SIZE=50`、`MIN_MESSAGES_FOR_ANALYSIS=20`、`Batch` / `BatchPlan` / `plan_batches()` / `InsufficientSampleError`
- `backend/pipeline/prompt.py`（新增）：`PROMPT_VERSION="1.0"`、`SYSTEM_PROMPT`（禁止诊断 / 人格标签 / 读心 / 操控 / 编造证据）、`build_system_prompt()`
- `backend/pipeline/run.py`（新增）：`load_messages`、`filter_profile`（证据双闸门）、`persist_batch`（1 行 `analyses` + N 行 `evidence` 同事务）、`analyze_conversation`、`analyze_conversation_from_db`、`PipelineReport`
- `tests/test_pipeline.py`（新增）：**34 例**，全程离线（`llm.FakeDeepSeekClient` + pytest `tmp_path`），不碰真实 API、不碰 `backend/data/relationinsight.db`
- `backend/schema.sql`（修改）：新增 `conversations` 表（§4.2 拍板）+ 索引 `idx_conversations_status`；表头注释更新
- `backend/db.py`（修改）：`REQUIRED_TABLES` 加入 `"conversations"`（`/health` 现检查 7 张表）
- `ARCHITECTURE.md`（修改）：§0 追加 2026-09-22 冻结表；§4.1 `person_id` 生成方式；§4.2 `conversations` 改为「已确认创建」；§4.5 补 `speaker_role` 读法；§6 区分「解析错误行」与「`message_id` 冲突」两条策略；§8 补 `response_format` / 重试 / 超时 / 脱敏范围；§9 记 0.3
- `TASKS.md`（修改）：T-004 总表与明细状态改「完成」；T-002 / T-003 明细中已拍板的「需人工确认」改为「已确认」
- `HANDOFF.md`（本记录）
- **未改动**：`backend/main.py`、`backend/parser.py`、`backend/llm/*`、`requirements.txt`（`openai` / `pytest` / `pytest-mock` 已在 T-003 加入）
- **未污染数据**：`backend/data/relationinsight.db` 仍为 7 张表 0 行（仅多出空的 `conversations` 表）

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 全量单测（离线、零网络）
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m pytest tests -q

# 只跑本任务
backend\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -q

# 健康检查（7 张表齐全，missing_tables 为空）
cd C:\Users\17352\Desktop\RelationInsight\backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
#   http://127.0.0.1:8000/health

# 管道调用（Fake 客户端：不联网、不花钱）
#   from pipeline import analyze_conversation_from_db
#   from llm import FakeDeepSeekClient
#   report = analyze_conversation_from_db("conv-1", FakeDeepSeekClient())
#   print(report.summary())   # [completed] conversation=conv-1 messages=100 batches=2 analyses=2 ...
#   print(report.message)     # 面向使用者的一句话（含「样本不足」等）
```

### 测试结果
（2026-09-22 本机实测：Python 3.12.4；`pytest tests -q` → **`70 passed in 3.14s`**，其中本任务 34 例、T-003 25 例、T-002 11 例。全程零网络请求、零真实 API 调用。）

| 用例 | 结果 | 备注 |
|------|------|------|
| 验收 ① 100 条 → 2 个完整批 | 通过 | `[50, 50]`；`seq` 区间 `(0,49)` / `(50,99)`；`message_id_from/to` 与库内首尾一致；`message_ids` 不重不漏 |
| 验收 ① 余数规则 | 通过 | 120 条 → `[50, 50, 20]`；51 条 → `[50, 1]`；余数批 `is_remainder=True`、独立成批、再调一次模型，`sample_size=20` 写入该批 `result_json.warnings` |
| 验收 ② 写库时校验证据 ID 存在 | 通过 | 编造 ID 不入库；跨会话 ID 被丢弃；本批真实存在的 ID 照常入库；`evidence.message_id` 全部 ∈ `messages` |
| 验收 ③ 缺证据的结论不入库 | 通过 | `evidence_message_ids=[]` 的结论不落 `result_json`；报告 `dropped_count` 与 `warnings` 留痕；证据全被剔除的结论整条丢弃（reason=`REASON_NO_EVIDENCE`） |
| 验收 ④ 总数 < 20 拒绝正式分析 | 通过 | 0 / 1 / 19 条抛 `InsufficientSampleError`（文案含「样本不足」）；19 条走管道 → `status=insufficient_sample`、`call_count=0`、`analyses`/`evidence` 均无行；恰好 20 条放行 |
| 验收 ⑤ 调用前脱敏 | 通过 | 手机号 / 邮箱 / 身份证 / 银行卡 4 个原值在发往模型的文本中零命中，占位符命中；`messages.body` 仍存原文；`evidence.quote == normalise_quote(mask_text(body))` |
| 系统提示词约束 | 通过 | 含「禁止 / 诊断 / 人格 / 读心 / 操控」，点名禁止「自恋型 / NPD / 依恋」，要求 `evidence_message_ids`、严格 JSON、§5 骨架；管道确实把它传给客户端 |
| 幂等（重复运行） | 通过 | 第二次运行 `analyses_written=0`、`batches_skipped=3`、`call_count=0`，旧行不被覆盖 |
| 失败即停 | 通过 | 401 → `status=failed`、`error_kind=auth_error`、只调用 1 次；非法 JSON → `bad_response`，管道不崩 |
| 日志隐私 | 通过 | DEBUG 级 `caplog` 中正文与 4 类原值零命中，会话 ID 仍可见 |
| 错误摘要隐私 | 通过 | `report.message` / `failures` / `warnings` 不含正文与原值 |
| 说话人映射 | 通过 | 从 `persons` 读 `person_id → A/B`；显式 `person_roles` 可覆盖（seq=0 由 A 改判为 B） |
| `GET /health`（回归） | 通过 | 7 张表齐全、`missing_tables: []`，`status: ok`（手工在 venv 内实测） |
| 真实 DeepSeek API 端到端 | 未测 | 无 Key，本任务不打真实网；`response_format` 与真机 429/超时行为需联网验证 |
| `POST /conversations` 建行 | 未测 | 属 API 层（T-007 / T-008）；本模块只读 `persons`，不写 `conversations` |
| T-005 增量合并 | 未测 | 属 T-005；本任务只做「每批一条 `analyses`」，不合并成 `profile_versions` |

### 遗留问题
- `speaker_role` 采用「该条证据消息的**真实说话人**」，`dyad.*` 证据也写 `A`/`B` 而非 NULL。已写入 `ARCHITECTURE.md` §4.5 并标注**需人工确认**（原草案只写「A/B」，未规定 dyad 情形）。单测名与 docstring 已按此读法固定。
- 管道把**原文** `MessageDTO` 交给 `client.analyze_batch()`，脱敏发生在客户端内部（T-003 契约，验收 ⑤ 由此满足）；`evidence.quote` 另用 `client.mask_batch()` 的输出生成，故 quote 与「实际发出去的文本」逐字一致，而与「库内原文」不同——这是策略 α 的设计意图，不是缺陷。
- `evidence.quote` 折叠空白并截断到 80 字符（`QUOTE_MAX_CHARS`）：因只取前缀，仍满足 §4.5「脱敏后文本的子串」要求；要看完整原文请回查 `messages.body`。
- 管道以 `strict_evidence_ids=False` 调客户端：越界 / 编造证据被降级为「丢弃 + 记录」而非整批失败，便于一次拿到完整报告。若将来要求「证据不合法即整批失败」，需改成 `True`（T-003 已支持）。
- 失败即停：某批抛 `DeepSeekError` 后不再尝试后续批次，已写入的批次保留，`status=failed`。当前没有「跳过失败批继续跑」的续跑入口。
- 幂等键为 `(conversation_id, batch_index)`：同一会话**追加**消息后，`batch_index=0` 仍是原来那 50 条、不会重算，只有新出现的尾批会被分析。「消息数变化后旧批是否要重算」留给 T-005 决策。
- 错误摘要直接内嵌 `DeepSeekError` 文本，依赖 T-003 的保证「异常文本不含聊天原文」；本模块未做二次清洗。
- 批次样本量只写进 `result_json.warnings`；`analyses` 表没有独立 `sample_size` 列（`seq_from` / `seq_to` 可推导）。若 UI 需要直接展示，建议 v1.1 加列。
- 「有 `messages` 但无 `conversations` 行」在当前版本是预期状态（导入器不隐式建会话行），不是数据损坏。
- 本次交接未改动任何 T-005+ 的代码。

### 下一步
- 建议下一任务：**T-005 长期画像增量更新**（把 2 批 `analyses` 合并成 `profile_versions` v1，并冻结 `trait_key` 与冲突合并规则）。
- 阻塞项：无。
- 需人工确认：① `speaker_role` 对 `dyad` 证据的读法（§4.5）；② 追加消息后是否需要重算既有批次（幂等键为 `batch_index`）；③ 是否给 `analyses` 加独立 `sample_size` 列；④ 失败批次是否需要「续跑」入口；⑤「证据不合法即整批失败」是否要成为默认。
- 交接指向：T-005 交 **Codex**；**Cursor** 定 `trait_key` 与合并冲突策略；**WorkBuddy** 复跑 `pytest tests -q`（当前应为 `70 passed`）并确认 `backend/data/relationinsight.db` 仍为 0 行。

## T-005 长期画像增量更新 — 2026-09-22

### 负责工具
- 主责：**Codex**（合并算法实现与离线自测）
- 协作：**Cursor**（`trait_key` 定义、四类变更与冲突合并策略、快照字段契约）；**WorkBuddy**（复跑 `pytest tests -q`、确认 `backend/data/relationinsight.db` 仍为 0 行）

### 修改文件
- `backend/pipeline/traits.py`（新增）：`trait_key` 规范化（`A.` / `B.` / `dyad.` 前缀）、`classify_change`（added / supported / weakened / revised 四类）、`weighted_average_confidence`（样本量优先加权）、`combine_observation`、`merge_unique_ids`（保首见顺序）；常量 `RULES_VERSION="1.0"`、`SUPPORT_SIMILARITY_THRESHOLD=0.5`、`WEAKEN_CONFIDENCE_DROP=0.15`
- `backend/pipeline/merge.py`（新增）：`update_profile`（主入口）/ `merge_profile`（纯函数）/ `persist_profile_version`（唯一 INSERT）/ `load_latest_profile` / `load_profile_versions` / `load_analyses` / `load_evidence` / `count_covered_messages` / `snapshot_to_sections` / `iter_snapshot_traits`；数据类 `AnalysisRecord` / `EvidenceRecord` / `ProfileVersionRecord` / `TraitChange` / `MergeResult` / `MergeReport`
- `backend/pipeline/__init__.py`（修改）：补齐 T-005 出口
- `tests/test_merge.py`（新增）：**23 例**，离线（`llm.FakeDeepSeekClient` + pytest `tmp_path`），逐条对应验收 ①–④
- `ARCHITECTURE.md`（修改）：§0 追加「2026-09-22 追加冻结（T-005 轮拍板）」表；§4.5 取消「需人工确认」——`speaker_role` 对 `dyad.*` 恒记真实说话人；§6 新增「批次幂等键 = `batch_index`、追加消息后不重算既有批次」；§8 新增「证据不合法 → 降级为丢弃 + 记录」行；§9 记 0.4
- `TASKS.md`（修改）：T-005 总表与明细状态改「完成」并补实现记录；T-004 补实现记录与遗留问题；修订记录 0.6
- `HANDOFF.md`（本记录）
- **未改动**：`backend/main.py`、`backend/db.py`、`backend/schema.sql`、`backend/parser.py`、`backend/pipeline/batch.py`、`backend/pipeline/prompt.py`、`backend/pipeline/run.py`、`backend/llm/*`、`requirements.txt`
- **未触碰**：`ACCEPTANCE.md`（含使用者本人尚未提交的改动）
- **未污染数据**：`backend/data/relationinsight.db` 仍为 7 张表 0 行；单测与冒烟一律用临时库（pytest `tmp_path` / 系统临时目录），跑完即弃

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 全量单测（离线、零网络）
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m pytest tests -q

# 只跑本任务
backend\.venv\Scripts\python.exe -m pytest tests/test_merge.py -q

# 合并调用（读库中该会话的 analyses / evidence → 新版本画像；全程离线）
#   from pipeline import update_profile
#   report = update_profile("conv-1")
#   print(report.status, report.version)   # completed 2
#   print(report.change_counts)            # {'added': 0, 'supported': 2, 'weakened': 0, 'revised': 0}
#   print(report.message)                  # 画像已更新到 v2（上一版 v1）：added 0、supported 2、weakened 0、revised 0
# 注意：会话必须已有 T-004 写入的 analyses 行，否则 status=nothing_to_do（不写库、不升版本）
```

### 测试结果
（2026-09-22 本机实测：Python 3.12.4；`pytest tests -q` → **`93 passed in 4.68s`**，其中本任务 23 例、T-004 34 例、T-003 25 例、T-002 11 例。全程零网络请求、零真实 API 调用。下表除标注「未测」外，均为本次实测或源码核对结果。）

| 用例 | 结果 | 备注 |
|------|------|------|
| 验收 ① 新增批次后版本 +1 | 通过 | 独立冒烟复验：50 条 → v1；追加 40 条使尾批越界成 `batch_index=1` → v2，`previous_version=1`、`message_count=90`、`analyses_used=1`、`analyses_skipped=1`（只折入新增尾批） |
| 验收 ① 无新批次不写行（幂等） | 通过 | 再次调用 → `nothing_to_do`，`profile_versions` 行数不变；`test_repeated_merge_without_new_batch_writes_nothing` |
| 验收 ① 余数批「原地长大」不重算 | 通过 | 冒烟复验：70 条 → v1；追加 20 条后管道仍计划 2 批、新写 `analyses` 0 条（`batch_index=1` 已存在）→ `nothing_to_do`，仍为 v1 且 `message_count=70` |
| 验收 ② 旧版快照逐字节不变 | 通过 | 升到 v2 后重读 v1 `snapshot_json`，与升版前**逐字节相同**（2107 字节）；旧版内 `A.request_style` 的 `statement`、`sample_size` 保持原值 |
| 验收 ③ 历史表述保留 + 结论级 `revision_of` | 通过 | `supported` 沿用旧表述并累加；`revised` 时新版另加条目、写 `revision_of`，旧条目标 `superseded_by` / `superseded_at_version`（`test_revision_adds_entry_and_records_revision_of`） |
| 验收 ④ 不 `UPDATE` 覆盖旧快照行 | 通过 | 源码核对：`merge.py` 对 `profile_versions` **只有一条 `INSERT`**，全文件无 SQL `UPDATE` / `DELETE`（命中的只是内存字典 `dict.update` 与注释）；`test_profile_versions_are_append_only` |
| 合并数值正确性 | 通过 | `confidence` 取样本量加权平均、`sample_size` 累加（25 → 45）、`evidence_message_ids` 合并去重（3 → 6），`statement` 不变 |
| 证据元数据跨版本保留 | 通过 | 脱敏 `quote` 与真实 `speaker_role` 随结论带入新版 |
| 坏批次降级 | 通过 | `analyses.result_json` 不可解析 → 跳过并记 `WARNING_BROKEN_ANALYSIS`，且**不计入** `covered_analyses`（下次仍可重试） |
| 越界 / 跨会话保护 | 通过 | 传入其他 `conversation_id` 的 `analyses` 被拒；两会话各写各的 `profile_versions`，互不干扰 |
| 纯规则单测（`traits.py`） | 通过 | 四类分类、加权平均、ID 合并保序、`trait_key` 规范化保守性、`statement_similarity` 对称性与阈值 |
| 真实 DeepSeek API 端到端 | 未测 | 无 Key，本任务不打真实网；真机上 `revised` 判定依赖模型返回的表述差异 |
| T-006 UI / T-007 删除 | 未测 | 属后续任务 |

### 遗留问题
- 变更分类是启发式：字符相似度 ≥ 0.5 视为 `supported`，置信度下滑 ≥ 0.15 视为 `weakened`，出现否定翻转或表述差异过大则判 `revised`。阈值集中在 `traits.py`（`SUPPORT_SIMILARITY_THRESHOLD` / `WEAKEN_CONFIDENCE_DROP`），将来调参不必改 `merge.py`。
- 幂等键是「已覆盖分析行 ID 的并集」（`covered_analyses`，由 `batch_index` 推导）：**已分析过的批次永不重算**，故「追加消息后旧批结论是否过期」本版不处理（2026-09-22 已拍板维持现状，见 `ARCHITECTURE.md` §6）。
- 余数批会「原地长大」：不足 50 条的尾批首次分析后即固定；若后续追加未越过 50 条边界，新消息不会被任何批次覆盖（冒烟已实测：70 → 90 条时无新批次，画像停在 v1）。
- `analyses` 表仍无独立 `sample_size` 列（T-004 遗留）；`snapshot_json.message_count` 为被覆盖消息数。
- 本模块无并发控制：同一会话并发 `update_profile` 可能撞 `UNIQUE(conversation_id, version)`。MVP 单用户同步调用，暂不处理。
- `snapshot_json` 顶层 `supersedes_version` 记录上一版版本号；结论级修订另见条目内 `revision_of` / `superseded_by`。
- 本次交接未改动任何 T-006+ 的代码。

### 下一步
- 建议下一任务：**T-006 Streamlit 前端原型**（可先用模拟数据；画像卡片直接渲染 `snapshot_to_sections()` 的输出即可对接 T-005）。
- 阻塞项：无。
- 需人工确认：① 证据 `quote` 折叠空白并截断 80 字符（`QUOTE_MAX_CHARS`）是否满足 UI 展示需求；② 余数批「原地长大」导致追加消息可能长期不进画像，是否需在 UI 解释或改批次策略；③ 并发写 `profile_versions` 是否需要加锁。
- 交接指向：T-006 交 **Codex**；**Cursor** 定信息架构与免责声明文案；**WorkBuddy** 复跑 `pytest tests -q`（当前应为 `93 passed`）并确认 `backend/data/relationinsight.db` 仍为 0 行。

---

## T-006 Streamlit 前端原型（模拟数据） — 2026-09-22

### 负责工具
- 主责：**Codex**（Streamlit 页面实现与离线点验）
- 协作：**Cursor**（信息架构、免责声明文案、与 `PRIVACY.md` 对齐）；**WorkBuddy**（按点击路径点验四块 UI、复跑 `pytest tests -q`）

### 修改文件
- `frontend/app.py`（新增）：Streamlit 单页原型 —— 左侧栏文本导入 + 顶部状态条 + 四个 tab（导入预览 / A/B 标记 / 画像卡片 / 证据列表）+ 底部免责声明
- `frontend/fixtures/mock_profile.json`（新增）：符合 `ARCHITECTURE.md` §5 的快照样例（`conversation_id=conv-demo-0001`、`version=3`、`message_count=63`；共 7 条条目 = 有效 6 条 + `superseded` 历史 1 条，每条均带 evidence）
- `frontend/requirements.txt`（新增）：`streamlit>=1.31,<2`（纯 ASCII，避免 Windows 下 pip 读取非 ASCII 注释触发编码错误）
- `ARCHITECTURE.md`（修改）：§6 新增「T-006 UI 约定」（余数批「原地长大」维持现状 + 前端顶部常显当前覆盖消息数与最新版本号）；§9 记 0.5
- `TASKS.md`（修改）：T-006 总表与明细状态改「完成」并补实现记录；T-005 三条遗留问题标「已确认」；修订记录 0.7
- `HANDOFF.md`（本记录）
- **未改动**：`backend/` 下任何文件（`main.py`、`db.py`、`schema.sql`、`parser.py`、`pipeline/*`、`llm/*`）、根 `requirements.txt`、`.gitignore`
- **未触碰**：`ACCEPTANCE.md`（含使用者本人尚未提交的改动）
- **未污染数据**：`backend/data/relationinsight.db` 仍为 7 张表 0 行；本任务纯前端，不读写数据库

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 安装前端依赖（首次）
backend\.venv\Scripts\python.exe -m pip install -r frontend\requirements.txt

# 启动原型（不启动 FastAPI，纯模拟数据）
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m streamlit run frontend\app.py
# 关键 URL：http://localhost:8501

# 离线自测（无需网络、无需 API Key）
backend\.venv\Scripts\python.exe -m pytest tests -q
```

### 测试结果
（2026-09-22 本机实测：Python 3.12.4；`pytest tests -q` → **`93 passed in 3.67s`**，与 T-005 后持平——本任务未新增单测文件。UI 侧用 `streamlit.testing.v1.AppTest` 跑 3 个离线场景，全程零网络请求、零真实 API 调用。）

| 用例 | 结果 | 备注 |
|------|------|------|
| 验收 ① 不启动 FastAPI 即可演示四块 UI | 通过 | `AppTest` 默认场景：4 个 tab = ① 导入预览 / ② A/B 标记 / ③ 画像卡片 / ④ 证据列表，无异常；仅读本地 fixture，不连后端 |
| 验收 ② 证据行可见 `message_id` 与脱敏 quote | 通过 | ④ 证据列表默认场景共 **20 行** evidence；quote 中出现 `[手机号]` / `[邮箱]` / `[银行卡号]`（与 `backend/llm/deepseek.py` 脱敏策略 α 一致） |
| 验收 ③ 同意勾选框 | 通过 | 勾选后提示「已勾选同意（原型：只存本地 local session state）」；联调写入 `consents` 属 T-007 |
| 验收 ④ 不做诊断式标题 | 通过 | 页面标题为「关系洞察 · 行为倾向归纳（原型）」，卡片文案为行为倾向类；全页无「自恋型」等诊断式命名 |
| 导入预览解析正确性（默认示例） | 通过 | 派生自真实 `backend/parser.py`：**63 条成功 / 4 行错误 / 3 行空行** |
| A/B 标记可改说话人 | 通过 | 场景 3：把 `seq=3` 改判为 B → 提示「已修改 1 条消息的说话人：seq 3 → B」，④ 中该 `message_id`（`63eaa5f5-…`）的 `speaker_role` 显示 `B（② 标记：由 A 改为 B）` |
| 空/短文本降级 | 通过 | 场景 2：输入 2 条合法 + 3 行错误 → 指标 2 条 / 3 行错误 / 1 行空行，仅 2 个说话人下拉框，无异常 |
| `frontend/app.py` 语法检查 | 通过 | `python -m py_compile frontend/app.py` OK |
| fixture 结构与 §5 契约 | 通过 | `json.load` OK；`schema_version=1.0`、`version=3`、`message_count=63`、`counts.active_traits=6`、`superseded_traits=1`、`total_traits=7` |
| 画像卡片三栏渲染 | 通过 | ③ 按 `snapshot_to_sections()` 分 A / B / dyad 三栏；卡片显示 statement / confidence / sample_size，并附 entry_key、change_kind、first_version、revision_of / superseded_by |
| 真实后端联调 / 真 API | 未测 | 属 T-008；本任务按验收 ① 只用模拟数据 |
| T-007 一键删除与同意落库 | 未测 | 属后续任务 |

### 遗留问题
- **② A/B 标记不写库**：`st.selectbox` 的改判只写 `st.session_state["speaker_overrides"]`，用于 ④ 证据展示的即时联动；持久化到 `messages.person_id` 属 T-008 接线。
- **同意勾选框为本地 state**：勾选状态不落 `consents` 表（验收 ③ 允许原型阶段先本地 state），T-007 接 API。
- **画像卡片数据源为静态 fixture**：`frontend/fixtures/mock_profile.json` 为手工构造（版本号、`covered_analyses` 等字段人写），不是真实 `profile_versions` 行的导出；T-008 应改为读后端画像接口。
- **依赖隔离**：`streamlit`（实测 1.64.0）及其依赖（pandas / pyarrow / numpy / pillow / altair）装进了 `backend\.venv`，尚未按 `frontend/requirements.txt` 拆独立虚拟环境；根 `requirements.txt` 未改动。
- **依赖缺失时的回退分支**：`openai` 等依赖不可用时，③ 画像卡片回退到本地等价分组逻辑（保证纯前端环境离线可演示）；该分支未在装了完整依赖的环境下覆盖测试。
- **UI 顶部对余数批只做文案提示**：常显「当前覆盖消息数 + 最新画像版本号」，但不会主动告知「最新一批消息未进画像」；如需更强提示（如与 `messages` 总行数对比）留待后续。
- **无真实 API 调用与无联调**：本任务不触碰网络，脱敏后的 quote 全部取自 fixture 预置文本。

### 下一步
- 建议下一任务：**T-007 一键删除与同意记录**（`consents` 落库 + 删除 API/UI + 残留检查；`conversations` 表已随 T-001 建表纳入 `REQUIRED_TABLES`，可支撑级联删除）。
- 阻塞项：无。
- 需人工确认：① T-007 删除范围是「删整个库」还是「按 `conversation_id`」；② 同意文案是否需 Cursor 按 `PRIVACY.md` 定稿后再落库。
- 交接指向：T-007 交 **Codex**；**WorkBuddy** 用 `streamlit run frontend\app.py` 按点击路径点验四块 UI 并复跑 `pytest tests -q`（当前应为 `93 passed`）、确认 `backend/data/relationinsight.db` 仍为 0 行；**Cursor** 对照 `PRIVACY.md` 复核免责声明与数据来源提示文案。

## T-007 一键删除与同意记录 — 2026-09-22

### 负责工具
- 主责：**Codex**（`backend/privacy.py` 实现、`backend/main.py` 接口接线、`frontend/app.py` 同意与删除入口接线、离线单测）
- 协作：**Cursor**（同意文案与 `PRIVACY.md` §1.3 逐字核对、删除范围与残留检查口径）；**WorkBuddy**（复跑 `pytest tests -q`、比对删除前后 `backend/data/relationinsight.db` 行数与文件大小、按点击路径点验 UI）

### 修改文件
- `backend/privacy.py`（新增）：同意文案唯一来源 `CONSENT_STATEMENT` / `CONSENT_STATEMENT_VERSION="v0.1-2026-09-21"` / `CONSENT_STATEMENT_SOURCE="PRIVACY.md §1.3"`；范围枚举 `SCOPE_BOTH_PARTIES` / `SCOPE_SELF_ONLY`；`record_consent` / `revoke_consent` / `load_consents` / `has_valid_consent` / `require_consent`（有效同意 = `granted=1 AND revoked_at IS NULL`）；`delete_conversation` / `delete_all_data`（单事务有序删除 → `VACUUM` → 清理 `-wal`/`-shm`/`-journal` → 字节级残留检查 → 追加 JSON 审计行）；`mask_for_model()` 复用 `llm.deepseek.mask_text`（脱敏正则不重复实现，符合 `ARCHITECTURE.md` §8）
- `backend/main.py`（修改）：新增 `POST /conversations/{id}/consent`、`DELETE /conversations/{id}`、`DELETE /data`；`POST /conversations/{id}/analyze` **前置**同意闸门（无有效同意 → `403 no_consent`，在调用管道之前就拒绝）；`app.state.db_path` / `audit_path` / `llm_client` 可注入（供离线单测，生产仍走 `db.DB_PATH`）；`GET /health` 语义不变
- `frontend/app.py`（修改）：同意勾选框接线 `POST /conversations/{id}/consent`（文案逐字取自 `privacy.CONSENT_STATEMENT`，不自行发挥）+ 范围单选；「删除本会话」按钮（需勾选确认框）；左侧栏「⚙️ 设置 · 危险操作（清空全部本地数据）」需二次确认；删除后展示回执（各表行数 / `vacuumed` / 残留是否干净）与 `PRIVACY.md` §2.3「删不掉的部分」说明
- `tests/test_privacy.py`（新增）：**28 个离线用例**（`tmp_path` 临时库 + `FakeDeepSeekClient` + `RELATIONINSIGHT_API_BASE` 指向不可达端口，零网络）
- `ARCHITECTURE.md`（修改）：§0 追加「2026-09-22 追加冻结（T-007 轮拍板）」表；§4.7 同意文案逐字 `PRIVACY.md` §1.3 与「有效同意」口径；§7 删除范围（按会话为主 + 设置页危险操作 + 二次确认）与实现约定（`confirm=true` 必填、删除顺序、`VACUUM`、残留检查只报文件名与命中数、同意闸门 403）；§9 记 0.6
- `TASKS.md`（修改）：T-007 总表与明细「当前状态」改「完成」，补实现记录与遗留问题，修订记录 0.8
- `HANDOFF.md`（本记录）
- **未改动**：`backend/db.py`、`backend/schema.sql`、`backend/parser.py`、`backend/llm/*`、`backend/pipeline/*`、`requirements.txt`、`.gitignore`（T-007 未新增依赖）
- **未触碰**：`ACCEPTANCE.md`（含使用者本人尚未提交的改动）
- **未污染数据**：`backend/data/relationinsight.db` 仍为 7 张表 0 行，且未生成 `backend/data/deletion_audit.jsonl`（单测把审计路径注入到 `tmp_path`）

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 启动后端（T-007 新接口）
cd C:\Users\17352\Desktop\RelationInsight\backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
#   POST   /conversations/{id}/consent        勾选同意 → 写 consents
#   POST   /conversations/{id}/analyze        无有效同意 → 403 no_consent
#   DELETE /conversations/{id}?confirm=true   按会话删除
#   DELETE /data?confirm=true                 清空全部本地数据（危险）
#   GET    /health

# 启动前端（同意勾选写 consents + 「删除本会话」+ 设置页危险操作）
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py

# 离线自测（无需网络、无需 API Key）
backend\.venv\Scripts\python.exe -m pytest tests -q
```
`confirm` 缺省为 `false`，缺参返回 `400 confirmation_required` —— 二次确认在 API 层强制，不只靠 UI。

### 测试结果
（2026-09-22 本机实测：Python 3.12.4；`pytest tests -q` → **`121 passed in 13.57s`**（T-006 后基线 93 + 本次新增 28）。全部离线：`tmp_path` 临时库 + `FakeDeepSeekClient`，零网络请求、零真实 API 调用。）

| 用例 | 结果 | 备注 |
|------|------|------|
| 验收 ① 无有效同意不得调用分析管道 | 通过 | `POST /conversations/{id}/analyze` 在 `require_consent` 处即返回 **403** `kind=no_consent`；用 monkeypatch 监视 `pipeline.analyze_conversation_from_db`，断言**调用次数 0** 且 `analyses` 行数不变；撤回（写 `revoked_at`）后同样 403；UI 侧 `btn_analyze` 未勾选时 `disabled=True` |
| 验收 ② 删除后业务表与同意表无该范围行 | 通过 | `DELETE /conversations/conv-1?confirm=true` 后 `evidence` / `analyses` / `profile_versions` / `messages` / `persons` / `consents` / `conversations` 该会话行数**逐表为 0**；同库另一个会话 `conv-2` 各表行数**逐表不变**（未误删） |
| 验收 ③ WAL/临时文件不含明文残留 | 通过 | 删除前对全部 `body` 采集 needle（≥ 6 字符、上限 200 条）；删除后 `VACUUM` + `PRAGMA wal_checkpoint(TRUNCATE)` + 清理 `-wal`/`-shm`/`-journal`；对库文件做**字节级**扫描 → `residual.clean=true`、`hits={}`，报告只含文件名与命中数、不含原文；`journal_mode=WAL` 场景单独覆盖 |
| 验收 ④ 操作可审计且不记原文 | 通过 | 每次删除追加一行 JSON 审计（`event` / `deleted_at` / `scope` / 各表行数 / `vacuumed` / `residual_clean`），`note="audit only: no plaintext recorded"`；断言审计文件与回执 `to_dict()` 中**不含**任何原文 needle |
| 同意文案逐字一致 | 通过 | 断言 `privacy.CONSENT_STATEMENT` == `PRIVACY.md` §1.3 引用行原文；接口回执 `statement.text` 与之相等，`statement.source == "PRIVACY.md §1.3"` |
| 同意落库字段最小化 | 通过 | `consents` 行恰好 7 列（`id` / `conversation_id` / `granted` / `scope` / `note` / `created_at` / `revoked_at`）；`note` 只含 `statement_version=v0.1-2026-09-21`，无原文 |
| scope 与文案版本校验 | 通过 | 非法 scope → 400 `invalid_scope`；过期 `statement_version` → 400 `stale_statement`；`self_only` 记录不能顶替 `both_parties_informed` 校验 |
| 删除闸门与错误码 | 通过 | 非法 / 未知 `conversation_id` → 400 / 404；`confirm` 缺失 → 400 `confirmation_required`（API 层强制二次确认）；重复删除同一会话 → 404 |
| 删除回执内容 | 通过 | 回执含 `deleted_rows` / `total_rows` / `vacuumed` / `temp_files_removed` / `residual.clean` / `disclosures`（`PRIVACY.md` §2.3 三条说明） |
| `DELETE /data` 全局清空 | 通过 | 单事务清空 7 张表 + `VACUUM`；`confirm` 缺失 → 400；UI 侧「设置 · 危险操作」需先勾选确认框才可点击 |
| UI 双重确认（`AppTest`） | 通过 | 未勾选时 `btn_submit_consent` / `btn_analyze` / `btn_delete_conversation` / `btn_delete_all` 全部 `disabled=True`；勾选「删除本会话」确认框后方可点击；「清空全部本地数据」需在设置页另行确认 |
| 日志不落原文 | 通过 | `caplog` 断言日志中不含原文；删除日志只含 `scope` / `deleted_at` / 行数 / 残留干净标记 |
| 真实 DeepSeek API | 未测 | 属 T-008；本次全部离线 |
| T-008 集成与验收 | 未测 | 属后续任务 |

### 遗留问题
- **撤回同意 vs 删除同意行**：现实现为「`revoke_consent` 只写 `revoked_at`（保留审计痕迹）」+「删除会话 / 清库时 `consents` 行随同删除」。`PRIVACY.md` §2.1 未明说撤回后是否保留该行，**需人工确认**。
- **删除后是否保留空库结构**：当前实现保留 7 张表结构、只清空行（不回删 `schema.sql` 定义）。**需人工确认**。
- **同意撤销后重授权**：同会话再次 `POST /consent` 会新增一行（旧的 `revoked_at` 行保留），有效同意取最新一行；是否改为一会话一行（UPSERT）待定。
- **`DELETE /data` 无口令保护**：二次确认只在 UI 勾选 + `confirm=true` 参数层面；`PRIVACY.md` §6 是否加简单口令待定。
- **未成年人 18 岁标准**：`PRIVACY.md` §4.1 的判定口径未定，本任务未实现任何年龄校验。
- **DeepSeek 隐私政策 URL**：`PRIVACY.md` §5 需补正式链接；本任务的免责声明只引用文案，不含 URL。
- **残留检查边界**：扫描覆盖库文件与 `-wal`/`-shm`/`-journal`；**不覆盖**文件系统级快照 / 备份 / SSD 磨损层，已在回执 `disclosures` 中如实说明。
- **`app.state` 注入路径**：单测通过 `app.state.db_path` / `audit_path` / `llm_client` 注入，生产路径仍是 `db.DB_PATH`；两者一致性未做启动期断言（`/health` 返回 `database_path`，可作 T-008 联调核对点）。
- **审计文件本身不加密**：`deletion_audit.jsonl` 只记时间与行数、无原文，但未加密也未随 `DELETE /data` 一并删除（当前实现会连带清理该文件外的数据；是否清审计留待确认）。

### 下一步
- 建议下一任务：**T-008 集成与验收**（`ACCEPTANCE.md` 全「必须」项 + 端到端样例 ≥ 70 条，以覆盖「1 个完整批 + 余数批」与追加消息增量）。
- 阻塞项：无。
- 需人工确认：① 撤回同意是否保留 `consents` 行；② 删除后是否保留空库结构；③ `PRIVACY.md` §4.1 未成年人标准、§5 DeepSeek 政策 URL、§6 是否加口令。
- 交接指向：T-008 交 **Cursor**（对照 `ACCEPTANCE.md` 出具结论）；**WorkBuddy** 执行手工项并复跑 `pytest tests -q`（当前应为 `121 passed`）、确认 `backend/data/relationinsight.db` 仍为 0 行且未生成审计文件；**Codex** 修复阻塞缺陷。

## T-008 集成与验收（集成部分） — 2026-09-22

### 负责工具
- 主责：**Codex**——前后端接线（`backend/main.py` 新增导入 / 画像接口与 CORS，`frontend/app.py` 改读真实画像并接线导入 / 刷新）与端到端自测
- 协作：**Cursor**（`ACCEPTANCE.md` 口径与结论把关、接口契约不越界）；**WorkBuddy**（按 `ACCEPTANCE.md` 逐条手工验收、复跑 `pytest tests -q`、比对 `backend/data/relationinsight.db` 行数）
- **本轮只做「集成 + 端到端自测」，不判验收通过**：是否达标由 **WorkBuddy / Cursor** 出具。

### 修改文件
- `backend/main.py`（修改）：新增 `POST /conversations/{id}/messages:import`（→ T-002 `parser.import_chat`；重复导入按 §6 方案 A **拒绝整批** → `409 duplicate_message_id` + `detail.conflicts`；响应不回显原文）与 `GET /conversations/{id}/profile`（读 T-005 快照，默认最新版 / `?version=N` 历史版，**只读**，无画像 → `404 no_profile`）；新增 `ImportRequest`、`_utc_now()`、`_ensure_conversation()`（`INSERT OR IGNORE` 补 `conversations` 主行）；`app = FastAPI(version="0.8.0")` + `CORSMiddleware`（`ALLOWED_ORIGINS = http://localhost:8501 / http://127.0.0.1:8501`）；**既有路由与 `app.state` 注入点（`db_path` / `audit_path` / `llm_client`）均未改动**
- `frontend/app.py`（修改）：画像卡片改为**优先** `GET /conversations/{id}/profile`（`resolve_snapshot()`：取到就用真实画像，取不到才回退 `frontend/fixtures/mock_profile.json` 并提示失败原因）；新增「导入到数据库」按钮（调 `messages:import`，展示写入条数 / seq 区间 / 错误行表 / 冲突表）与「刷新画像」按钮；新增 `set_flash()` / `render_flash()` / `fetch_profile()` / `invalidate_profile_cache()`（导入 / 分析 / 删除后自动失效画像缓存）；② A/B 标记页注明 `PATCH /messages/{id}/speaker` **本轮未接线**；同意勾选与「删除本会话」沿用 T-007 接线（确认可用）
- `TASKS.md`（修改）：T-008 总表与明细「当前状态」改「集成完成，待 WorkBuddy 验收」，补实现记录 / 自测结果 / 遗留问题；T-007 遗留问题 ①② 标「已确认」、未成年人标准 / DeepSeek URL / 口令三项移入 v1.1；修订记录 0.9
- `HANDOFF.md`（本记录）
- **未改动**：`backend/db.py`、`backend/schema.sql`、`backend/parser.py`、`backend/llm/*`、`backend/pipeline/*`、`backend/privacy.py`、`tests/**`、`requirements.txt`、`.gitignore`（T-008 未新增依赖、未新增测试文件）
- **未触碰**：`ACCEPTANCE.md`（含使用者本人尚未提交的改动，工作区里原样保留，未编辑、未提交）
- **未污染数据**：`backend/data/relationinsight.db` 仍 7 张表 0 行；自测全部跑在 `%TEMP%\relationinsight_t008_e2e\` 临时库上，临时脚本（`_e2e_*.py`）跑完已删，仓库根已无残留文件

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 1) 后端（T-008 新增两个接口）
cd C:\Users\17352\Desktop\RelationInsight\backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
#   POST   /conversations/{id}/messages:import   纯文本 → 解析 → 写 messages（T-008 新增）
#   GET    /conversations/{id}/profile           读画像快照，?version=N 读历史版（T-008 新增，只读）
#   POST   /conversations/{id}/consent           T-007
#   POST   /conversations/{id}/analyze           T-007（无有效同意 → 403 no_consent）
#   DELETE /conversations/{id}?confirm=true      T-007
#   DELETE /data?confirm=true                    T-007（危险操作）
#   GET    /health

# 2) 前端（画像自动改读后端；后端不可达时回退 mock_profile.json 只读演示）
cd C:\Users\17352\Desktop\RelationInsight
backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py
#   浏览器 http://localhost:8501
#   后端地址可用环境变量覆盖：set RELATIONINSIGHT_API_BASE=http://127.0.0.1:8000（默认值即此）

# 3) 离线回归（零网络、零真实 API）
backend\.venv\Scripts\python.exe -m pytest tests -q

# 4) 本轮端到端自测的复现方式（临时脚本，跑完即删；不落库到生产路径）
#   服务端：起真实 uvicorn，但把存储与模型注入到临时位置：
#     main.app.state.db_path    = <临时目录>\e2e.db
#     main.app.state.audit_path = <临时目录>\deletion_audit.jsonl
#     main.app.state.llm_client = llm.FakeDeepSeekClient()
#     uvicorn.run(main.app, host="127.0.0.1", port=8011)
#   客户端：用 streamlit.testing.v1.AppTest 驱动**真实页面**，环境变量
#     RELATIONINSIGHT_API_BASE=http://127.0.0.1:8011
#   点击顺序：导入到数据库 → 勾选同意并提交 → 分析并合并画像 → 重新渲染读画像 → 勾选确认并删除本会话
```

### 测试结果
（2026-09-22 本机实测：Python 3.12.4；`pytest tests -q` → **`121 passed in 21.91s`**，与 T-007 基线一致、无回归。端到端自测全程离线：真实 `uvicorn` + 真实 Streamlit 页面 + **`FakeDeepSeekClient`**，**零真实 DeepSeek API 调用**。）

| 用例 | 结果 | 备注 |
|------|------|------|
| 回归 `pytest tests -q` | 通过 | `121 passed`（T-008 未新增测试文件，验证既有 121 条不被接线破坏） |
| ① 服务健康 + CORS | 通过 | `GET /health` → 200、`status=ok`、`python=3.12.4`、7 张表齐；`Origin: http://localhost:8501` 与 `http://127.0.0.1:8501` 均回 `access-control-allow-origin`，`http://evil.example.com` **不回** ACAO；预检 `OPTIONS` → 200 且回显 `allow-methods` / `allow-headers` |
| ② 同意闸门先于管道 | 通过 | 未同意时 `POST /conversations/conv-demo-0001/analyze` → **403 `no_consent`**，且该会话 `analyses` 仍 0 行 |
| ③ 前端一键导入 63 条 | 通过 | 点「导入到数据库」→ `已写入 63 条消息（seq 0–62）；错误行 4 行未阻断导入`；库内 `conversations 1 / persons 2 / messages 63` |
| ④ 同意勾选写入 `consents` | 通过 | 勾选 + 提交 → `已写入 consents：2026-09-22T08:50:49Z · scope=both_parties_informed`（1 行） |
| ⑤ 分析 + 合并画像 | 通过 | 点「分析并合并画像」→ 2 批、`analyses` 2 行、`evidence` 12 行、`profile_versions` v1 |
| ⑥ 画像卡片读**真实**画像 | 通过 | 新开页面渲染：`GET /conversations/conv-demo-0001/profile` → 200、`version=1`、`message_count=63`；顶部指标「当前覆盖消息数 63 条 / 最新画像版本号 v1」；来源提示为**后端真实画像**；traits：`A.request_style`（conf 0.50 / sample 32 / evidence 6）、`B.request_style`（conf 0.50 / sample 31 / evidence 6） |
| ⑦ 一键删除（UI 二次确认） | 通过 | 勾选确认框 → 点「删除本会话」→ `已删除会话 conv-demo-0001 的本地数据（2026-09-22T08:50:50Z）：evidence 12、analyses 2、profile_versions 1、messages 63、persons 2、consents 1、conversations 1；VACUUM 已执行；残留检查通过（0 命中）` |
| ⑧ 删除后无残留 | 通过 | 七表「该会话」与「全库」计数**全部 0**；`e2e.db` 及 `-wal` / `-shm` / `-journal` 字节级扫描：手机号 / 邮箱 / 身份证号 / 银行卡号 / 示例正文 / 会话 ID 命中数均为 **0** |
| ⑨ 审计可追溯、不含原文 | 通过 | `deletion_audit.jsonl` 1 行：`event=delete`、`deleted_at`、`scope`、各表 `deleted_rows`、`total_rows`；**不含**聊天原文与任何 PII |
| ⑩ 调用模型前脱敏 | 通过 | 63 条中 seq 28/30/44 的 `messages.body` 确含手机号 / 邮箱 / 银行卡号原文（只留本机）；走真实管道 + 记录型 Fake 客户端后，**发往模型的文本 PII 命中全为 False**，并出现 `[手机号] 1` / `[邮箱] 1` / `[银行卡号] 1`；入库 `evidence.quote`（12 行）同样无 PII |
| ⑪ 脱敏会话删除后复检 | 通过 | 该会话七表计数全 0；库文件与 WAL 扫描 PII 命中 0 |
| ⑫ 真实 DeepSeek API | **未测** | 按本轮要求只用 `FakeDeepSeekClient`；真实 API 冒烟与 `ACCEPTANCE.md` 逐条结论留给 WorkBuddy / Cursor |

### 遗留问题
- **`PATCH /messages/{id}/speaker` 未接线**：② A/B 标记页的「改说话人」目前只改页面展示，**不回写** `messages.person_id`。T-002 / T-007 未定义该接口，T-008 不新增契约；若验收要求「改完重新分析生效」，需先补契约。
- **画像历史版本**：前端只读最新版；API 侧已支持 `?version=N`，UI 暂无版本选择器。
- **`RELATIONINSIGHT_API_BASE` 未写入 `backend/.env.example`**：前端目前仅支持环境变量覆盖（本轮未新增依赖，也未改 `.env.example`）。
- **CORS 只放行 8501**：换端口起 Streamlit 需改 `backend/main.py` 的 `ALLOWED_ORIGINS`（`ARCHITECTURE.md` §8 约定只放行本机原型）。
- **画像缓存**：缓存在 `st.session_state`（键 `profile_payload::<conversation_id>`），导入 / 分析 / 删除后由代码主动失效；若库被别处改动，需点「刷新画像」。
- **审计记会话 ID**：`deletion_audit.jsonl` 的 `scope` 是会话 ID（追溯需要，非原文）；若要求连 ID 也不记，需另行拍板。
- 沿用 T-007 遗留问题：撤回同意保留 `revoked_at` 行、删除后保留空库结构 → **均已确认（2026-09-22）维持现状**；未成年人 18 岁标准 / DeepSeek 政策 URL / `DELETE /data` 口令 → **移入 v1.1**。

### 下一步
- 建议下一任务：**T-008 验收（不属 Codex）**——把 `ACCEPTANCE.md` 逐条结论交 **WorkBuddy**（手工项）并由 **Cursor** 出具是否通过；**Codex** 只在收到缺陷票后修阻塞项。
- 阻塞项：无（集成路径已跑通；真实 DeepSeek API 未联调，属验收方可选手工项）。
- 需人工确认：① 是否补 `PATCH /messages/{id}/speaker` 契约（否则 A/B 改标记不落库）；② 画像卡片是否需要历史版本选择器；③ `ACCEPTANCE.md` 中「真实 API 冒烟」是否列为 MVP 必须项。

---

## T-008 最终验收 — 2026-09-22

### 负责工具
- **执行：WorkBuddy**（按 `ACCEPTANCE.md` 逐项操作：真实 HTTP + 真实 Streamlit 页面 + 真实 SQLite 文件）
- **判定：Cursor**（本记录只给结论与证据，**不代签**）
- **修复：Codex**（仅在收到缺陷票后修阻塞项）
- **拍板：产品负责人（人工）**——是否宣布 MVP 达标由人工签字

### 修改文件
- `HANDOFF.md`（本记录）
- **未改动**：`backend/**`、`frontend/**`、`tests/**`、`requirements.txt`、`.gitignore`、`ARCHITECTURE.md`、`PRIVACY.md`、`TASKS.md`（**代码与业务逻辑零改动**）
- **未触碰**：`ACCEPTANCE.md`（保留使用者本人尚未提交的改动，原样不动）
- **数据库**：按要求清理了 `backend/data/relationinsight.db` 中的 **1 行遗留 `consents`**（详见「前置状态修正」）；除此之外**未手工写库**，全部业务验收跑在独立临时库
- **未生成**：`backend/data/deletion_audit.jsonl`（审计文件只出现在临时目录）
- **验收证据（新增，非项目代码）**：`.workbuddy\accept-tmp\acceptance_report.txt`、`.workbuddy\accept-tmp\acceptance_results.json`、`.workbuddy\accept-tmp\shots\*.png`（14 张 UI 截图）

### 验收环境（对应 `ACCEPTANCE.md` §0）

| 项 | 填写 |
|------|------|
| 日期 | 2026-09-22 |
| 执行人 | WorkBuddy |
| 分支/提交 | **main / 0a451a7**（注意：`ACCEPTANCE.md` §0 预填的 `0351ff5` 已过期，落后 5 个提交） |
| Python 版本 | 3.12.4（`backend\.venv`） |
| 是否使用真实 DeepSeek | **否（`FakeDeepSeekClient`）**——按本次调令「禁止调用真实 DeepSeek API」 |
| 样例消息条数 | 50（正式分析）/ **70**（增量后）/ 19（样本不足）/ 63（UI 走查） |
| 结果 | **部分通过：7 个必须项中 6 通过、1 失败（必须项 5）** |

### 如何运行

```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# ── A. 本次验收口径（生产库隔离：存储与模型注入临时位置，零真实 API）──
#    等效于验收调令里的两条启动命令，只多一层 app.state 注入；加载的是未改动的 backend/main.py
$env:RI_ACCEPT_DIR = "C:\Users\17352\Desktop\RelationInsight\.workbuddy\accept-tmp"
& backend\.venv\Scripts\python.exe <注入启动器>.py     # uvicorn 127.0.0.1:8000，db/audit/llm 全指向 RI_ACCEPT_DIR
$env:RELATIONINSIGHT_API_BASE = "http://127.0.0.1:8000"
& backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py   # 127.0.0.1:8501

# ── B. 生产口径（使用者手点用，会写 backend\data\relationinsight.db）──
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# 另开终端（仓库根）
backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py
# 浏览器 http://localhost:8501

# ── C. 离线回归 ──
backend\.venv\Scripts\python.exe -m pytest tests -q
#   注意：本机沙箱会拦截 pytest 在系统 %TEMP% 下的历史临时目录回收；
#   本次把临时根改到工作区内再跑，命令见「遗留问题」第 8 条。
```

**口径说明（重要，与调令的唯一偏差）：** 调令要求「禁止修改数据库」且「测试后 `backend\data\relationinsight.db` 仍为 0 行」。为同时满足这两条，所有**写入型**验收（导入 / 同意 / 分析 / 增量 / 删除）都通过**真实 HTTP + 真实页面**跑在 `.workbuddy\accept-tmp\accept.db` 上；生产库全程只被读取，事后做过 SHA-256 逐字节比对。若要「在原库上跑一遍」，把 A 段的注入去掉即可复现，但会污染生产库。

### 测试结果

**必须项（`ACCEPTANCE.md` §1–§7）**

| 项 | 结论 | 证据要点 |
|----|------|----------|
| 1 结论可追溯（抽 10 条） | **通过** | 50 条正式分析 → 增量后 v2（70 条）。**2 条结论 × 6 条证据 = 12 组「结论→message_id→原文」全部核对通过（12/12 ≥ 10）**；每条 `message_id` 均能在 `messages` 打开原文；`evidence.quote` 与 `normalise_quote(mask_text(body))` 一致；quote 中 PII 零命中。抽样明细见 `acceptance_report.txt` |
| 2 样本量与置信度 | **通过** | 2/2 条正式结论均带 `confidence`（0.5，∈[0,1]）与 `sample_size`（25 ≥ 1）；UI 画像卡片与 `GET /profile` JSON 均可读到这两个字段 |
| 3 少于 20 条提示「样本不足」 | **通过** | 19 条 → `POST /analyze` 返回 `status=insufficient_sample`，文案逐字含「**样本不足**：当前仅有 19 条消息…」；`profile_versions` / `analyses` / `evidence` 均为 0 行（**未调用模型**）；`messages` 保留 19 条；真实页面顶部同样渲染该文案（截图 `11_sample_insufficient_top.png`） |
| 4 一键删除后无残留 | **通过** | 删除前该会话 7 表 90 行 → `DELETE /conversations/{id}?confirm=true` → 7 表全 0；`GET /profile` → 404；`VACUUM` 已执行；**库文件（含 -wal/-shm/-journal）字节级扫描**：唯一原文片段 0 命中、手机号/邮箱/银行卡 0 命中、会话 ID 0 命中；内置残留检查 `clean=true / hits=0`；删除回执与审计均不含原文。另有独立复现实验两轮（`conv-repro-01/02`）同样 0 命中。UI 侧「删除本会话」二次确认按 `disabled=True → 勾选 → False` 实测生效（截图 `12/13/14/15_*.png`） |
| 5 新增 20 条后画像版本 +1 | **失败（阻断）** | **产品路径不可达**：`POST /messages:import` 追加 20 条 → **HTTP 409 `duplicate_message_id`**（50 个 `message_id` 冲突，整批未写入）。根因见下节。**逻辑层已单独验证正确**：按 T-002 冻结的 `seq` 补写 50–69 后走真实 `/analyze` → `versions=[1,2]`、v1 的 `snapshot_json` **逐字节未改写**、`message_count` 50 → 70、既有批次未重算（`analyses=2`、`batches_skipped=1`） |
| 6 同意门闩 | **通过** | 未同意时 `POST /analyze` → **403 `no_consent`**，且 `analyses` / `profile_versions` 均 0 行（**闸门先于管道，未触模型**）；UI 侧未勾选时「提交同意」「开始分析」两个按钮 `disabled=True`，勾选后 `False`；`POST /consent` 200 落库（`granted=1 AND revoked_at IS NULL`）后分析 200 并产出 v1 |
| 7 范围与安全文案 | **通过** | UI 可见「不是心理诊断、不是人格标签、不推测对方动机/想法（不读心）、不提供操控或 PUA 建议」「不做心理诊断、不给人格标签、不推测对方想法」「只处理你主动粘贴的文本」「调用模型前对手机号/邮箱/身份证号/银行卡号做正则脱敏」「删除删不掉的部分（§2.3 三条披露）」；**不做清单**在 `PROJECT.md` §3 完整可查；`git ls-files` **无 `.env`、无 `*.db`**（根 `.gitignore` 已覆盖）；全仓正则扫 `sk-*` / `DEEPSEEK_API_KEY=<值>` **零命中**；服务实测 `127.0.0.1:8000`、`127.0.0.1:8501` LISTENING（**未绑 0.0.0.0**，该项不豁免） |

**额外检查**

| 检查 | 结论 | 证据 |
|------|------|------|
| `pytest tests -q` | **通过：121 passed**（4 个 DeprecationWarning，均为 FastAPI `on_event` / starlette testclient，非失败） | 用时 130s（临时根落在工作区磁盘，比 T-007 记录的 13.5s 慢，属环境差异） |
| 生产库未被污染 | **通过** | `backend\data\relationinsight.db` SHA-256 在「清理后 → pytest 后 → 全部验收后」三个阶段**逐字节一致**（`09CA6696…DEDEB91`）；**仍为 7 张表 0 行** |
| 未生成 `deletion_audit.jsonl` | **通过** | `backend\data\` 下只有 `relationinsight.db` 一个文件；审计文件仅存在于 `.workbuddy\accept-tmp\` 与 pytest 临时目录 |

**功能冒烟（§8）与非功能（§9）**

| ID | 结论 | 证据 |
|----|------|------|
| S2 50 条一批 | **通过** | `plan_batches(100)` → `[(0,49),(50,99)]` 2 个完整批；实例：63 条 → 2 批（50+13）、70 条 → 2 批（50+20） |
| S3 前端四块 | **通过** | 四个 tab = ① 导入预览 / ② A/B 标记 / ③ 画像卡片 / ④ 证据列表（截图 `01/08_*.png`） |
| S4 证据点击 | **通过** | ④ 展开结论可见 `message_id` / `seq` / 脱敏 `quote` / `speaker_role` 表格（截图 `06_evidence_list.png`） |
| S5 群聊/第三人 | **部分通过（需人工确认）** | `C: …` 被记为错误行「说话人标记无效：仅支持大写 A 或 B」，但**同批的 A/B 行仍照常入库**（3 条）——即三人对话会被**部分**当成两人对话摄入，没有「群聊超出 MVP 范围」的显式拦截 |
| S1 导入 + A/B 改标 | **未通过（已知）** | `PATCH /messages/{id}/speaker` **未接线**：② 页改标只改页面展示，不回写 `messages.person_id`（T-008 遗留①，未新增契约） |
| S6 无 Key | **未测** | 本次全程 Fake 客户端、零真实 API；`DeepSeekError` 的 `missing_api_key` 分支由 T-003 单测覆盖，未做真机联调 |
| §9 空文本导入 | **通过** | `text="   "` → 400 `empty_text`，文案友好 |
| §9 超大文本 | **未测** | MVP 5000 条上限属「需人工确认」项，当前实现未见上限校验 |
| §9 删除二次确认 | **通过** | 缺 `confirm` → 400 `confirmation_required`（会话级与 `DELETE /data` 均如此）；UI 侧按钮默认禁用 |

### 失败项细节（必须项 5）

**现象**

```text
POST /conversations/conv-accept-0001/messages:import
   body: {"text": "<同一会话的完整 70 条文本>"}
→ HTTP 409 {"kind":"duplicate_message_id",
            "message":"重复导入被拒绝：50 个 message_id 已存在，整批未写入
                       （ARCHITECTURE.md §6 方案 A：拒绝整批，不做部分导入）",
            "conflicts":[{"message_id":"609966b0-…","source_line":1}, … 共 50 条]}
```

**根因（读源码得出，非猜测）**

1. `backend/parser.py::parse_chat()` 的 `seq` **恒从 0 开始**、按本次输入的可解析行递增；`message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")` 因此**只由「会话 + 本条在本段文本里的序号」决定**。
2. 于是「在同一会话追加 20 条」只有两条路，**都被堵死**：
   - 只粘新 20 行 → `seq` 又从 0 起 → 与既有 0–19 的 `message_id` **必然冲突**；
   - 粘完整 70 行 → 前 50 条与库里既有 `message_id` 冲突 → 触发 §6 方案 A「**拒绝整批**」→ 一行都写不进去。
3. `backend/main.py::import_messages()` 忠实执行了 `import_chat()` 的语义，没有旁路；`frontend/app.py` 的「导入到数据库」按钮把整个文本框内容原样提交，因此**用户界面同样无法完成追加**。

**影响**

- `ACCEPTANCE.md` 必须项 5 的**通过标准无法通过产品路径验证**（只能像本次这样，在逻辑层补写 `seq` 后证明「合并/版本逻辑本身是对的」）。
- 产品卖点「持续增量更新长期画像」（`PROJECT.md` §1、§4.3）在**未接线的 UI 上实际不可达**：第二次分析永远只会看到 `batches_skipped`，用户拿不到 v2。
- 与 T-005 已记录的「余数批原地长大」叠加后更明显：即便将来能追加，尾批 `batch_index` 已存在也不会重算。

**是否需要交回 Codex 修：是（阻塞项，建议必修）**。本次**未改任何代码**（调令禁止），仅留缺陷票。可选修法（供 Codex / Cursor 决策，不在本次范围）：
- **A（推荐）**：导入端在写库前取 `MAX(seq)+1` 作为 `seq_offset`，让新批次的 `seq` 自然续号（`message_id` 随之唯一），并明确它与 §6「方案 A 拒绝整批」的边界（方案 A 退化为「同批自重复 / 与偏移后仍冲突」才拒绝）。
- **B**：`import_chat()` 增加显式 `seq_offset` 参数，由调用方（含 UI）传入；契约需 Cursor 重新冻结。
- **C（不推荐）**：改成「部分导入 + 跳过已存在行」——与已冻结的方案 A 直接冲突，且会静默吞数据。

### 遗留问题
- **上述必须项 5 阻断**（新增）。这是本次验收唯一的实质缺陷，也是唯一需要 Codex 动手的点。
- **S5 范围边界偏软**（新增）：三人及以上输入只把 `C:` 行标错，A/B 行仍入库，缺少「群聊超出 MVP 范围」的显式拒绝；建议与缺陷票一并处理或明确豁免。
- **`ACCEPTANCE.md` §0 的提交号过期**（新增）：文档写 `0351ff5`，实际 `HEAD=0a451a7`（T-005～T-008 共 5 个提交未回填）。请在签字前更新。
- **`ACCEPTANCE.md` 自身仍有未提交改动**（`git status` → ` M ACCEPTANCE.md`）：本次未触碰，签字页与 §0/§1–§7 的勾选需人工补填，建议填完再提交。
- **仓库根出现未跟踪目录 `.workbuddy/`**（新增）：本次验收的证据与 pytest 临时根都落在这里（`.workbuddy\accept-tmp\`、`.workbuddy\pytest-tmp\`）。这些不属于项目资产，建议加进根 `.gitignore`（本次未改），或由人工确认后删除 `pytest-tmp`。
- **pytest 在本机的临时目录问题**（新增）：默认 `%TEMP%\pytest-of-<user>` 的历史目录回收会触发本机沙箱的删除拦截，需把 `TEMP`/`TMP` 与 `--basetemp` 都指到工作区内再跑；这会让 121 例耗时从 ~13.5s 涨到 ~130s。
- **沿用 T-001～T-008 集成部分的全部遗留**：`PATCH /messages/{id}/speaker` 未接线、画像历史版本无 UI 选择器、`RELATIONINSIGHT_API_BASE` 未写进 `.env.example`、CORS 只放行 8501、`app.on_event` 旧式钩子（本次 pytest 仍报 DeprecationWarning）、撤回同意保留 `revoked_at` 行、删除后保留空库结构（后两条均已确认维持现状）、未成年人标准 / DeepSeek 政策 URL / `DELETE /data` 口令（已移入 v1.1）。
- **未验边界（如实列出）**：真实 DeepSeek API 端到端（含 401/429/超时行为与 `response_format` 真机效果）、超大文本上限、文件系统快照/备份/SSD 磨损层的残留、并发写 `profile_versions`。

### 前置状态修正（本次对数据库的唯一动作）

验收开始前，`backend/data/relationinsight.db` **并不是** `TASKS.md`/`HANDOFF.md` 记载的「7 张表 0 行」：

```text
conversations 0 / persons 0 / messages 0 / analyses 0 / evidence 0 / profile_versions 0
consents      1   ← conv-demo-0001, granted=1, scope=both_parties_informed, created_at 2026-09-22T09:00:13Z
```

该行时间戳（UTC 09:00:13 ≈ 本地 17:00:13）与文件 mtime 吻合，判断为**本地手工点验时在 UI 上点过「提交同意并写入 consents」**留下的（`frontend/app.py` 的默认 `conversation_id` 即 `conv-demo-0001`；对应会话主行不存在，属孤儿同意行）。按使用者明确指示用 SQL 清理：**先整库备份** → `DELETE FROM consents WHERE conversation_id = 'conv-demo-0001'`（影响 1 行）→ `VACUUM`。

- 清理前备份：`%TEMP%\ri_prod_backup_before_cleanup.db`（102400 字节，可回滚）
- 清理后：**7 张表 0 行**；库文件字节级 `conv-demo-0001` **0 命中**
- 之后直到本记录写入，生产库 SHA-256 未再变化

### 下一步
- **建议下一任务**：把「必须项 5 追加消息不可达」作为**缺陷票**交 **Codex** 修（冻结新契约前先由 **Cursor** 定 `seq` 续号口径）；修完只需重跑必须项 5 的产品路径即可，其余 6 项与 121 例回归已通过、无需重验。
- **是否宣布 MVP 达标**：**WorkBuddy 不建议直接宣布。** 理由：`ACCEPTANCE.md` 判定规则是「全部『必须』项为通过方可宣布达标」，当前 7 项中 **6 通过 / 1 失败**，不满足该条款；按项目宪章也不支持「先达标后补」。**建议交回人工拍板**，可选路径：
  1. **先修后判**（推荐）：Codex 修完必须项 5，WorkBuddy 只复验该项，再由 Cursor 判定、产品负责人签字；
  2. **豁免后判**：若人工认为「MVP 交付以单次分析可用为准、增量留到 v1.1」，则须按 `ACCEPTANCE.md` 顶部规则**书面豁免并签字（姓名/日期）**，把必须项 5 明确移入 v1.1，同时接受「长期画像增量在 UI 上不可达」这一后果。
- **阻塞项**：必须项 5（追加消息路径缺失）。
- **需人工确认**：① 是否走「先修后判」还是「豁免后判」；② S5 群聊边界是否豁免；③ `ACCEPTANCE.md` §0 提交号更新与签字页填写；④ `.workbuddy/` 是否加入 `.gitignore`；⑤ 是否允许在**生产库**上再跑一遍同口径验收（会写库）。

## T-008 缺陷修复（必须项 5：追加导入自动续号） — 2026-09-23

### 负责工具
- 主责：**Codex**（补冻结契约口径 + 修代码 + 离线回归 + 真实 HTTP 冒烟）
- 输入依据：**WorkBuddy** 的「T-008 最终验收」（7 个必须项 **6 通过 / 1 失败**，唯一失败项 = 必须项 5「追加消息后画像版本 +1」）；产品口径 = WorkBuddy 推荐的**方案 A：追加导入自动续号**
- **本轮只修缺陷、不判验收**：必须项 5 需由 **WorkBuddy** 重跑产品路径复验，结论仍由 **Cursor** 出具、产品负责人签字

### 修改文件
- `ARCHITECTURE.md`（§6 补冻结「追加导入自动续号」：`seq` 语义改为**会话内全局序号**、导入端取 `MAX(seq)+1`、先偏移后检测冲突；修订记录 0.7）
- `TASKS.md`（T-002 补 `seq` 语义与验收标准措辞；T-008 总表与明细状态改「修复完成，待 WorkBuddy 复验必须项 5」并补缺陷修复实现记录与 1 条遗留；修订记录 1.0）
- `backend/parser.py`（`parse_chat()` / `import_chat()` 新增 `seq_offset=0`，`seq` 从 `seq_offset` 起递增；非 int / 负数早失败）
- `backend/main.py`（`import_messages()` 写库前取 `SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE conversation_id = ?` 作为 `seq_offset`；导入日志加 `seq_offset`）
- `tests/test_parser.py`（+2 例；并在既有参数校验用例补 `seq_offset` 断言）
- `tests/test_import_append.py`（**新增**，2 例离线端到端：50+20 续号 → 画像 v1→v2；偏移后仍冲突仍拒绝整批）
- `HANDOFF.md`（本记录）
- **未改动**：`backend/db.py`、`backend/schema.sql`、`backend/llm/**`、`backend/pipeline/**`、`backend/privacy.py`、`frontend/**`、`requirements.txt`、`.gitignore`、`ACCEPTANCE.md`（保留 WorkBuddy 的验收证据与使用者本人改动，原样未动）
- **未动语义**：`message_id` 算法本身（仍 `uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")`）、§6 方案 A「拒绝整批」——只把**起点**从「恒 0」改为「`MAX(seq)+1`」，即**先偏移、后检测冲突**

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 1) 离线回归（零网络、零真实 API）
backend\.venv\Scripts\python.exe -m pytest tests -q
#   → 125 passed（T-008 集成时的 121 + 本轮新增 4）

# 2) 只跑本轮相关用例
backend\.venv\Scripts\python.exe -m pytest tests/test_import_append.py tests/test_parser.py -q

# 3) 产品口径起服务（会写 backend\data\relationinsight.db）
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
#   POST /conversations/{id}/messages:import   ← 追加导入已在后端自动续号
#   POST /conversations/{id}/analyze            ← 取新增尾批，画像版本 +1

# 4) 本轮真实 HTTP 冒烟的复现方式（临时库 + Fake 模型，零真实 API；脚本跑完已删）
#    启动器把 app.state.db_path / audit_path / llm_client 指到 %TEMP%\ri_t008fix\，
#    uvicorn 绑 127.0.0.1:8012；客户端用 urllib 依次调 import(50) → consent → analyze
#    → import(20) → analyze → GET profile?version=1 → GET profile
```

### 测试结果

| 用例 | 结果 | 备注 |
|------|------|------|
| 回归 `pytest tests -q` | 通过 | **`125 passed`**（121 + 4），零回归 |
| `tests/test_parser.py::test_parse_chat_with_seq_offset_continues_numbering` | 通过 | `seq_offset=50` → `seq` 50–69；与 `make_message_id(conv, 0..49)` 生成的 ID **完全不重合** |
| `tests/test_parser.py::test_appended_import_continues_seq_and_write_succeeds` | 通过 | 50 条 + `seq_offset=50` 的 20 条 → 两次都 `inserted`，库内 `messages` **70** 行、`seq` 0–69 连续、70 个唯一 ID、`persons` 仍 2 行；不带 `seq_offset` 的同类调用仍 `rejected_conflict`（证明修复点在续号而非冲突策略） |
| `tests/test_import_append.py::test_append_import_continues_seq_then_profile_version_bumps` | 通过 | 必须项 5 的**产品路径**：导入 50 → 同意 → 分析 v1 → 追加 20（HTTP 200、seq 50–69、conflicts 0）→ 再分析 → **画像 v2**（`batch_count=2` / `analyses_written=1`），v1 快照前后完全一致、`message_count=70` |
| `tests/test_import_append.py::test_conflict_after_offset_still_rejects_the_whole_batch` | 通过 | 显式压回 `seq_offset=0` → 仍 `409` / `rejected_conflict`，整批 0 行写入（方案 A 语义未被削弱） |
| 真实 HTTP 冒烟（`uvicorn 127.0.0.1:8012` + 临时库 + `FakeDeepSeekClient`） | 通过 | 导入 50（seq 0–49）→ consent → analyze（v1）→ **追加 20 → HTTP 200、seq 50–69、conflicts 0**（旧实现此处 409 `duplicate_message_id`）→ analyze（v2）→ `GET profile?version=1` sha256 未变 → `GET profile` = v2 / `message_count=70`；库内 `conversations 1 / persons 2 / messages 70 / analyses 2 / evidence 12 / profile_versions 2 / consents 1`，批次 `[(0, 0, 49), (1, 50, 69)]`，版本 `[(1, 50), (2, 70)]` |
| 生产库未被污染 | 通过 | `backend\data\relationinsight.db` 仍 **7 张表 0 行**（冒烟全程跑在 `%TEMP%` 临时库；临时脚本与临时库跑完已删） |
| 真实 DeepSeek API | **未测** | 按要求全程 `FakeDeepSeekClient`；必须项 5 的复验由 WorkBuddy 决定是否用真实 API |

### 遗留问题
- **内容级去重缺失（新增，v1.1）**：续号修复后，把**同一段文本原样再导入**不再报 `409`，而是被当作新消息续号追加（内容重复但 `seq` 合法）。MVP 接受该行为；若需要「同内容不重复入库」，需另立契约（内容哈希或显式 `mode` 参数）。
- **`PATCH /messages/{id}/speaker` 仍未接线**（沿用 T-008 集成部分遗留①）：② 页改说话人只影响页面展示，不回写 `messages.person_id`；与本次修复无关，仍待人工拍板是否补契约。
- 沿用 T-008 验收记录中的其余遗留：`ACCEPTANCE.md` §0 提交号过期、仓库根未跟踪目录 `.workbuddy/`、pytest 临时目录回收问题、画像历史版本无 UI 选择器、`RELATIONINSIGHT_API_BASE` 未入 `.env.example`、CORS 只放行 8501、`app.on_event` 旧式钩子、S5 群聊边界、超大文本上限、并发写 `profile_versions`。
- 未验边界：真实 DeepSeek API 端到端（401/429/超时 / `response_format` 真机效果）。

### 下一步
- **建议下一任务**：**WorkBuddy 复验必须项 5**——按生产口径重跑「导入 50 → 同意 → 分析 → **追加** 20 → 分析」，确认画像版本 v1 → **v2**、旧版本快照可读且未被改写；其余 6 个必须项与 121 例回归上轮已通过，无需重验。
- **阻塞项**：无（原阻塞项「必须项 5 追加消息路径缺失」已具备修复证据，等待复验）。
- **需人工确认**：① 必须项 5 复验通过后，是否走 Cursor 判定 + 产品负责人签字；② `ACCEPTANCE.md` §0 提交号与签字页更新；③ 内容级去重是否列入 v1.1；④ `.workbuddy/` 是否加进 `.gitignore`。
- **未判验收**：本轮为**缺陷修复**，Codex 不自行判定 `ACCEPTANCE.md` 通过。

## T-008 必须项 5 复验 — 2026-09-23

### 负责工具
- **执行：WorkBuddy**——按生产口径起真实 `uvicorn` + 真实 Streamlit，用**真实浏览器（系统 Chrome，Playwright 驱动）**走产品路径点完 7 步
- **判定：Cursor**（本记录只给结论与证据，**不代签**）
- **修复：Codex**——本轮结论为「通过」，**无需交回修**
- **拍板：产品负责人（人工）**——是否宣布 MVP 达标由人工签字
- 复验范围：**只验必须项 5**（其余 6 项与 121 例回归上轮已通过，按调令不重验）

### 修改文件
- `HANDOFF.md`（本记录）
- **未改动**：`backend/**`、`frontend/**`、`tests/**`、`requirements.txt`、`.gitignore`、`ARCHITECTURE.md`、`PRIVACY.md`、`TASKS.md`（**代码与业务逻辑零改动**）
- **未触碰**：`ACCEPTANCE.md`（使用者本人尚未提交的改动原样保留）
- **未污染数据**：`backend\data\relationinsight.db` 全程只读，SHA-256 在复验前后**逐字节一致**（`09CA6696…DEDEB91`）；**未生成** `backend\data\deletion_audit.jsonl`
- **复验证据（新增，非项目代码）**：`.workbuddy\accept-tmp\`（`flow_log.json`、`summary.json`、`post_check.json`、`drive_out.txt`、`pytest_out.txt`、启动器/驱动脚本、`shots_fix\*.png` 16 张浏览器截图）

### 验收环境

| 项 | 填写 |
|------|------|
| 日期 | 2026-09-23 |
| 执行人 | WorkBuddy |
| 分支/提交 | **main（本轮未取提交号；`ACCEPTANCE.md` §0 仍写 `0351ff5`，实际 `HEAD` 已前进，需人工回填）** |
| Python 版本 | 3.12.4（`backend\.venv`） |
| 是否使用真实 DeepSeek | **否（`FakeDeepSeekClient`）**——按调令「禁止调用真实 DeepSeek API」 |
| 样例消息条数 | 50（首次分析）/ **70**（追加 20 后） |
| 结果 | **必须项 5：通过**（7 个必须项至此 7/7 均有通过记录） |

### 如何运行

```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# ── A. 本轮复验口径（生产库隔离；与调令两条启动命令只差一层 app.state 注入）──
#    加载的是**未改动**的 backend/main.py；注入只把存储与模型指到临时位置：
#      db     -> .workbuddy\accept-tmp\accept_fix.db
#      audit  -> .workbuddy\accept-tmp\deletion_audit.jsonl
#      llm    -> llm.FakeDeepSeekClient()        （零真实 API）
& backend\.venv\Scripts\python.exe .workbuddy\accept-tmp\serve_backend.py   # 127.0.0.1:8000
& backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.port 8501   # 127.0.0.1:8501
# 驱动（真实 Chrome，系统已装；playwright 位于 managed venv 而非 backend\.venv）
& "C:\Users\17352\.workbuddy\binaries\python\envs\default\Scripts\python.exe" .workbuddy\accept-tmp\drive_flow.py
#   点击顺序：设会话 ID → 粘 50 条 → 导入到数据库 → 勾选同意并提交 → 开始分析 → 粘 20 条 → 导入 → 再分析
#             → 展开「删除本会话」→ 勾选二次确认 → 删除本会话

# ── B. 生产口径（使用者手点用，会写 backend\data\relationinsight.db）──
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# 另开终端（仓库根）
backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py
# 浏览器 http://localhost:8501

# ── C. 离线回归 ──
$env:TEMP="C:\Users\17352\Desktop\RelationInsight\.workbuddy\pytest-tmp"; $env:TMP=$env:TEMP
backend\.venv\Scripts\python.exe -m pytest tests -q --basetemp="$env:TEMP\bt"
#   注意：本机沙箱会拦截 pytest 对系统 %TEMP% 历史临时目录的回收，故临时根改到工作区内（耗时 ~130s）
```

**口径说明（与调令的唯一偏差）：** 调令同时要求「跑完写入型流程」与「`backend\data\relationinsight.db` 仍为 7 张表 0 行」。为两条都满足，**写入型验收全部跑在临时库**上（真实 HTTP + 真实页面 + 真实 SQLite 文件，只是文件位置在 `.workbuddy\accept-tmp\`）；生产库全程被读取、事后做过 SHA-256 逐字节比对。要去掉偏差就把 A 段的注入删掉，代价是污染生产库。

### 测试结果

**必须项 5 的 7 个步骤（一次连续的真实浏览器会话，20:54:40 → 20:55:18）**

| 步骤 | 结果 | 页面 / 库证据 |
|------|------|------|
| 1 新建会话 `conv-accept-fix-01` | 通过 | 页面「会话 ID」= `conv-accept-fix-01`；① 导入预览「可解析消息 50 条 / 错误行 0 行」 |
| 2 导入 50 条 | 通过 | 页面提示 **「已写入 50 条消息（seq 0–49）」**；库内 `conversations 1 / persons 2 / messages 50 / analyses 0 / profile_versions 0 / consents 0` |
| 3 勾选同意 → 提交 | 通过 | 未勾选时「开始分析」为禁用；勾选后提示 **「已写入 consents：2026-09-23T12:54:51Z · scope=both_parties_informed」**；`consents` 1 行 |
| 4 点分析 → v1 | 通过 | **「最近一次分析：status=completed · 批次 1 · analyses 1 行 · evidence 6 行 · 版本 v1」**；顶部「最新画像版本号 v1」「当前覆盖消息数 50 条」；画像来源切换为**后端真实画像**（脚本开头是 404 `no_profile` 回退演示数据） |
| 4′ **记录 v1 快照** | 通过 | `profile_versions` v1：`message_count=50`，`snapshot_json` **2594 字节**，**SHA-256 `1D619DF3F9A41B77B46EDDE71BFDAB41B92917CFC044F9B5C778E1BE366C0551`**（原始字符串已存 `flow_log.json`） |
| 5 追加导入 20 条 | **通过（原缺陷点）** | **页面提示「已写入 20 条消息（seq 50–69）」，HTTP 200，`conflicts` 为空——不再出现 409 `duplicate_message_id`**；库内 `messages 70`，`seq` 恰为 **0–69 连续**（70 个唯一值，`is_0_to_69=true`） |
| 6 再点分析 → v2 | 通过 | **「status=completed · 批次 2 · analyses 1 行 · evidence 6 行 · 版本 v2」**（batch 0 幂等跳过，只折入新增尾批）；顶部「最新画像版本号 v2」「当前覆盖消息数 70 条」 |
| 6′ v1 快照未被改写 | 通过 | 升到 v2 后重读 v1 `snapshot_json`：**与第 4′ 步逐字节相同**（`byte_identical=true`，SHA-256 仍为 `1D619DF3…C0551`，2594 字节）；API 复核 `GET /profile?version=1` → `version=1 / message_count=50` |
| 6″ v2 覆盖数大于 v1 | 通过 | v2 `message_count=70` **>** v1 `50`（v2 `snapshot_json` 3979 字节，SHA-256 `0577D0EE…6545E`）；`GET /profile` → `version=2 / message_count=70`；`profile_versions` 共 2 行 |
| 7 删除该会话（二次确认） | 通过 | 勾选前「删除本会话」禁用，勾选后可点；回执：**「已删除会话 conv-accept-fix-01 的本地数据（2026-09-23T12:55:14Z）：evidence 12、analyses 2、profile_versions 2、messages 70、persons 2、consents 1、conversations 1；VACUUM 已执行；残留检查通过（0 命中）」**；删除后七表该会话行数**全部 0**；`GET /profile` → **404 `no_profile`** |

**额外检查**

| 检查 | 结论 | 证据 |
|------|------|------|
| `pytest tests -q` | **通过：125 passed**（134.42s，4 个 DeprecationWarning 均为既有的 FastAPI `on_event` / starlette，非失败） | `.workbuddy\accept-tmp\pytest_out.txt` |
| 生产库未被污染 | **通过** | `backend\data\relationinsight.db` SHA-256 **`09CA6696…DEDEB91`** 在「复验前 → 复验后」**逐字节一致**；**仍 7 张表 0 行**；文件字节级扫描 `conv-accept-fix-01` / `复验第` **0 命中** |
| 未生成 `deletion_audit.jsonl` | **通过** | `backend\data\` 下只有 `relationinsight.db` 一个文件；本轮删除会话的审计行（`scope=conv-accept-fix-01`、各表行数、`vacuumed=true`、`residual_clean=true`、`note="audit only: no plaintext recorded"`）落在 `.workbuddy\accept-tmp\deletion_audit.jsonl` |
| 真实 DeepSeek API | **未测** | 按要求全程 `FakeDeepSeekClient`，零真实模型调用 |

### 复验结论

- **必须项 5：通过。** 原阻断点（同一会话追加导入 → `409 duplicate_message_id` → 产品路径上拿不到 v2）**已消失**：追加导入 20 条返回 200、`seq` 自动续号为 50–69，再分析后画像由 v1 升到 v2，且 v1 快照逐字节未被改写、v2 覆盖消息数（70）大于 v1（50）。三条通过标准（版本 +1 / 旧快照未改写 / 新版 `message_count` 更大）全部满足。
- **是否需要交回 Codex 修：否。** 本轮未发现新的阻塞缺陷，Codex 的修复（`parse_chat` / `import_chat` 新增 `seq_offset`，`import_messages()` 写库前取 `MAX(seq)+1`）在产品路径上按预期生效。
- **是否建议宣布 MVP 达标：不建议由 WorkBuddy 直接宣布。** `ACCEPTANCE.md` 的判定规则是「全部『必须』项为通过方可宣布达标」，而**判定权在 Cursor、签字权在产品负责人**。就本机可观测证据而言，7 个必须项现已 **7/7 有通过记录**（前 6 项见「T-008 最终验收」记录，第 7 项见本条），**具备进入签字流程的条件**；建议：Cursor 复核本记录并出具判定 → 人工填写 `ACCEPTANCE.md` §0（提交号已过期）与第 10 节签字页。

### 遗留问题
- **② A/B 标记的陈旧勾选值（本轮观察，非本轮范围）**：`st.selectbox` 的 widget key 是 `speaker_{message_id}`，而 `message_id = uuid5(conversation_id, seq)` 是**位置型**。在同一会话里把左侧文本整体换成另一段内容时，`seq` 重合的消息会沿用上一次该位置的选择，② 页顶部因此出现「已修改 N 条消息的说话人」提示（本轮自动化连续替换文本时稳定复现 6 条 / 4 条）。**新开页面**加载同一文本时显示「当前说话人与解析结果一致」。因 ② 本身未接线（T-008 遗留①），**不影响导入 / 同意 / 分析 / 画像 / 删除链路**，仅作观察记录；若要修，可把 widget key 换成「内容哈希」或在文本变更时清空 `speaker_*` 状态。
- **`ACCEPTANCE.md` §0 提交号过期**（沿用上轮）：文档写 `0351ff5`，实际 `HEAD` 已前进（T-005～T-008 共 5 个提交 + 本轮未取号）；签字前须更新。
- **仓库根未跟踪目录 `.workbuddy/`**（沿用上轮）：本轮证据与 pytest 临时根都落在这里，建议加进根 `.gitignore` 或人工确认后清理 `pytest-tmp`。
- **内容级去重仍缺失**（Codex 上轮已列为 v1.1）：续号修复后，同一段文本原样再导入不会报 409，而是作为新消息续号追加（内容重复但 `seq` 合法）。MVP 接受，本轮未触及。
- **pytest 本机临时目录问题**（沿用上轮）：默认 `%TEMP%\pytest-of-<user>` 回收会触发沙箱删除拦截，需把 `TEMP`/`TMP` 与 `--basetemp` 指到工作区内。
- 沿用 T-001～T-008 的其余遗留：`PATCH /messages/{id}/speaker` 未接线、画像历史版本无 UI 选择器、`RELATIONINSIGHT_API_BASE` 未入 `.env.example`、CORS 只放行 8501、`app.on_event` 旧式钩子、S5 群聊边界、超大文本上限、并发写 `profile_versions`、未成年人标准 / DeepSeek 政策 URL / `DELETE /data` 口令（已移入 v1.1）。
- **未验边界（如实列出）**：真实 DeepSeek API 端到端（401/429/超时与 `response_format` 真机效果）；本轮跑的是 `FakeDeepSeekClient`，故「v1→v2 的逻辑正确性」已验，「模型输出质量」不在本轮范围。

### 下一步
- **建议下一任务**：由 **Cursor** 依据本记录 + 「T-008 最终验收」记录，对 `ACCEPTANCE.md` 七项必须项出具**判定意见**；随后由产品负责人填写 §0 提交号与第 10 节签字页并**拍板是否宣布 MVP 达标**。
- **阻塞项**：无（必须项 5 已通过，原唯一阻塞项关闭）。
- **需人工确认**：① 是否宣布 MVP 达标（WorkBuddy 不代签）；② `ACCEPTANCE.md` §0 提交号更新与签字页填写；③ ② A/B 标记的陈旧勾选值是否需要修（及是否补 `PATCH /messages/{id}/speaker` 契约）；④ `.workbuddy/` 是否加进 `.gitignore`、`pytest-tmp` 是否清理；⑤ `ACCEPTANCE.md` 中「真实 API 冒烟」是否列为 MVP 必须项（本轮仍未做，全程 Fake）。
- **交接指向**：判定交 **Cursor**；**Codex** 本轮无待修项；**WorkBuddy** 可在人工要求下按 A 段口径复现本次复验。

---

## 项目收尾 — 2026-09-23

### 负责工具
- **执行：Codex**——本轮为**收尾回填**，**只改文档、代码零改动**（未动 `backend/**`、`frontend/**`、`tests/**`、`requirements.txt`、`.gitignore`、`ARCHITECTURE.md`、`PRIVACY.md`）
- **复验依据：WorkBuddy**——真实 `uvicorn` + 真实 Streamlit + **真实浏览器（系统 Chrome）**走完 7 步产品路径，必须项 5 通过（见上一条记录）
- **判定：Cursor**——`ACCEPTANCE.md` §10 签字行「同意通过」
- **拍板：产品负责人（人工）**——MVP 达标口径由人工签字确认；`ACCEPTANCE.md` §10 产品负责人签字行**留空，未代签**

### 修改文件
- `ACCEPTANCE.md`——§0 验收环境回填（分支/提交 `main / 396825a`、Python **3.12.4**、是否使用真实 DeepSeek「**否（Fake）**」、样例消息条数 **50（正式）/ 70（增量）/ 19（样本不足）**、结果 **通过**）；§1 抽样表补真实 `message_id`；§2–§7 七个必须项结果全部勾选 **通过** 并补证据；§5 追加「增量证据」段；§10 签字表（WorkBuddy / Cursor 两行）；修订记录 0.2
- `TASKS.md`——T-008 总表与明细「当前状态」→ **完成**；修订记录 1.1
- `HANDOFF.md`——本记录；修订记录 1.2
- **未勾选**：`ACCEPTANCE.md` §8 / §9（非 MVP 必须项，保持未动）
- **未触碰**：`.workbuddy/**`（WorkBuddy 验收证据，未跟踪，原样保留）

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 本轮为纯文档回填，无启动动作。复现 7 项验收见上一条记录
# 「T-008 必须项 5 复验」的 A 段命令（真实 uvicorn + 真实 Streamlit
# + FakeDeepSeekClient；全程零真实 API）。

# 离线回归（仓库根）
& backend\.venv\Scripts\python.exe -m pytest tests -q
```

### 测试结果
| 用例 | 结果 | 备注 |
|------|------|------|
| MVP 必须项 1–7（`ACCEPTANCE.md` §1–§7） | **通过** | **7/7**；必须项 5 由 WorkBuddy 真实浏览器复验 |
| 必须项 5：新增 20 条消息后画像版本 +1 | **通过** | 导入 50（seq 0–49）→ v1（`message_count=50`，快照 SHA-256 `1D619DF3F9A41B77B46EDDE71BFDAB41B92917CFC044F9B5C778E1BE366C0551`）→ 追加 20（HTTP 200、无 409、seq 50–69）→ v2（`message_count=70`）；**v1 快照逐字节未改** |
| `pytest tests -q`（离线回归） | 通过 | **125 passed**（T-008 修复轮 121 → `test_parser` +2 → `test_import_append` +2） |
| 真实 DeepSeek API 端到端 | **未测** | 全程 `FakeDeepSeekClient`，按要求禁止调用真实 API；列入 v1.1 |

### 收尾结论
- **三份文档回填完成**：`ACCEPTANCE.md`（§0 / §1–§7 / §10 + 修订 0.2）、`TASKS.md`（T-008 → 完成 + 修订 1.1）、`HANDOFF.md`（本记录 + 修订 1.2）。
- **MVP 正式达标**：七个必须项 **7/7 通过**，判定见 Cursor 签字、执行见 WorkBuddy 复验；原唯一阻断点（同一会话无法追加 → 拿不到 v2）已关闭，具备宣布达标的条件。
- **待人工签字**：`ACCEPTANCE.md` §10 **产品负责人**签字行留空，由使用者本人签署后口径正式生效。
- **未代签声明**：Codex 本轮只做文档回填，**未代签产品负责人**、未自行宣布达标。

### 遗留问题
**v1.1 待办清单（下一里程碑）**
- **真实 DeepSeek 联调**：401 / 429 / 5xx / 超时的真机表现、`response_format` 真机效果、真实延迟与成本、key 轮换
- **录音转写**：语音 → 文本（MVP 仅支持 `A: 正文` / `B: 正文` 纯文本）
- **微信 / QQ 导入器**：聊天记录格式适配
- **`PATCH /messages/{id}/speaker`**：② A/B 标记回写 `messages.person_id`（当前只改页面展示，且 `speaker_*` widget 位置型 key 会残留陈旧勾选值）
- **内容级去重**：同一段文本原样再导入会续号入库（内容重复但 `seq` 合法）；如需「同内容不重复」需另立契约（内容哈希或显式 `mode`）
- **未成年人标准**：18 岁口径与拦截策略
- **DeepSeek 政策 URL**：`PRIVACY.md` 中待补的政策链接
- **`DELETE /data` 口令**：设置页「清空全部本地数据」危险操作的二次确认口令

**沿用未清事项**
- 画像历史版本**无 UI 选择器**（`profile_versions` 多版本可读，前端只展示最新）
- `RELATIONINSIGHT_API_BASE` 未入 `.env.example`；CORS 只放行 `localhost:8501`
- `app.on_event` 旧式钩子（建议迁 `lifespan`）
- S5 群聊边界（>2 人）未覆盖；超大文本导入无上限保护
- 并发写 `profile_versions` 不加锁（MVP 单用户同步调用）
- `analyses` 无独立 `sample_size` 列；失败批次无续跑入口（失败即停）
- 撤回同意保留 `revoked_at` 行；删除后保留空库结构（空表可读）
- `.workbuddy/` 是否加进 `.gitignore`；pytest 本机临时目录回收问题

### 下一步
- **建议下一任务**：T-001–T-008 **全部「完成」**，MVP 无在办任务；后续按上方 v1.1 清单另开任务（建议首项：真实 DeepSeek 联调冒烟）。
- **阻塞项**：无。
- **需人工确认**：① **产品负责人签字**（`ACCEPTANCE.md` §10 已留空）；② `ACCEPTANCE.md` §0 提交号是否在签字时更新为当时 `HEAD`（现填 `main / 396825a`）；③ v1.1 优先级排序；④ 「真实 API 冒烟」是否列为 v1.1 首项。
- **交接指向**：T-001–T-008 全部关闭；后续任务按 v1.1 清单重新立单。

---

## 真实模型接入（DeepSeek 真实客户端，不再依赖 Fake）— 2026-09-23

### 负责工具
- **执行：Codex**——按调令一次做完所有代码改动（使用者无需手工改文件）
- **复核：待人工**——填 Key 后首跑真实模型是使用者本机动作（**本轮未调真实 API**）
- 范围：只动 6 个文件（见下）；`parser.py` / `llm/*` / `pipeline/*` / `privacy.py` / `frontend/**` / `tests/**`
  一律**未动**，T-001–T-008 已冻结的接口契约与响应字段均未改（唯一可见变化是 `app` 版本号 `0.8.0` → `0.9.0`）

### 修改文件
| 文件 | 改动 |
|------|------|
| `backend/main.py` | ① 顶部 `load_dotenv(Path(__file__).resolve().parent / ".env")`（放在**任何** `os.environ` 读取之前，`override=False`）；② `_resolve_client()` 改为「注入 > `DEEPSEEK_API_KEY` 非空 → `DeepSeekClient()` > 否则 `FakeDeepSeekClient()` + warning」；③ 新增只读 `GET /client-info`；④ 启动日志新增一行「LLM 客户端模式：real/fake」；⑤ 新增 `_env_api_key()` / `_client_mode()` / `_client_info()` 三个内部工具 |
| `requirements.txt` | 新增 `python-dotenv>=1.0.0,<2.0.0`（venv 已装 **1.2.3**） |
| `backend/.env` | **新增**（已被 gitignore）：占位模板，`DEEPSEEK_API_KEY=`（**留空**）、`DEEPSEEK_BASE_URL=https://api.deepseek.com`、`DEEPSEEK_MODEL=deepseek-chat` |
| `backend/.env.example` | **未改动**——已存在且已含同样三个键，按调令「已存在则保持原样」 |
| `backend/.gitignore` / 仓库根 `.gitignore` | **未改动**——两者都已含 `.env`（`git check-ignore -v backend/.env` → `backend/.gitignore:1:.env`），无需补 |
| `HANDOFF.md` | 本记录 + 修订记录 1.3 |

- **未改**：`TASKS.md` / `ACCEPTANCE.md` / `ARCHITECTURE.md` / `PRIVACY.md`（本轮授权范围外）

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 1) 填 Key（唯一的人工步骤）：backend\.env → DEEPSEEK_API_KEY=sk-你的真实Key

# 2) 起后端（`main.py` 会自动加载同目录 backend\.env）
& backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000

# 3) 看模式：real = 已接真实模型；fake = 没读到 Key
& curl.exe http://127.0.0.1:8000/client-info

# 4) 离线回归（全程 Fake，不联网）
& backend\.venv\Scripts\python.exe -m pytest tests -q
```

### 测试结果
| 用例 | 结果 | 备注 |
|------|------|------|
| `pytest tests -q` | **通过：125 passed** | 29.8s；4 个 Warning 都是既有的 `app.on_event` / starlette 弃用提示，与本次改动无关 |
| 无 Key → `_resolve_client()` | 通过 | 返回 `FakeDeepSeekClient` 并打 warning「未检测到 DEEPSEEK_API_KEY，使用 Fake 客户端（仅用于离线测试）」（只提环境变量**名**，不含值） |
| 有 Key → `_resolve_client()` | 通过 | 返回 `DeepSeekClient`；`model=deepseek-chat`、`base_url=https://api.deepseek.com`；`repr()` 不含 Key（既有实现） |
| 注入 `app.state.llm_client` 优先级 | 通过 | 即使环境里有 Key，仍用注入的 Fake：单测 / 离线演示路径**不受影响** |
| `GET /client-info`（无 Key） | 通过 | `{"mode":"fake","model":"fake","base_url":null}` |
| `GET /client-info`（有 Key） | 通过 | `{"mode":"real","model":"deepseek-chat","base_url":"https://api.deepseek.com"}` |
| `GET /client-info`（自定义 env） | 通过 | `DEEPSEEK_MODEL=deepseek-reasoner` + `DEEPSEEK_BASE_URL=.../v1/` → `{"mode":"real","model":"deepseek-reasoner","base_url":"https://api.deepseek.com/v1"}`（尾部 `/` 归一） |
| `backend/.env` 真的被加载 | 通过 | 导入 `main` 前 `os.environ` 三个键均为 `None`；导入后 `DEEPSEEK_API_KEY=""`（来自 .env 的空值）、`DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` 由 .env 填入 |
| 真实 `uvicorn` + 真实 HTTP | 通过 | 启动日志出现「**LLM 客户端模式：fake**」/「**real**」（有/无 Key 两种各跑一次）；`GET /client-info` 200；`GET /health` → `status=ok / python=3.12.4 / tables=7` |
| 日志与响应无 Key 材料 | 通过 | uvicorn 输出与 `GET /client-info` 原始响应体全文扫描 `sk-dummy` / `not-a-real-key` / `key` → **0 命中**；日志只出现模式与模型名 |
| 生产库未被本轮污染 | 通过 | `backend\data\relationinsight.db` SHA-256 `2142114A…FE3B` 在「uvicorn 起停 ×2 + 125 例回归 ×2」前后**逐字节一致**（本轮验证全部走临时库 / `app.state` 注入） |
| 真实 DeepSeek API 端到端 | **未测** | 按调令不调真实 API；只构造了 `DeepSeekClient` 对象，**未发出任何真实模型请求** |

### 遗留问题
- **真实模型首跑未验**（本轮唯一空白）：需人工在 `backend\.env` 填 Key 后跑一次「导入 → 同意 → 分析」，确认 `deepseek-chat` 真实返回能通过 §5 schema 校验；401 / 429 / 5xx / 超时与 `response_format` 的真机表现仍是 v1.1 清单首项。
- **`TASKS.md` 未增行**：本轮授权文件不含 `TASKS.md`，故未登记任务状态；建议人工补一条（如 `T-009 真实模型接入`）并写「完成」。
- **前端未显示模式**：`frontend/**` 本轮禁改，UI 上仍看不出 real / fake；人工可用 `GET /client-info` 或启动日志确认（要在 UI 顶栏显示需另立任务）。
- **生产库已含使用者本地数据**：`conversations 1 / persons 2 / messages 5 / consents 1 / analyses 0 / evidence 0 / profile_versions 0`（使用者本人手工导入，mtime `2026-09-23 21:14:46`）；本轮**未删改**该库，也**未生成** `deletion_audit.jsonl`。
- **Key 只在环境里**：`.env` 不入 Git（已用 `git check-ignore` 确认；`backend/.env.example` 仍可提交）；换机器需重新填 Key，`DEEPSEEK_BASE_URL` 指向自建网关时走同一套 env。
- **`--reload` 与多 worker 未测**：本轮只验证单进程 `uvicorn`；生产若用多 worker，`.env` 由每个进程各自加载，行为一致但未实测。

### 下一步
- **建议下一动作（人工 3 步）**：① 填 `backend\.env` 的 `DEEPSEEK_API_KEY`；② 重启后端；③ `curl http://127.0.0.1:8000/client-info` 见 `"mode":"real"` 后，导入 ≥ 20 条消息 → 勾选同意 → 点分析，看真实模型返回。
- **阻塞项**：无（代码路径已通；真实效果取决于 Key 与账户额度）。
- **需人工确认**：① 「真实模型冒烟」是否记为 v1.1 首项；② 是否在 `TASKS.md` / `ACCEPTANCE.md` 补本次接线记录；③ 是否要把当前模式显示到前端顶栏。
- **未判验收**：本轮为功能接线（非验收轮），Codex 不自判 `ACCEPTANCE.md` 通过。

## 研究模式字段贯通（analyses → merge → profile_versions → 前端）— 2026-09-23

### 负责工具
- 主责：**Codex**（改 `backend/pipeline/merge.py` + `frontend/app.py`、离线回归、真实 `uvicorn` + 真实 `frontend/app.py` 渲染自证）
- 上游：上一轮「研究模式」（`backend/pipeline/prompt.py` + `ARCHITECTURE.md` §5.1：`RELATIONINSIGHT_RESEARCH_MODE` 开关；`tendencies[]` 新增 `type` / `quote_anchors` / `counter_evidence`）——**该轮未单独立节**，在本记录里一并交代
- 触发问题：研究模式的新字段只写进了 `analyses.result_json`，**没进** `profile_versions.snapshot_json`，前端看不到。本轮把这条链路接通
- **本轮为接线（非验收轮）**：Codex 不自判 `ACCEPTANCE.md` 通过

### 修改文件
- `backend/pipeline/merge.py`
- `frontend/app.py`
- `HANDOFF.md`（本记录）
- **未改动**：`backend/pipeline/traits.py`（`fold_new_observations()` / `combine_observation()` 只认 6 个数值字段，故附加字段由 `merge.py` 自行折叠，未动 traits.py 的冲突策略）、`backend/pipeline/prompt.py`、`backend/pipeline/run.py`、`backend/pipeline/batch.py`、`backend/privacy.py`、`backend/llm/**`、`backend/main.py`、`tests/**`、`frontend/fixtures/mock_profile.json`、`ARCHITECTURE.md`
- **未改语义**：`profile_versions` 仍**只追加、绝不 UPDATE/DELETE**；`traits[].evidence[].quote`（库内脱敏 quote 前缀）与 `traits[].quote_anchors`（模型给的逐字摘录）仍是**两套来源**、互不覆盖

### 改动清单（行号 = 改后行号）

`backend/pipeline/merge.py`

| 位置 | 改动 |
|------|------|
| L56–L69（模块 docstring） | 新增「研究模式附加字段（§5.1）」小节：取值 / 折叠规则 + 「有值才写」的向后兼容承诺 |
| L165 `_as_text()` | **新增**（紧跟 `_as_int()`）：非字符串或全空白 → 空串 |
| L553 / L556 | **新增** `RESEARCH_TRAIT_FIELDS = ("type", "quote_anchors", "counter_evidence")`、`TRAIT_TYPE_LABELS = ("观察", "推断", "猜测")` |
| L559 `_observation_research_fields()` | **新增**：从单条 `tendency` 取三字段，缺哪个不带哪个键 |
| L574 `_fold_research_fields()` | **新增**：同一 `trait_key` 多批观测折叠 —— `type` / `counter_evidence` 后写覆盖（**最新批胜**），`quote_anchors` 用 `merge_unique_ids()` **合并去重**（旧的在先） |
| L599 `_research_entry_fields()` | **新增**：算条目最终字段。`previous=None`（`added` / `revised`）只看本批；否则 `type` / `counter_evidence` 取最新批、本批没给则沿用旧值，`quote_anchors` 与旧锚点合并去重 |
| L680（`_group_observations()` 里的 observation dict） | **新增** `**_observation_research_fields(tendency)`：三字段随观测进入归组结果 |
| L759（`merge_profile()` 循环内） | **新增** `research = _fold_research_fields(grouped[trait_key])` |
| L818（`revised` 分支） | **新增** `entry.update(_research_entry_fields(None, research))`——表述已改写，新条目只带本批锚点；旧锚点仍留在同一快照的 `superseded` 行 |
| L846（`added` 分支） | **新增** `entry.update(_research_entry_fields(None, research))` |
| L873（`supported` / `weakened` 分支） | **新增** `old_entry.update(_research_entry_fields(old_entry, research))` |

`frontend/app.py`

| 位置 | 改动 |
|------|------|
| L38 | **新增** `import html`（转义 `type` 标记，避免把模型输出当 HTML 注入） |
| L366 `TRAIT_TYPE_COLORS` | **新增**：观察 `#1a7f37`（绿）/ 推断 `#bf8700`（橙）/ 猜测 `#6e7781`（灰）；未知取值回落灰色 |
| L373 / L379 / L387 | **新增** `trait_type()` / `trait_quote_anchors()` / `trait_counter_evidence()`：三字段的宽松取用（字段缺失或类型不符 → 空值），**老数据不报错** |
| L393 `render_research_fields()` | **新增**：`[观察]/[推断]/[猜测]` 彩色标记（`html.escape` + `unsafe_allow_html`）、`> 原文锚点` 引用块、`counter_evidence` 灰色 `st.caption` |
| L413 `render_trait_card()` | statement 之后（L427）调用 `render_research_fields(entry)`——③ 画像卡片每张都显示；docstring 同步说明 |
| L801（③ tab 说明） | 补一句：研究模式另显示标记 / 锚点 / 反例 |
| L843（④ tab 说明） | 补一句：`quote_anchors` 为模型逐字摘录（≥ 2 条），紧随其下列出 |
| L857（④ 证据列表展开区） | **新增** `anchors = trait_quote_anchors(entry)` → `**原文锚点（quote_anchors，模型逐字摘录，N 条）**` + 逐条 `> 引用块`，与下方脱敏 quote 表格并列 |

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 1) 离线回归（零网络、零真实 API）——预期 125 passed
backend\.venv\Scripts\python.exe -m pytest tests -q

# 2) 研究模式下的产品路径（要真实结论需真实 Key）
cd backend
$env:RELATIONINSIGHT_RESEARCH_MODE = "1"     # 缺省 / 其它值 = 保守模式；切换后必须重启
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
#  另一个终端：
backend\.venv\Scripts\python.exe -m streamlit run frontend/app.py
#  → 侧栏粘贴 ≥ 20 条「A: …」「B: …」→ 导入到数据库 → 顶部勾选同意 → 分析
#  → ③ 画像卡片应出现彩色 [观察]/[推断]/[猜测] 标记、> 原文锚点引用块、counter_evidence 灰色小字
#  → ④ 证据列表展开后，除脱敏 quote 表格外还多出「原文锚点（quote_anchors…）」

# 3) 本轮用过的离线自证脚本（临时库 + ResearchFake + 真实 uvicorn:8137 + streamlit AppTest）
#    %TEMP%\verify_research_ui.py       → 打印 [6]-[10] 与 RESULT: OK
#    %TEMP%\verify_backcompat.py        → 后端不可达时回退 fixture，无标记、无异常
#    脚本与临时库都在 %TEMP%，仓库零残留
```

### 测试结果

| 用例 | 结果 | 备注 |
|------|------|------|
| 回归 `pytest tests -q` | **通过：125 passed** | 20.8s；4 个 Warning 是既有的 `app.on_event` / starlette 弃用提示，与本轮无关 |
| merge 侧：临时库 + 真实 `uvicorn` + `ResearchFake` 跑「导入 24 → 同意 → 分析（含合并）」 | 通过 | `update_profile()` 落 v1；快照 `traits[]` 两行都带 `type=推断`、`quote_anchors=['第 0 条消息内容','第 1 条消息内容']`、`counter_evidence=观察窗口很短，无法排除这是一次性情境。` |
| 折叠规则（`supported` / `weakened` / `revised`） | 通过 | `supported`：`type` / `counter_evidence` 取最新批、`quote_anchors` 合并去重、条目仍沿用同一 `entry_key`；`revised`：新条目只带本批锚点、旧锚点留在 `superseded` 行；**旧版本快照对象未被就地改写** |
| 保守模式 / 老快照结构 | 通过 | 无三字段时 `traits[]` **不多出任何键**，键序与改动前逐字节一致（上一轮已离线单测锁定，本轮复验） |
| 前端真渲染（`streamlit.testing.v1.AppTest` 跑**真实** `frontend/app.py`，画像走真实 HTTP 200） | 通过 | `[推断]` 标记命中 **2** 次（A / B 两张卡片，色值 `#bf8700`）；`> 第 0 条消息内容` 引用块命中 **4** 次（③ 卡片 2 + ④ 证据列表 2）；`counter_evidence（反例 / 不确定）：…` caption 命中 **2** 次（另 1 条命中是 ③ 的说明文案本身） |
| 向后兼容：后端不可达 → 回退离线 fixture（无三字段） | 通过 | 渲染 84 个 markdown 元素、**0** 个类型标记、**0** 个引用块、`AppTest.exception` 为空——老数据不报错，只是不显示 |
| 生产库未被污染 | 通过 | 验证全程走 `%TEMP%` 临时库 + `app.state` 注入；`backend\data\relationinsight.db` 本轮只读、未改 |
| 真实 DeepSeek API | **未测** | 按要求不调真实 API；前端渲染自证用 `FakeDeepSeekClient` 子类 `ResearchFake`（在 `default_profile()` 上补三字段） |

### 遗留问题
- **`ARCHITECTURE.md` §5.1「数据流现状（重要；接线留 v1.1）」这段已过时**：本轮已把三字段接进 `profile_versions` 与前端，该段仍写着「暂不进入 `snapshot_json`、前端也看不到……是 v1.1 任务」。本轮授权文件不含 `ARCHITECTURE.md`，**未改**——建议下一轮把该段改为「已接线（2026-09-23）」并删掉末尾那句。
- **研究模式的 `prompt.py` 轮未单独立节**：`RESEARCH_MODE` 开关、解禁版提示词与 §5.1 契约目前只在 `ARCHITECTURE.md` §5.1 与本记录里可查；若坚持「每轮一节」的惯例，可补一条。
- **前端不显示当前模式**：real / fake 仍需 `GET /client-info` 或启动日志确认；研究模式开关同理（import 时解析，切换必须重启）。
- **`quote_anchors` 未与库内 quote 交叉校验**：前者是模型逐字摘录，后者是库内策略 α 脱敏前缀；二者理论上应一致，本轮不做校验（是否校验留人工拍板）。
- **老快照不追溯补字段**：只有研究模式下**重新分析**产生的批次才带三字段；历史 `profile_versions` 行原样不动（符合 §4.6「不改写旧行」）。
- **未测边界**：三种 `type` 只实测了「推断」；「观察」「猜测」共用同一渲染分支（配色表已就位），未单独造数据验证。
- 沿用前几轮遗留：内容级去重、`PATCH /messages/{id}/speaker`、`ACCEPTANCE.md` §0 提交号、未跟踪的 `.workbuddy/`、以及 v1.1 清单（真实模型联调、录音转写、微信 / QQ 导入器、未成年人标准、DeepSeek 政策 URL、`DELETE /data` 口令）。

### 下一步
- **建议下一任务**：① 用真实 Key + `RELATIONINSIGHT_RESEARCH_MODE=1` 跑一次真实研究模式分析，确认真实模型按 §5.1 产出三字段且推测类 `confidence ≤ 0.5`；② 修 `ARCHITECTURE.md` §5.1 那句过时的「数据流现状」。
- **阻塞项**：无（链路已通；「观察 / 猜测」两种标记未造数据实测，如需证据可下一轮补）。
- **需人工确认**：① 前端是否要显示「当前模式（保守 / 研究）」徽标；② `quote_anchors` 是否要与库内 quote 做交叉校验；③ 研究模式结论是否允许出现在默认 UI（§5.1「产品边界」写明面向研究者本人）。
- **未判验收**：本轮为接线，Codex 不自判 `ACCEPTANCE.md` 通过；验收结论仍由 Cursor / WorkBuddy 出具。

---

## T-002 宽容解析器升级（多格式标记 / 连续发言合并 / 未标记兜底）— 2026-09-23

### 负责工具
- 主责：**Codex**（重写 `backend/parser.py` 解析核心、扩展 `backend/main.py::import_messages()` 回执、重写 `tests/test_parser.py`、离线回归、三份文档回填）
- 协作：**Cursor** 定格式规格（三项决策已拍板，规格落进 `ARCHITECTURE.md` §6）；**WorkBuddy** 按惯例提醒交接
- 触发问题（真实用户反馈两大痛点）：① **连续说话**——同一人连发多条被拆成多条消息；② **格式不对就理解不了**——只认 `A: ` / `B: `，真实聊天里的姓名 / 我你 / 方括号写法全进不来
- **本轮为功能升级（非验收轮）**：Codex 不自判 `ACCEPTANCE.md` 通过

### 修改文件
- `backend/parser.py`（重写解析核心：宽容标记 + 连续发言合并 + 未标记通道）
- `backend/main.py`（仅 `import_messages()`：响应新增 `unmarked_lines`、日志加 `unmarked=%d`、空批文案更新）
- `tests/test_parser.py`（13 例 → **37 例**；26 个测试函数 + 1 组 12 例参数化）
- `ARCHITECTURE.md`（§0 放宽冻结表、§6 解析规则 / 连续发言合并 / 未标记行 + 两条策略表、§9 修订 0.9）
- `TASKS.md`（顶部规格、T-002 验收口径与「放宽冻结」+ 实现记录、修订 1.2）
- `HANDOFF.md`（本记录 + 修订 1.5）
- **未改动**：`backend/db.py`、`backend/schema.sql`、`backend/pipeline/**`、`backend/llm/**`、`backend/privacy.py`、`frontend/**`、`tests/` 其它文件、`ACCEPTANCE.md`
- **未改语义**：`message_id = uuid5(NAMESPACE_URL, f"{conversation_id}:{seq}")` 与「重复导入拒绝整批」（`409 duplicate_message_id`）**逐字不变**；`messages` 表结构未变（`source_lines` **不落库**）

### 改动前后对比（用户点名的 7 个场景）

| 场景 | 改动前 | 改动后 |
|------|--------|--------|
| `A: 正文` | ✅ 识别 | ✅ 识别（另：大小写不敏感，`a:` 也可） |
| `张三: 正文` | ❌ 报错 | ✅ 识别（角色 A / B 按标记**首次出现顺序**分配） |
| `张三：正文`（全角冒号） | ❌ 报错 | ✅ 识别（中英文冒号都接受） |
| `我: 正文` | ❌ 报错 | ✅ 识别（`我` 恒为角色 A，`你` 恒为角色 B） |
| `[张三] 正文` | ❌ 报错 | ✅ 识别（`【张三】正文` 同样支持） |
| `张三连续 3 条` | 3 条独立消息 | **合并成 1 条**（`seq` 只 +1、`body` 空格连接、`source_lines=[1,2,3]`） |
| `无法识别的行` | 报错 | 归入 `unmarked`（行号 + 原因；**不报错、不阻断导入**） |
| `A:正文`（补充：冒号后 0 空格） | ❌ 报错 | ✅ 识别（冒号后 0~N 个空格都接受） |
| `A: `（补充：正文为空） | 报错 | **仍报错**（`REASON_EMPTY_BODY`；不产出消息，且不打断连续段） |
| `10:30 出发`（补充：纯数字前缀） | ❌ 报错 | 归入 `unmarked`（不误当人名） |

### 契约变化（`ARCHITECTURE.md` §6「放宽冻结」）
- `parse_chat(text, conversation_id, *, seq_offset=0, merge_consecutive=True)`：新增 `merge_consecutive` 形参；`seq_offset` 续号语义不变。
- `MessageDTO` 新增 `source_lines: list[int]`（合并前的原始行号；`source_line` 仍写**首行号**）。
- 新增 `UnmarkedLine(line_number, raw_text, reason)` 与 `ParseResult.unmarked`；`ParseResult.ok` 只看 `errors`（未标记**不算失败**）。
- 解析错误只剩一种：**有标记但正文为空**（`REASON_EMPTY_BODY`）。
- `import_chat()` 签名不变；未标记行天然不产出消息，故自动跳过。
- `POST /conversations/{id}/messages:import` 响应新增 `unmarked_lines`（每项 `line_number` + `preview` = 该行前 **50** 字符，常量 `UNMARKED_PREVIEW_CHARS`）；**日志仍只记条数**。

### 如何运行
```text
# 仓库根：C:\Users\17352\Desktop\RelationInsight
# Python：backend\.venv\Scripts\python.exe（3.12.4）

# 1) 离线回归（零网络、零真实 API）
& backend\.venv\Scripts\python.exe -m pytest tests -q        # 预期 149 passed

# 2) 只看解析器行为（不起服务、不写库）
& backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, r'backend'); from parser import parse_chat; r = parse_chat('A: hi\nA: again\nplain line without marker', 'conv-demo'); print([(m.seq, m.body, m.source_lines) for m in r.messages]); print([(u.line_number, u.reason) for u in r.unmarked])"
# 期望：[(0, 'hi again', [1, 2])]  +  未标记 [(3, ...)]

# 3) 产品路径（可选；会写 backend\data\relationinsight.db）
#    工作目录 = backend
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
#    POST http://127.0.0.1:8000/conversations/{id}/messages:import
#      → 响应新增 unmarked_lines；409 duplicate_message_id 语义不变
```

### 测试结果

| 用例 | 结果 | 备注 |
|------|------|------|
| 回归 `pytest tests -q`（仓库根） | **通过：149 passed** | 22.98s；口径：上轮基线 125 − `tests/test_parser.py` 旧 13 例 + 新 37 例 = **149**；`test_pipeline` / `test_merge` / `test_privacy` / `test_deepseek` / `test_import_append` 全部继续通过，**零回归** |
| 参数化 12 例：标记写法全覆盖 | 通过 | 集合：`A:` / `a:` / `A：` / `A:你好`（0 空格）/ `A:     你好`（多空格）/ `张三:` / `张三：` / `张三2:`（含数字）/ `li_si:`（下划线）/ `我:` + `你:` / `我：` + `你：` / `[张三] 你好` / `【张三】你好`；每例都断言归到 A / B 两人 |
| 连续发言合并（3 条张三 + 1 条李四） | 通过 | 产出 2 条；`seq=[0,1]`；`body` 空格连接；`source_lines=[[1,2,3],[4]]`、`source_line` 为首行号 |
| `merge_consecutive=False` | 通过 | 逐行一条，`seq` 连续递增 |
| 未标记行夹在中间 | 通过 | 前后 A/B 行照常产出、**不被阻断**；行号与 `reason` 正确 |
| 第三位说话人不猜 | 通过 | 归「未标记」（双人硬边界），并**打断**连续段 |
| 中英文冒号混用 / 同人换写法 | 通过 | `张三: …` + `张三：…` 仍属同一连续段 → 合并；`A:` 与 `我:` 视为同一人 |
| 纯数字前缀 `10:30 出发` | 通过 | 不误当人名 → 未标记 |
| `seq_offset` 续号 / 追加导入 | 通过 | 本轮 2 例 + `tests/test_import_append.py` 端到端（50 → 70、画像 v1 → v2）仍绿 |
| 导入接口 `unmarked_lines` | 通过 | 行号 + 前 50 字符预览；未标记行不阻断导入；无可写消息仍 `nothing_to_import` |
| 真实 DeepSeek API | **未测** | 本轮不涉及模型链路，未调真实 API |

### 遗留问题
- **前端未接（授权名单外，本轮未改）**：`frontend/app.py` ① tab 的 caption 仍写「`seq` 只对**可解析成功**的行从 0 递增」与「格式：`A: 正文` / `B: 正文`」——**口径已过时**（现为「合并后的序号 + 多格式标记」）；`unmarked_lines` 也还没展示（前端只读 `result.messages` / `result.errors`），未标记行目前在 UI 上「看不见」。
- 合并的 `body` 用**一个空格**连接：原文的换行 / 空行信息丢失；`source_lines` 只在内存与响应里，**不落库**，重启后无法回看「这条合并消息原本是哪几行」。
- 姓名规格 1–20 字符（中文 / 英文 / 数字 / 下划线）是**规格假设**：含空格 / 标点的姓名（如 `张三 李四:`）会判为未标记，尚未与真实用户样本对过。
- **单字中文 + 冒号会误判**（决策 1 规格的副作用）：`注: 请尽快回复` 这类「不是说话人的单字提示」会被当成说话人（名字允许 1–20 字符），并占用 A / B 中空闲的那一个角色——实测 `注: …` + `A: …` → **2 条消息**（`注` 拿了角色 B），而不是「1 条消息 + 1 条未标记」。若要收紧，可要求中文姓名 ≥ 2 字，或加保留字黑名单（`注` / `提示` / `系统` 等）——属规格变更，需人工拍板。
- 「不合并」开关当前只有后端形参（`merge_consecutive`），前端开关按决策 2 留到下一轮。
- 未标记行**不占 `seq`**：若用户之后手动标注这些行，需要走 `PATCH /messages/{id}/speaker`（未实现）或重新导入，序号会与前端预期不同（需下轮一并处理）。
- 沿用前几轮遗留：内容级去重、`PATCH /messages/{id}/speaker`、`quote_anchors` 与库内 quote 交叉校验、`ARCHITECTURE.md` §5.1 过时段、`.workbuddy/` 未跟踪、v1.1 清单（真实模型联调、录音转写、微信 / QQ 导入器、未成年人标准、DeepSeek 政策 URL、`DELETE /data` 口令）。

### 下一步
- **建议下一任务**：前端接线（需把 `frontend/app.py` 纳入授权名单）——① tab 展示 `unmarked_lines` 并更新 caption 口径；② 加「不合并」开关（调 `merge_consecutive=False`）；③ 未标记行手动标注（依赖 `PATCH /messages/{id}/speaker`）。
- **阻塞项**：无（解析器与导入链路已通）。
- **需人工确认**：① 合并 `body` 是否保留换行符而非空格；② 姓名标记字符集是否放宽到空格 / 标点；③ 是否需要「未标记行一键批量标注」；④ `source_lines` 是否要落库（属表结构变更）。
- **未判验收**：本轮为功能升级，Codex 不自判 `ACCEPTANCE.md` 通过；是否纳入验收由 Cursor / WorkBuddy 决定。

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1 | 2026-09-21 | 模板初稿 |
| 0.2 | 2026-09-22 | 追加 T-001 交接记录 |
| 0.3 | 2026-09-22 | T-001 记录补「更正」小节（Python 基线 / Git / message_id 决策落地）；追加 T-002、T-003 交接记录 |
| 0.4 | 2026-09-22 | 追加 T-004 交接记录；2026-09-22 拍板同步进 ARCHITECTURE.md（person_id 冻结 / conversations 建表 / response_format / 重试 / 脱敏范围） |
| 0.5 | 2026-09-22 | 追加 T-005 交接记录；T-005 轮拍板同步进 ARCHITECTURE.md（§4.5 `speaker_role` 对 `dyad.*` 确认为真实说话人 / §6 批次幂等键与追加消息不重算既有批次 / §8 证据不合法保持「丢弃 + 记录」）；TASKS.md T-005 状态改「完成」、T-004 补实现记录与遗留问题 |
| 0.6 | 2026-09-22 | 追加 T-006 交接记录；T-006 轮拍板同步进 ARCHITECTURE.md（§6 余数批「原地长大」维持现状 + UI 顶部常显当前覆盖消息数与最新画像版本号）、TASKS.md（T-005 遗留问题标「已确认」、T-006 状态改「完成」、修订记录 0.7） |
| 0.7 | 2026-09-22 | 追加 T-007 交接记录；T-007 轮拍板同步进 `ARCHITECTURE.md`（§7 删除范围＝「按会话删除为主」+ 设置页「清空全部本地数据」危险操作与二次确认；§4.7 同意文案严格按 `PRIVACY.md` §1.3 落地、不自行发挥）；`TASKS.md` T-007 状态改「完成」并补实现记录与遗留问题、修订记录 0.8 |
| 0.8 | 2026-09-22 | 追加 T-008（集成部分）交接记录：`backend/main.py` 新增 `messages:import` / `profile` 接口与 CORS(8501)、`frontend/app.py` 改读真实画像并接线导入与刷新、端到端自测（真实 uvicorn + 真实 Streamlit 页面 + `FakeDeepSeekClient`，零真实 API）；`TASKS.md` T-008 状态改「集成完成，待 WorkBuddy 验收」、T-007 遗留问题 ①② 标「已确认」、未成年人标准 / DeepSeek URL / 口令移入 v1.1、修订记录 0.9；**未判 `ACCEPTANCE.md` 通过** |
| 0.9 | 2026-09-22 | 追加 **T-008 最终验收**记录（WorkBuddy 执行）：7 个必须项 **6 通过 / 1 失败**；发现「同一会话无法追加消息 → 必须项 5 阻断」（`/messages:import` 409 `duplicate_message_id`，根因 `parse_chat` 的 `seq` 恒从 0 起 + §6 方案 A 拒绝整批），建议交回 Codex 修；`pytest tests -q` → 121 passed；生产库经清理后 7 表 0 行且 SHA-256 全程未变；未生成 `deletion_audit.jsonl`；**未代签、不自行宣布 MVP 达标**，交人工拍板 |
| 1.0 | 2026-09-23 | 追加 **T-008 缺陷修复**交接记录（Codex）：必须项 5 根因＝`parse_chat()` 的 `seq` 恒从 0 起 → 追加导入必冲突 → 方案 A 拒绝整批；修法＝`parse_chat` / `import_chat` 新增 `seq_offset`，`import_messages()` 写库前取 `MAX(seq)+1`（先偏移后检测冲突，算法与方案 A 语义不变）；`ARCHITECTURE.md` §6 补冻结「追加导入自动续号」、`TASKS.md` T-002 补 `seq` 语义且 T-008 状态改「修复完成，待 WorkBuddy 复验必须项 5」；新增 `tests/test_import_append.py` + `tests/test_parser.py` 2 例 → `pytest tests -q` **125 passed**，真实 HTTP 冒烟验证 50 → v1 → 追加 20 → v2；生产库仍 7 表 0 行；**未判验收** |
| 1.1 | 2026-09-23 | 追加 **T-008 必须项 5 复验**记录（WorkBuddy 执行）：真实 uvicorn + 真实 Streamlit + **真实浏览器（系统 Chrome）**走完 7 步产品路径 → **通过**。导入 50（seq 0–49）→ 同意 → 分析得 v1（`message_count=50`，快照 SHA-256 `1D619DF3…C0551`）→ **追加 20 条 HTTP 200、无 409、seq 50–69** → 再分析得 v2（批次 2、只折入新尾批、`message_count=70`），v1 快照**逐字节未改写**、70 > 50；删除会话后七表回 0、`GET /profile` 404。额外：`pytest tests -q` **125 passed**；生产库 SHA-256 `09CA6696…DEDEB91` 逐字节未变、仍 7 表 0 行；`backend\data\` 未生成 `deletion_audit.jsonl`。**结论：通过，无需交回 Codex；不代签，建议交 Cursor 判定 + 人工拍板是否宣布 MVP 达标** |
| 1.2 | 2026-09-23 | 追加 **项目收尾**交接记录（Codex，代码零改动）：必须项 5 复验通过、7 个必须项 **7/7**；三份文档回填（`ACCEPTANCE.md` §0/§1–§7/§10 + 修订 0.2、`TASKS.md` T-008 → 完成 + 修订 1.1、`HANDOFF.md` 本记录）；**MVP 正式达标**（待产品负责人签字，未代签）；移交 v1.1 遗留清单（真实 DeepSeek 联调、录音转写、微信/QQ 导入器、`PATCH /messages/{id}/speaker`、内容级去重、未成年人标准、DeepSeek 政策 URL、`DELETE /data` 口令）|
| 1.3 | 2026-09-23 | 追加 **真实模型接入**交接记录（Codex）：`backend/main.py` 加载 `backend/.env` + `_resolve_client()` 改为「注入 > `DEEPSEEK_API_KEY` 非空 → 真实 `DeepSeekClient` > 否则 Fake + warning」+ 新增只读 `GET /client-info` + 启动打一行「LLM 客户端模式：real/fake」；`requirements.txt` 加 `python-dotenv`（venv 装 1.2.3）；新增 `backend/.env` 占位（Key 留空），`.env.example` / 两个 `.gitignore` 按调令未改。验证：`pytest tests -q` **125 passed**；无 Key→fake、有 Key→real、注入优先、自定义 model/base_url 透传均已验；真实 `uvicorn` + HTTP 通过且日志/响应无 Key 材料；生产库 SHA-256 `2142114A…FE3B` 逐字节未变。**未调真实 API**，真实模型首跑待人工填 Key |
| 1.4 | 2026-09-23 | 追加 **研究模式字段贯通** 交接记录（Codex）：`backend/pipeline/merge.py` 新增 `_as_text` / `RESEARCH_TRAIT_FIELDS` / `_observation_research_fields` / `_fold_research_fields` / `_research_entry_fields`，并把 `type` / `quote_anchors` / `counter_evidence` 写进 `profile_versions.snapshot_json`（`added` / `revised` 只看本批；`supported` / `weakened` 的 `type` / `counter_evidence` 取最新批、锚点合并去重；有值才写，保守模式与老快照结构不变）；`frontend/app.py` 新增 三字段取用与渲染（`[观察]/[推断]/[猜测]` 彩色标记 + `> 原文锚点` 引用块 + `counter_evidence` 灰色小字），③ 卡片与 ④ 证据列表都可见、老 fixture 不报错；回归 125 passed；真实 uvicorn + 真实 AppTest 渲染自证通过（标记 2 / 锚点 4 / 反例 2）；遗留：`ARCHITECTURE.md` §5.1「数据流现状」段已过时（本轮授权不含该文件，未改） |
| 1.5 | 2026-09-23 | 追加 **T-002 宽容解析器升级** 交接记录（Codex）：`backend/parser.py` 重写解析核心（五级标记识别 / 中英文冒号 / 冒号后 0~N 空格 / 连续发言**默认合并** + `source_lines` / `ParseResult.unmarked` 未标记兜底，解析错误只余「有标记但正文为空」），`backend/main.py::import_messages()` 响应新增 `unmarked_lines`（行号 + 前 50 字符，**不阻断导入**），`tests/test_parser.py` 13 → 37 例 → `pytest tests -q` **149 passed**；`ARCHITECTURE.md` §0/§6/§9（修订 0.9）、`TASKS.md` 顶部规格 + T-002 明细与修订 1.2 同步；`message_id` 算法与「重复导入拒绝整批」语义**逐字不变**；遗留：前端口径未同步、`source_lines` 不落库 |
