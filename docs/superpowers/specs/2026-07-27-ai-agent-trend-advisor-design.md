# AI Agent 行情与学习方向顾问 (AgentRadar) — 设计文档

- 日期: 2026-07-27
- 状态: Approved (MVP scope)
- 代号: AgentRadar

## 1. 背景与目标

构建一个**对话式 AI agent**,面向想入行或转型 "AI agent" 方向的程序员。它实时联网调研程序员 / AI agent 领域的行情与趋势,并为用户建立长期画像,给出**强个性化**的学习方向建议。

核心价值:把"散落在招聘站、GitHub、科技媒体、社区里的信号"实时聚合并解读,省去用户手动搜集;并基于个人背景给出可执行的学习路径。

## 2. 目标用户

- 程序员(后端 / 前端 / 算法 / 学生),想转入或深化 AI agent 方向
- 不擅长持续追踪行业动态,希望"问一句就有结论 + 出处"
- 需要个性化:不同背景的人学习路径不同

## 3. 范围

### MVP(本次实现)
- 对话式交互(CLI 优先)
- 实时联网搜索(Web Search API)
- 覆盖两个维度:**技术生态趋势** + **学习资源/路径**
- 用户画像采集与长期存储(技能栈 / 岗位 / 目标)
- 对话记忆(短期会话历史)
- 强个性化学习路径生成(基于画像)
- 回答附引用来源

### 后续阶段(本次不实现,仅留扩展点)
- Phase 2: 就业市场行情 + 行业应用动态维度
- Phase 3: 多 agent 协作(Orchestrator + 维度专家)、定时简报推送、Web UI

## 4. 整体架构

方案 A(单 Agent + 多工具,原生 SDK 自建循环),预留多 agent 扩展点。

```
用户 (CLI)
   │  自然语言提问
   ▼
Agent Loop (自建 ReAct 循环)
   │  感知 → 决策(选工具) → 执行 → 观察 → ... → 最终回答
   ├──► Tools:
   │      • web_search        实时联网搜索
   │      • github_stats      GitHub 仓库 star/趋势 (API)
   │      • read_profile      读用户画像
   │      • update_profile    写/更新画像
   │      • read_memory       读近期对话记忆
   │      • write_memory      写记忆
   ├──► Model: GLM-4 (智谱), function calling
   └──► 回答 + 引用来源
```

**设计原则:** 每个组件单一职责、接口清晰、可独立测试。Agent Loop、Tools、存储、模型客户端、数据层分层;新增工具或维度只改注册表,不动核心循环。

## 5. 核心组件

### 5.1 Agent Loop (`agent_radar/agent/loop.py`)
- 自建 ReAct 风格循环:读取用户输入 + 上下文 → 调模型 → 若模型请求工具则执行工具、把结果喂回 → 直到模型给出最终回答
- 最大迭代轮数限制(防死循环)、超时、错误兜底
- 接口:`run(user_message: str) -> Answer`(Answer 含正文 + 引用 + 使用过的工具)

### 5.2 Tools (`agent_radar/agent/tools/*.py`)
每个工具 = 一个符合统一 schema 的函数(function calling 描述符 + 执行函数)。
- `web_search(query)`: 调 Web Search API,返回结果列表(title / url / snippet)
- `github_stats(repo)`: 调 GitHub API,返回 star / fork / 近期增长
- `read_profile()` / `update_profile(fields)`: 读写用户画像
- `read_memory(n)` / `write_memory(item)`: 读写近期记忆

工具注册表(`ToolRegistry`),新增工具只改注册表。

### 5.3 用户画像存储 (`agent_radar/store/profile.py`)
- 本地 SQLite(单用户;表 `profile`:技能栈、当前岗位、经验年限、目标方向、偏好,以 JSON 字段存储)
- 首次使用引导采集;后续 `update_profile` 增量更新
- 接口:load / save / patch

### 5.4 对话记忆 (`agent_radar/store/memory.py`)
- SQLite 表 `memory`:近期对话要点(摘要),供 `read_memory` 检索
- 短期:当前会话上下文窗口;长期向量化检索留待 Phase 3

### 5.5 搜索 / 数据层 (`agent_radar/data/search_client.py`, `agent_radar/data/github_client.py`)
- 封装外部 API 调用、重试、限流、错误处理
- 抽象接口,便于切换搜索提供商(博查 Bocha / 智谱 web_search / Tavily)

### 5.6 模型客户端 (`agent_radar/llm/client.py`)
- 封装智谱 GLM 调用,支持 function calling
- 配置驱动可切换 DeepSeek

