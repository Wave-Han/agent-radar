# AgentRadar

对话式 AI agent:实时追踪 AI agent 领域的**行情与趋势**(技术生态 / 就业 / 行业动态),并基于你的个人画像给出**强个性化学习方向**建议。

## 能力

覆盖四个维度(自动识别问题类型,套对应输出格式):
- **技术生态趋势** — 框架 / 模型 / 方向热度(GLM 内置 `web_search` + `github_stats` 工具)
- **就业行情** — 岗位 / 薪资(定性近似)/ 核心技能 / 城市 / 趋势 → 就业行情卡
- **行业动态** — 融资 / 新品 / 开源动向 / 趋势判断 → 行业动态简报
- **学习方向**(个性化) — 基于画像的分阶段学习路径

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
首次运行会引导填写背景;之后直接提问(自动识别维度),例如:
- "现在做 AI agent,LangChain 和 AutoGen 哪个更值得学?"
- "我是 Java 后端 3 年,想转 AI agent,给我一条学习路径。"
- "AI agent 相关岗位现在就业行情怎么样?"
- "最近 AI agent 行业有什么值得注意的动态?"

输入 `/profile` 查看画像,Ctrl+C 退出。

## 模型与容错(可选)

- 默认用**智谱 GLM**(内置联网 `web_search`,推荐)。
- 在 `.env` 配置 `DEEPSEEK_API_KEY` 后,GLM 调用失败(429 / 余额 / 网络)会**自动切换 DeepSeek** 兜底,会话内继续;DeepSeek 无联网搜索(降级),但工具仍可用。

## 测试

```bash
python -m pytest -v
```

## 架构

单 agent + 多工具(自建 ReAct 循环):

```
用户 (CLI) → AgentLoop → ResilientClient → 模型 (GLM 主,DeepSeek 兜底)
                          ↘ tools: github_stats / read_profile / update_profile
                                    / read_memory / write_memory
                          ↘ SYSTEM_PROMPT: 四维度指引 + 就业卡 / 行业简报模板
```

- `agent_radar/agent/loop.py` — ReAct 循环 + SYSTEM_PROMPT + 输出模板
- `agent_radar/agent/tools/` — 各工具(SPEC 描述符 + 工厂)
- `agent_radar/llm/client.py` — GLM / DeepSeek 客户端 + ResilientClient(自动兜底)
- `agent_radar/store/` — SQLite 画像与记忆
- `agent_radar/cli.py` — 接线与 REPL

设计与实现文档见 `docs/superpowers/`。
