# Phase 3a (Multi-Agent Routing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single agent with an `Orchestrator` that classifies each question (lightweight LLM call) and routes it to a dimension expert (trend / jobs / industry / learning / general), where each expert is an `AgentLoop` instance differing only by system prompt.

**Architecture:** New `experts.py` (per-dimension prompts) + `orchestrator.py` (route + run). `AgentLoop` is reused unchanged; all experts share the same `registry` and `client` (so `ResilientClient` GLM→DeepSeek fallback applies automatically). `cli.py` swaps `AgentLoop` for `Orchestrator`.

**Tech Stack:** Python 3.11+, no new dependencies, pytest.

## Global Constraints

- Python 3.11+.
- `AgentLoop` is NOT modified; `SYSTEM_PROMPT` / `JOB_CARD_TEMPLATE` / `INDUSTRY_BRIEF_TEMPLATE` are reused (general expert + jobs/industry experts reference them).
- Experts share one `registry` and one `client` — no per-expert tool subsets.
- Code identifiers/comments in English; expert/router prompts are user-facing → Chinese.
- The router reuses the shared client; it may opportunistically trigger web_search — acceptable (the prompt tells the model to just classify). Tests mock the client so this is not exercised.
- TDD: failing test first → minimal impl → green → commit — one commit per task.
- All tests mock the model — no real API calls.

---

## Task 1: Per-dimension expert prompts

**Files:**
- Create: `agent_radar/agent/experts.py`
- Test: `tests/agent/test_experts.py`

**Interfaces:**
- Consumes: `SYSTEM_PROMPT`, `JOB_CARD_TEMPLATE`, `INDUSTRY_BRIEF_TEMPLATE` from `agent_radar/agent/loop.py`.
- Produces: `EXPERT_PROMPTS: dict[str, str]` with keys `trend`, `jobs`, `industry`, `learning`, `general`; `DIMENSIONS: frozenset[str]` matching the keys.

- [ ] **Step 1: Write the failing test `tests/agent/test_experts.py`**

```python
from agent_radar.agent.experts import DIMENSIONS, EXPERT_PROMPTS
from agent_radar.agent.loop import SYSTEM_PROMPT


def test_all_five_dimensions_present():
    assert set(EXPERT_PROMPTS) == {"trend", "jobs", "industry", "learning", "general"}


def test_jobs_prompt_references_job_card_template():
    assert "岗位方向" in EXPERT_PROMPTS["jobs"]
    assert "近似" in EXPERT_PROMPTS["jobs"]


def test_industry_prompt_references_brief_template():
    assert "近期重要动态" in EXPERT_PROMPTS["industry"]


def test_general_prompt_is_system_prompt():
    assert EXPERT_PROMPTS["general"] is SYSTEM_PROMPT


def test_dimensions_matches_keys():
    assert DIMENSIONS == frozenset(EXPERT_PROMPTS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/agent/test_experts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_radar.agent.experts'`.

- [ ] **Step 3: Write `agent_radar/agent/experts.py`**

```python
"""Per-dimension expert system prompts for the multi-agent orchestrator."""
from agent_radar.agent.loop import (
    INDUSTRY_BRIEF_TEMPLATE,
    JOB_CARD_TEMPLATE,
    SYSTEM_PROMPT,
)

_COMMON = (
    "\n\n工作方式:用内置 web_search 实时调研;回答前用 read_profile 了解用户背景"
    "(若提问中透露新背景,用 update_profile 记录);可用 github_stats 核实仓库热度;"
    "涉及数据附来源链接并说明时效;用简体中文,先给结论再展开。"
)

EXPERT_PROMPTS = {
    "trend": (
        "你是 AgentRadar 的「技术趋势专家」,专注 AI agent 领域的技术生态趋势:"
        "框架(LangChain / AutoGen / CrewAI 等)、模型、技术方向的升温 / 降温。"
        "用 github_stats 核实仓库热度,用 web_search 看最新动态。" + _COMMON
    ),
    "jobs": (
        "你是 AgentRadar 的「就业行情专家」,专注 AI agent 相关岗位的就业市场:"
        "岗位方向、薪资(定性近似,标注「近似 / 公开数据」,不要编造精确数字)、"
        "核心技能、热门城市、需求趋势。不要爬取招聘网站,以公开信息为准。"
        "按下面的「就业行情卡」格式输出:\n" + JOB_CARD_TEMPLATE + _COMMON
    ),
    "industry": (
        "你是 AgentRadar 的「行业动态专家」,专注 AI agent 领域的公司 / 产品 / "
        "融资 / 开源动向。按下面的「行业动态简报」格式输出:\n" + INDUSTRY_BRIEF_TEMPLATE
        + _COMMON
    ),
    "learning": (
        "你是 AgentRadar 的「学习方向专家」,专注为用户给出个性化、可执行的学习路径。"
        "务必先 read_profile 了解用户背景,基于背景给分阶段、标优先级、附资源链接的学习路径。"
        + _COMMON
    ),
    "general": SYSTEM_PROMPT,
}

DIMENSIONS = frozenset(EXPERT_PROMPTS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/agent/test_experts.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_radar/agent/experts.py tests/agent/test_experts.py
git commit -m "feat: per-dimension expert prompts"
```

