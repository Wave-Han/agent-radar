# AgentRadar

![CI](https://github.com/Wave-Han/agent-radar/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-120%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

对话式 AI agent:实时追踪 AI agent 领域的**行情与趋势**(技术生态 / 就业 / 行业动态),并基于你的个人画像给出**强个性化学习方向**建议。

## 能力(多 agent 架构)

`Orchestrator` 自动识别问题维度,路由给对应的**维度专家**:
- **技术趋势专家** — 框架 / 模型 / 方向热度(`web_search` + `github_stats`)
- **就业行情专家** — 岗位 / 薪资(定性近似)/ 技能 / 城市 / 趋势 → 就业行情卡
- **行业动态专家** — 融资 / 新品 / 开源动向 / 趋势 → 行业动态简报
- **学习方向专家** — 基于画像的分阶段学习路径
- **通用专家** — 综合问题 / 兜底

其他:
- 用户画像 + 对话记忆(SQLite 持久化)
- **自动容错** — GLM 失败时自动切换 DeepSeek 兜底(见下)

## 安装

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash;cmd 用 .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # 填入 ZHIPU_API_KEY
```

## 运行

```bash
python -m agent_radar.cli
```
首次运行会引导填写背景;之后直接提问(Orchestrator 自动路由到对应专家),例如:
- "现在做 AI agent,LangChain 和 AutoGen 哪个更值得学?" → 趋势专家
- "AI agent 相关岗位现在就业行情怎么样?" → 就业专家
- "最近 AI agent 行业有什么值得注意的动态?" → 行业专家
- "我是 Java 后端 3 年,想转 AI agent,给我一条学习路径。" → 学习专家

输入 `/profile` 查看画像,Ctrl+C 退出。

## Web UI(可选)

```bash
python -m agent_radar.web
```
浏览器打开 http://127.0.0.1:8000 — 网页聊天 + 一键「生成周报」(配置同 `.env`)。

## 模型与容错(可选)

- 默认用**智谱 GLM**(内置联网 `web_search`,推荐)。
- 在 `.env` 配置 `DEEPSEEK_API_KEY` 后,GLM 调用失败(429 / 余额 / 网络)会**自动切换 DeepSeek** 兜底,会话内继续;DeepSeek 无联网搜索(降级),但工具仍可用。

## 测试

```bash
python -m pytest -v
```

## 架构

多 agent(`Orchestrator` 路由 + 维度专家):

```
用户 (CLI) → Orchestrator.route(轻量 LLM 分类维度)
           → 维度专家 AgentLoop(专属 system_prompt)
           → ResilientClient → 模型 (GLM 主,DeepSeek 兜底)
              ↘ tools: github_stats / read_profile / update_profile / read_memory / write_memory
```

- `agent_radar/agent/orchestrator.py` — 路由分类 + 调度专家
- `agent_radar/agent/experts.py` — 5 维度专家 prompt
- `agent_radar/agent/loop.py` — ReAct 循环 + SYSTEM_PROMPT + 输出模板
- `agent_radar/agent/tools/` — 各工具(SPEC 描述符 + 工厂)
- `agent_radar/llm/client.py` — GLM / DeepSeek 客户端 + ResilientClient(自动兜底)
- `agent_radar/store/` — SQLite 画像与记忆
- `agent_radar/cli.py` — 接线与 REPL

设计与实现文档见 `docs/superpowers/`。