### 5.7 交互层 (`agent_radar/cli.py`)
- REPL 风格 CLI,分块输出,**显示工具调用过程**(透明、利于学习)
- 首次启动触发画像引导

## 6. 典型数据流

用户:"我现在是 Java 后端 3 年,想转 AI agent,现在该重点学什么?"

1. CLI 接收 → Agent Loop
2. Loop 调模型;模型决策:先 `read_profile`
3. 若画像缺失 → `update_profile` 存入"Java 后端 3 年,目标 AI agent"
4. 模型决策:`web_search("AI agent framework trend 2026")` + `github_stats(若干热门仓库)`
5. 工具返回结果 → 喂回模型
6. 模型综合:趋势 + 用户画像 → 生成个性化学习路径(分阶段、附资源链接)
7. Answer 返回 CLI,带引用

## 7. 数据来源与可行性约束

| 维度 | 来源 | 可行性 |
|---|---|---|
| 技术生态趋势 | GitHub API(star / 趋势)、HuggingFace、PyPI、Web 搜索 | ✅ 可靠 |
| 学习资源路径 | Web 搜索 + awesome 列表聚合 | ✅ 可靠 |
| 行业动态(后续) | Web 搜索(科技媒体) | 🟡 中 |
| 就业行情(后续) | Web 搜索近似片段 | ⚠️ 定性,无精确数字 |

约束:
- **不硬爬** BOSS直聘 / 拉勾(反爬 + 法律风险),就业数据仅做定性分析并明确标注"近似"
- 搜索 API 有成本与限流,需缓存 + 限流
- 实时性 = 每次对话联网查询(MVP 不预抓取建库、不引入向量库)

## 8. 技术栈

- 语言:Python 3.11+
- 模型:智谱 GLM-4(function calling),DeepSeek 备选
- 搜索:博查 Bocha / 智谱 web_search / Tavily(配置切换)
- 存储:SQLite(画像 + 记忆),标准库即可
- 依赖管理:`uv`(优先)或 `pip` + `requirements.txt`
- 测试:pytest
- 配置:`.env`(API keys)+ `config.py`

## 9. 错误处理与降级

- 网络 / API 失败:重试(指数退避)→ 降级为"提示数据源暂不可用"
- 模型 function calling 异常:捕获、最多 N 轮、超出则用最后已知结果回答
- 搜索无结果:明确告知 + 建议换关键词
- API key 缺失:启动时校验,缺则提示如何配置

## 10. 测试策略

- 工具层:单元测试(mock 外部 API,验证输入输出 schema)
- Agent Loop:用 mock 模型(预设工具调用序列)验证循环逻辑、迭代上限、错误兜底
- 存储层:SQLite 临时库测试画像 / 记忆读写
- 集成:可选,真实模型跑固定 query(需 API key,标记为 slow / integration)
- 目标:核心逻辑(工具、loop、存储)高覆盖;真实 API 调用隔离为可选集成测试

## 11. 分阶段路线图

- **Phase 1 (MVP, 本次):** Agent Loop + `web_search` + `github_stats` + 画像 + 记忆 + CLI,覆盖「技术生态趋势 + 学习路径」
- Phase 2: 加「就业 + 行业」维度(更多数据源适配)
- Phase 3: 多 agent 编排 + 定时简报 + Web UI

## 12. 开放决策(本次用默认值锁定,可改)

1. 招聘数据 → **默认:定性近似,不硬爬**
2. 架构 → **默认:方案 A(单 agent),预留多 agent 扩展点**
3. MVP 范围 → **默认:先做「技术生态趋势 + 学习路径」**

## 13. 目录结构(MVP)

```
ai_agent/
├── docs/superpowers/specs/         # 设计文档
├── agent_radar/
│   ├── __init__.py
│   ├── cli.py                      # 交互层 REPL
│   ├── config.py                   # 配置加载(.env)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py                 # Agent ReAct 循环
│   │   ├── registry.py             # 工具注册表
│   │   └── tools/                  # 各工具
│   │       ├── web_search.py
│   │       ├── github_stats.py
│   │       ├── profile.py
│   │       └── memory.py
│   ├── llm/
│   │   └── client.py               # GLM / DeepSeek 客户端
│   ├── data/
│   │   ├── search_client.py        # 搜索 API 封装
│   │   └── github_client.py        # GitHub API 封装
│   └── store/
│       ├── db.py                   # SQLite 连接/建表
│       ├── profile.py              # 画像读写
│       └── memory.py               # 记忆读写
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```