---

## Task 2: Orchestrator (route + run)

**Files:**
- Create: `agent_radar/agent/orchestrator.py`
- Test: `tests/agent/test_orchestrator.py`

**Interfaces:**
- Consumes: `ChatClient.chat(messages, tools, tool_choice)`, `ToolRegistry.to_tools_param()`, `AgentLoop(client, registry, max_iterations, system_prompt).run(user, history)`, `EXPERT_PROMPTS`, `DIMENSIONS`.
- Produces: `Orchestrator(client, registry, max_iterations=8)` with `.route(user_message) -> str` and `.run(user_message, history=None) -> Answer`.

- [ ] **Step 1: Write the failing test `tests/agent/test_orchestrator.py`**

```python
from agent_radar.agent.orchestrator import Orchestrator
from agent_radar.agent.registry import ToolRegistry
from agent_radar.llm.client import ChatResponse


class _ScriptedClient:
    """First chat() = router (returns label); later chat()s = expert turns."""
    def __init__(self, label, expert_reply="expert-answer"):
        self._label = label
        self._expert_reply = expert_reply
        self._n = 0
        self.expert_systems = []

    def chat(self, messages, tools, tool_choice="auto"):
        self._n += 1
        if self._n == 1:  # router call
            return ChatResponse(content=self._label)
        self.expert_systems.append(messages[0]["content"])
        return ChatResponse(content=self._expert_reply)


def _empty_registry():
    return ToolRegistry()


def test_route_returns_each_dimension():
    for label in ["trend", "jobs", "industry", "learning", "general"]:
        orch = Orchestrator(_ScriptedClient(label), _empty_registry())
        assert orch.route("whatever") == label


def test_route_lowercases_and_trims():
    orch = Orchestrator(_ScriptedClient("  JOBS "), _empty_registry())
    assert orch.route("x") == "jobs"


def test_route_unknown_label_falls_back_to_general():
    orch = Orchestrator(_ScriptedClient("something-unknown"), _empty_registry())
    assert orch.route("x") == "general"


def test_route_empty_content_falls_back_to_general():
    orch = Orchestrator(_ScriptedClient(""), _empty_registry())
    assert orch.route("x") == "general"


def test_run_routes_to_expert_and_returns_answer():
    client = _ScriptedClient("jobs", expert_reply="就业答案")
    orch = Orchestrator(client, _empty_registry())
    ans = orch.run("AI agent 就业?")
    assert ans.content == "就业答案"
    # the expert turn used the jobs expert prompt
    assert "就业" in client.expert_systems[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/agent/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_radar.agent.orchestrator'`.

- [ ] **Step 3: Write `agent_radar/agent/orchestrator.py`**

