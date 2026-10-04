# AgentRadar 项目复盘

> 面向程序员的多 agent 行情顾问:实时追踪 AI agent 领域趋势/就业/行业动态,基于用户画像给出个性化学习方向。
> 从零到生产级,16 轮迭代,114 个测试全绿。

## 一、项目概览

| | |
|---|---|
| 定位 | 对话式 AI agent(多 agent 路由架构) |
| 技术栈 | Python 3.13 / 智谱 GLM-4 + DeepSeek / FastAPI / SQLite / SSE |
| 交互入口 | CLI REPL / Web UI(流式)/ 周报邮件 / 路由评估 |
| 核心能力 | 多 agent 路由 · RAG 双形态 · 流式输出 · 自动容错 · 双层 Evals |
| 测试 | **114 passed**(全 mock,不联网) |
| 路由准确率 | **18/18 (100%)**(真实 LLM 实测) |
| 回答质量 | **3/4 (75%)**(LLM-as-judge,降级态) |

## 二、架构演进(16 轮)

```
R1  MVP:     单 agent ReAct + 5 工具 + SQLite 画像/记忆
R2  Phase2:  + 四维度输出模板(就业卡/行业简报/学习清单)
R3  Fallback:+ ResilientClient(GLM→DeepSeek 会话级兜底)
R4  清单:    + learning 专家「本周可执行清单」模板
R5  多agent: + Orchestrator 路由 + 5 维度专家(共享工具/客户端)
R6  周报:    + generate_brief(3 专家拼报告)+ SMTP 邮件
R7  Web:     + FastAPI + 单页 HTML(build_app 依赖注入)
R8  加载:    + 思考中提示 + try/catch + 按钮防重复(感知性能)
R9  流式:    + stream()/run_stream() 全链路 SSE(逐字输出)
R10 Evals:   + 路由评估(18 题固定集 + 确定性打分)
R11 RAG①:   + 语义记忆(embedding + 余弦 top-k 检索)
R12 RAG②:   + 文档知识库(标题切块 + search_docs 工具)
R13 加固:    + 注入防护声明 + tokens 可见化(usage 链路)
R14 EDD:    + eval 实跑→GBK 崩溃修复→100%(fallback 真实验证)
R15 质量E:  + LLM-as-judge(严格标准 + 逐条 PASS/FAIL)
R16 分层:   + route_client(便宜模型路由,强模型专家)
```

**演进主线**:能跑(ReAct)→ 能用(四维度)→ 能看(Web/流式)→ 能信任(Evals/容错)→ 能记(RAG)→ 能省(分层)

## 三、核心架构决策

| 决策 | 选择 | 备选 | 理由 |
|---|---|---|---|
| Agent 框架 | 自建 ReAct 循环 | LangChain/AutoGen | 学习价值最大;看得见每一步;可控性强 |
| 多 agent 策略 | 路由式(1 问→1 专家) | 并行协作 | MVP 够用;token 成本低;后续可演进 |
| 专家实现 | 共享 AgentLoop,仅 prompt 不同 | 每专家独立类 | 复用不重写;加维度只改 prompt |
| 联网搜索 | GLM 内置 web_search | 外接搜索 API | 零额外 key;国产直连;DeepSeek 无此能力(已知降级) |
| 流式方案 | SSE(FastAPI StreamingResponse) | WebSocket | 单向推送够用;实现简单;浏览器原生支持 |
| 容错设计 | 包装器(ResilientClient),loop 零改动 | loop 内置双客户端 | 隔离性好;可单独测试;符合开闭原则 |
| RAG 存储 | SQLite + JSON 向量列 + 纯 Python 余弦 | numpy/faiss/向量库 | 记忆条数小;零新依赖;够用 |
| Chunking | 按标题切,不合并 | 固定大小滑窗/合并小节 | 标题是语义边界;TDD 测试抓过合并 bug 后修正 |
| 质量评估 | LLM-as-judge,严格 prompt | 人工抽检 | 可重复;便宜;严格措辞防 leniency bias |
| 模型分层 | route_client 配置驱动 | 硬编码双模型 | 可开关;不改代码就能切换 |

