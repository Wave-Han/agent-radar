# AgentRadar

对话式 AI agent:实时追踪 AI agent 领域行情与趋势,并基于你的个人画像给出学习方向建议。

## 能力(MVP)
- 实时联网搜索(智谱 GLM 内置 `web_search`)
- GitHub 仓库热度查询(`github_stats` 工具)
- 用户画像 + 对话记忆(SQLite 持久化)
- 强个性化学习路径建议

## 安装
```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; cmd 用 .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # 填入 ZHIPU_API_KEY
```

## 运行
```bash
python -m agent_radar.cli
```
首次运行会引导填写背景;之后直接提问,例如:
- "现在做 AI agent,LangChain 和 AutoGen 哪个更值得学?"
- "我是 Java 后端 3 年,想转 AI agent,给我一条学习路径。"

输入 `/profile` 查看已记录的画像,Ctrl+C 退出。

## 测试
```bash
python -m pytest -v
```

## 架构
单 agent + 多工具(自建 ReAct 循环):

```
用户 (CLI) → AgentLoop → 模型 (GLM-4 + 内置 web_search)
                          ↘ tools: github_stats / read_profile / update_profile
                                    / read_memory / write_memory
```

- `agent_radar/agent/loop.py` — ReAct 循环 + SYSTEM_PROMPT
- `agent_radar/agent/tools/` — 各工具(SPEC 描述符 + 工厂)
- `agent_radar/llm/client.py` — 智谱 GLM 客户端(含 tool-call 解析)
- `agent_radar/store/` — SQLite 画像与记忆
- `agent_radar/cli.py` — 接线与 REPL

设计文档与实现计划见 `docs/superpowers/`。