```python
"""Orchestrator: classifies a user message and routes it to a dimension expert."""
from agent_radar.agent.experts import DIMENSIONS, EXPERT_PROMPTS
from agent_radar.agent.loop import AgentLoop, Answer
from agent_radar.llm.client import ChatClient

_ROUTE_PROMPT = (
    "判断用户问题主要属于下面哪个维度,只回复一个英文词,不要任何额外文字或标点:\n"
    "trend(技术生态趋势)、jobs(就业行情)、industry(行业动态)、"
    "learning(学习方向 / 路径)、general(其他或综合)。\n\n"
    "用户问题:"
)


class Orchestrator:
    """Routes each turn to a dimension expert (an AgentLoop with a focused prompt)."""

    def __init__(self, client: ChatClient, registry, max_iterations: int = 8):
        self._client = client
        self._registry = registry
        self._max = max_iterations

    def route(self, user_message: str) -> str:
        resp = self._client.chat(
            messages=[
                {"role": "system", "content": "你是一个分类器,只输出维度标签,不要搜索。"},
                {"role": "user", "content": _ROUTE_PROMPT + user_message},
            ],
            tools=[],
        )
        text = (resp.content or "").strip().lower()
        first = text.split()[0] if text else ""
        return first if first in DIMENSIONS else "general"

    def run(self, user_message: str, history: list[dict] | None = None) -> Answer:
        dim = self.route(user_message)
        expert = AgentLoop(
            self._client,
            self._registry,
            max_iterations=self._max,
            system_prompt=EXPERT_PROMPTS[dim],
        )
        return expert.run(user_message, history=history)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/agent/test_orchestrator.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_radar/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat: Orchestrator routes to dimension experts"
```

---

## Task 3: Wire Orchestrator into the CLI

**Files:**
- Modify: `agent_radar/cli.py` (import `Orchestrator`; add `build_orchestrator`; use it in `main`)
- Test: `tests/test_cli.py` (add `test_build_orchestrator_returns_orchestrator`)

**Interfaces:**
- Consumes: `Orchestrator(client, registry, max_iterations)`; existing `build_client`, `build_registry`, `run_turn`.
- Produces: `cli.build_orchestrator(client, registry, max_iterations=8) -> Orchestrator`. `main` now drives an `Orchestrator` instead of an `AgentLoop`.

- [ ] **Step 1: Write the failing test (append to `tests/test_cli.py`)**

```python
def test_build_orchestrator_returns_orchestrator():
    from agent_radar.agent.orchestrator import Orchestrator

    class _C:
        def chat(self, m, t, tool_choice="auto"):
            from agent_radar.llm.client import ChatResponse
            return ChatResponse(content="general")

    orch = cli.build_orchestrator(_C(), object())  # registry unused at construction
    assert isinstance(orch, Orchestrator)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py::test_build_orchestrator_returns_orchestrator -v`
Expected: FAIL — `AttributeError: module 'agent_radar.cli' has no attribute 'build_orchestrator'`.

- [ ] **Step 3: Update `agent_radar/cli.py`**

Add `Orchestrator` to the `agent_radar.llm.client` import line is wrong — it lives in `agent_radar.agent.orchestrator`. Add this import near the other agent imports:

```python
from agent_radar.agent.orchestrator import Orchestrator
```

Add the `build_orchestrator` helper (next to `build_client` / `build_registry`):

```python
def build_orchestrator(client, registry, max_iterations: int = 8):
    """Build the multi-agent Orchestrator (routes to dimension experts)."""
    return Orchestrator(client, registry, max_iterations=max_iterations)
```

In `main`, replace the `AgentLoop` construction and the turn call. Find:

```python
    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))
    loop = AgentLoop(client, registry, max_iterations=config.max_iterations)
```

Replace with:

```python
    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))
    loop = build_orchestrator(client, registry, max_iterations=config.max_iterations)
```

(`run_turn(loop, user)` stays unchanged — `Orchestrator.run(user)` is compatible with `run_turn`'s `loop.run(user)` call.)

- [ ] **Step 4: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 46 passed (35 existing + 5 Task 1 + 5 Task 2 + 1 Task 3), all green, no failures.

- [ ] **Step 5: Commit**

```bash
git add agent_radar/cli.py tests/test_cli.py
git commit -m "feat: wire Orchestrator into CLI (multi-agent routing)"
```

---

## Definition of Done

- `python -m pytest -v` fully green; no real network calls.
- A routed turn: `Orchestrator.route` classifies the dimension (mock-verifiable), then the matching expert `AgentLoop` runs with that expert's prompt.
- Fallback: unknown / empty router output → `general` expert (existing four-dimension prompt).
- CLI launches and drives the `Orchestrator`; GLM→DeepSeek fallback still applies (shared client).
- Manual smoke test (GLM key): asking a jobs question routes to the jobs expert and yields a job-card answer; asking an industry question yields a brief.

## Out of Scope

- Parallel multi-expert collaboration (future).
- Per-expert tool subsets (decided to share).
- Scheduled briefings, Web UI (separate sub-systems).
