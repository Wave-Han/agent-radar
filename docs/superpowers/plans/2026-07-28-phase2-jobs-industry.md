# Phase 2 (Jobs + Industry) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the agent answer jobs-market and industry-trend questions by extending the system prompt with two structured output templates (job card / industry brief), using the existing GLM built-in web search — no new tools, keys, or commands.

**Architecture:** Pure prompt engineering in `agent_radar/agent/loop.py`: add `JOB_CARD_TEMPLATE` and `INDUSTRY_BRIEF_TEMPLATE` module constants, then rewrite `SYSTEM_PROMPT` as an f-string that embeds them and tells the model to auto-detect question type and apply the matching format.

**Tech Stack:** Python 3.11+, no new dependencies, pytest.

## Global Constraints

- Python 3.11+.
- Only `agent_radar/agent/loop.py` changes; no other files, no new tools/keys/commands.
- Code identifiers/comments in English; `SYSTEM_PROMPT` and templates are user-facing → Chinese.
- Jobs data is **qualitative/approximate** — never invent exact numbers; label "近似/公开数据"; do NOT scrape job sites.
- Every jobs/industry answer must carry source links + time-freshness note.
- `SYSTEM_PROMPT` is an f-string that embeds the two template constants (define templates BEFORE the prompt).
- TDD: failing test first → minimal impl → green → commit.
- Existing tests must keep passing (incl. `test_loop_sends_system_prompt_first` which asserts "AgentRadar" is in the prompt).

---

## Task 1: Extend SYSTEM_PROMPT + add output templates

**Files:**
- Modify: `agent_radar/agent/loop.py` (replace the `SYSTEM_PROMPT` block; add two template constants)
- Test: `tests/agent/test_loop.py` (add imports + 4 tests)

**Interfaces:**
- Produces: module constants `JOB_CARD_TEMPLATE: str`, `INDUSTRY_BRIEF_TEMPLATE: str`, and an expanded `SYSTEM_PROMPT: str` (f-string embedding both templates).

- [ ] **Step 1: Write the failing tests (append to `tests/agent/test_loop.py`)**

Add this import at the top of the file (merge into the existing `from agent_radar.agent.loop import ...` line if one exists, otherwise add it):

```python
from agent_radar.agent.loop import (
    INDUSTRY_BRIEF_TEMPLATE,
    JOB_CARD_TEMPLATE,
    SYSTEM_PROMPT,
)
```

Then append these tests:

```python
def test_system_prompt_covers_jobs_and_industry():
    assert "就业" in SYSTEM_PROMPT
    assert "行业动态" in SYSTEM_PROMPT


def test_job_card_template_has_required_fields():
    assert "岗位方向" in JOB_CARD_TEMPLATE
    assert "薪资" in JOB_CARD_TEMPLATE
    assert "近似" in JOB_CARD_TEMPLATE
    assert "来源" in JOB_CARD_TEMPLATE


def test_industry_brief_template_has_required_fields():
    assert "动态" in INDUSTRY_BRIEF_TEMPLATE
    assert "趋势" in INDUSTRY_BRIEF_TEMPLATE
    assert "来源" in INDUSTRY_BRIEF_TEMPLATE


def test_system_prompt_embeds_both_templates():
    # The f-string prompt must contain the template fields so the model sees the format.
    assert "岗位方向" in SYSTEM_PROMPT
    assert "近期重要动态" in SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/agent/test_loop.py -v`
Expected: FAIL — `INDUSTRY_BRIEF_TEMPLATE` / `JOB_CARD_TEMPLATE` not yet defined (ImportError).

- [ ] **Step 3: Replace the `SYSTEM_PROMPT` block in `agent_radar/agent/loop.py`**

Find the existing `SYSTEM_PROMPT = """..."""` assignment and replace the whole block with:

```python
JOB_CARD_TEMPLATE = """【就业行情卡】
- 岗位方向:
- 薪资区间(定性,近似/公开数据):
- 核心技能 Top5:
- 热门城市:
- 需求趋势(一句话):
- 来源 + 时效:"""


INDUSTRY_BRIEF_TEMPLATE = """【行业动态简报】
- 近期重要动态(融资/新品/开源):
- 值得关注的公司·项目:
- 趋势判断(升温/降温):
- 来源 + 时效:"""


SYSTEM_PROMPT = f"""你是 AgentRadar,面向程序员的 AI agent 行情与学习方向顾问。

工作方式:
1. 用内置 web_search 实时了解 AI agent 领域的技术趋势、框架热度、行业动态、就业行情。
2. 回答前先用 read_profile 了解用户背景;若用户在提问中透露了新背景,用 update_profile 记录。
3. 基于用户背景给出个性化、可执行的学习方向/路径建议:分阶段、标优先级、附资源链接。
4. 可用 github_stats 核实具体仓库热度。
5. 涉及事实/数据时在正文中附出来源链接;信息可能过时时明确说明时效。

按问题类型自动选择输出格式:
- 技术趋势 / 学习路径:自由结构,先结论后展开,附来源。
- 就业行情(岗位 / 薪资 / 技能 / 招聘):按下面的「就业行情卡」输出。薪资为定性近似,标注"近似/公开数据",不要编造精确数字;以公开信息为准,不要爬取招聘网站。
{JOB_CARD_TEMPLATE}
- 行业动态(公司 / 产品 / 融资 / 开源动向):按下面的「行业动态简报」输出,附来源与时效。
{INDUSTRY_BRIEF_TEMPLATE}

混合问题可综合多种格式。用简体中文回答,先给结论再展开。"""
```

- [ ] **Step 4: Run the loop tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/agent/test_loop.py -v`
Expected: 7 passed (3 existing + 4 new).

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 35 passed (31 existing + 4 new), all green, no failures.

- [ ] **Step 6: Commit**

```bash
git add agent_radar/agent/loop.py tests/agent/test_loop.py
git commit -m "feat: Phase 2 jobs/industry templates in system prompt"
```

---

## Definition of Done

- `python -m pytest -v` fully green (35 passed).
- `SYSTEM_PROMPT` references both templates and instructs jobs/industry coverage with the qualitative-data + source + freshness rules.
- Manual smoke test (GLM key): asking "AI agent 现在就业行情怎么样" yields a job-card-style answer; asking "最近 AI agent 行业有什么动态" yields a brief-style answer — both with source links and a freshness note.

## Out of Scope

- `jobs_search` / `news_search` tools (would need an external search key — future).
- `/jobs` `/news` slash commands (user chose auto-detection).
- Real job-site data sources (anti-scrape / legal risk).