## 四、量化成果

| 指标 | 数值 | 说明 |
|---|---|---|
| 测试总数 | 114 | 全 mock,不联网,CI 可跑 |
| 路由准确率 | 100% (18/18) | DeepSeek 实测,5 维度全覆盖 |
| 回答质量 | 75% (3/4) | LLM-judge,DeepSeek 降级态(GLM 在线时应更高) |
| Git 提交 | ~60 | 每 task 一提交,16 个 feature 分支全部合并删除 |
| 设计文档 | 10 specs + 9 plans | brainstorm→spec→plan→TDD→review 完整流程 |
| 真实验证 | fallback ✅ / 流式 ✅ / evals ✅ / 个性化 ✅ | GLM 余额不足时 DeepSeek 自动接管 |

## 五、关键踩坑与修复

| # | 坑 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| 1 | GLM 429 余额不足崩 REPL | 无容错 | ResilientClient 会话级 fallback | 设计每层都要有降级路径 |
| 2 | `.env.example` 被填真实 key | 模板误用 | 恢复模板;key 只进 .env(gitignore) | 模板永不放真密钥 |
| 3 | venv 缺 sniffio | zhipuai 间接依赖未声明 | 补装 + 写进 requirements | 依赖要显式声明 |
| 4 | `pytest \| tail` 吞退出码 | 管道返回 tail 的退出码 | pytest 直接放 && 链 | CI 脚本经典坑 |
| 5 | 测试 fake 依赖被测数据 | `_perfect_route` 去 EVAL_CASES 查答案 | fake 改为独立 mapping | fake 要自包含 |
| 6 | chunking 设计自相矛盾 | plan 写"合并"但测试期望"分开" | TDD 抓住→按语义边界修正 | 测试逼你想清楚设计 |
| 7 | Web UI「没反应」 | agent 慢(30-90s) + 无加载提示 | 思考中提示 + 按钮禁用 + try/catch | 感知性能 > 实际速度 |
| 8 | `ChatResponse` 漏 content ×2 | 必填字段在工具轮恒 None | 给默认值 None(防呆设计) | 同错两次 = API 缺陷 |
| 9 | Windows GBK 控制台 UnicodeEncodeError | emoji ⚠️ 不在 GBK 字符集 | 入口统一 `reconfigure(encoding="utf-8")` | Windows Python 经典坑 |

## 六、技术能力清单

| 领域 | 具体技能 | 代码位置 |
|---|---|---|
| Agent 核心 | ReAct 循环、function calling、多 agent 路由 | `agent/loop.py`, `orchestrator.py` |
| RAG | embedding、余弦相似、语义记忆、文档 chunking | `store/memory.py`, `store/kb.py` |
| 生产化 | 容错(fallback)、流式(SSE)、降级设计 | `client.py`, `web.py` |
| 评估 | 路由 evals、LLM-as-judge、eval 驱动开发 | `evals.py`, `eval_quality.py` |
| Web | FastAPI 依赖注入、SSE、前端流式渲染 | `web.py` |
| 工程 | TDD、增量式重构、系统化调试、配置驱动 | 全项目 |
| 安全 | prompt injection 防护(声明隔离) | `loop.py`, `experts.py` |
| 成本 | token 可见化、模型分层 | `client.py`, `orchestrator.py` |

## 七、面试叙事(一分钟版)

"我从零构建了一个多 agent 系统:Orchestrator 用轻量模型分类用户问题,路由给 5 个维度专家(趋势/就业/行业/学习/通用),每个专家是共享 ReAct 循环 + 专属 prompt。支持 RAG 双形态——对话记忆语义检索和文档知识库——以及 SSE 流式输出和 GLM→DeepSeek 自动容错。用 114 个测试(全 mock)保障代码质量,用双层 Evals(路由 100% + LLM-as-judge 质量)保障效果,真实环境验证过 fallback 在 GLM 余额不足时自动切换。整个项目走了 16 轮 TDD 迭代,每轮都有设计文档、实现计划和独立分支。"

---

*项目代码:`D:\develop-project\dr-project\ai_test\ai_agent` · 学习地图:`docs/learning-map.md`*
