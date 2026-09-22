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
