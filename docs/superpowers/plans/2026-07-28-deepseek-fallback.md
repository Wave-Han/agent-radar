# DeepSeek Auto-Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the GLM primary model fails mid-conversation, automatically switch to DeepSeek for the rest of the session so the REPL never crashes.

**Architecture:** A new `ResilientClient` (implements the existing `ChatClient` protocol) wraps `ZhipuChatClient` (primary) + optional `DeepSeekChatClient` (fallback). On any primary exception it marks itself degraded and routes to fallback for all subsequent calls. `AgentLoop` is unchanged. CLI also gains a `try/except` around `loop.run` so a total failure prints a message instead of crashing.

**Tech Stack:** Python 3.11+, `requests` (already a dependency — no new deps), pytest, existing `zhipuai` SDK.

## Global Constraints

- Python 3.11+ (uses `X | None` union syntax).
- **No new dependencies** — use the already-installed `requests`; do NOT add `openai`.
- `AgentLoop`, `ToolRegistry`, and tools are NOT modified.
- DeepSeek has **no built-in `web_search`** — `DeepSeekChatClient` must NOT emit a web_search tool (function tools only). This is an accepted degradation.
- Fallback is **session-wide**: once primary fails, the whole CLI session uses DeepSeek until restart.
- Code identifiers/comments in English; user-facing strings (warnings, prompts) in Chinese.
- TDD: failing test first → minimal impl → green → commit — one commit per task.
- All tests mock network — no real API calls in the suite.

---

## Task 1: Config fields for DeepSeek

**Files:**
- Modify: `agent_radar/config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` gains `deepseek_api_key: str | None = None` and `deepseek_model: str = "deepseek-chat"`; `load_config()` reads `DEEPSEEK_API_KEY` and `AGENT_RADAR_DEEPSEEK_MODEL`.

- [ ] **Step 1: Replace `agent_radar/config.py` with**

```python
"""Configuration loaded from environment / .env."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    zhipu_api_key: str
    github_token: str | None
    model: str
    db_path: str
    max_iterations: int = 8
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"


def load_config(env_file: str = ".env") -> Config:
    """Load config from a .env file then environment variables."""
    load_dotenv(env_file)
    return Config(
        zhipu_api_key=os.environ.get("ZHIPU_API_KEY", ""),
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        model=os.environ.get("AGENT_RADAR_MODEL", "glm-4"),
        db_path=os.environ.get("AGENT_RADAR_DB_PATH", "agent_radar.db"),
        max_iterations=int(os.environ.get("AGENT_RADAR_MAX_ITERATIONS", "8")),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
        deepseek_model=os.environ.get("AGENT_RADAR_DEEPSEEK_MODEL", "deepseek-chat"),
    )
```

- [ ] **Step 2: Append to `.env.example`**

```
DEEPSEEK_API_KEY=optional_for_auto_fallback_when_glm_fails
AGENT_RADAR_DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 3: Write the failing test (append to `tests/test_config.py`)**

```python
def test_load_config_reads_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    monkeypatch.setenv("AGENT_RADAR_DEEPSEEK_MODEL", "deepseek-chat")
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.deepseek_api_key == "ds-key"
    assert cfg.deepseek_model == "deepseek-chat"


def test_load_config_deepseek_defaults_to_none(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.deepseek_api_key is None
    assert cfg.deepseek_model == "deepseek-chat"
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 3 passed (1 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/config.py .env.example tests/test_config.py
git commit -m "feat: add DeepSeek config fields"
```

---

## Task 2: DeepSeekChatClient + dict tool-call parser

**Files:**
- Modify: `agent_radar/llm/client.py` (add `import requests`; add `_parse_dict_tool_calls`; add `DeepSeekChatClient`)
- Test: `tests/llm/test_client.py`

**Interfaces:**
- Consumes: `ToolCall`, `ChatResponse` (already in `client.py`).
- Produces: `_parse_dict_tool_calls(tool_calls_list) -> list[ToolCall]`; `DeepSeekChatClient(api_key, model="deepseek-chat")` implementing `.chat(messages, tools, tool_choice="auto") -> ChatResponse`.

- [ ] **Step 1: Add `import requests` to the top of `agent_radar/llm/client.py`**

After the existing `import json` line, add:

```python
import requests
```

- [ ] **Step 2: Append these to `agent_radar/llm/client.py`** (after the `ZhipuChatClient` class)

```python
def _parse_dict_tool_calls(tool_calls_list) -> list[ToolCall]:
    """Parse OpenAI/DeepSeek-style tool_calls (list of dicts) into ToolCall."""
    calls: list[ToolCall] = []
    for tc in tool_calls_list or []:
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments")) if fn.get("arguments") else {}
        except (TypeError, ValueError):
            args = {}
        calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))
    return calls


class DeepSeekChatClient:
    """DeepSeek chat client (OpenAI-compatible). Supports function calling.
    Has NO built-in web_search — only function tools are sent."""

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self._api_key = api_key
        self._model = model

    def chat(self, messages, tools, tool_choice="auto") -> ChatResponse:
        resp = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        return ChatResponse(
            content=msg.get("content"),
            tool_calls=_parse_dict_tool_calls(msg.get("tool_calls")),
            raw=data,
        )
```

- [ ] **Step 3: Write the failing tests (append to `tests/llm/test_client.py`)**

```python
from unittest.mock import MagicMock, patch

from agent_radar.llm.client import (
    DeepSeekChatClient,
    ToolCall,
    _parse_dict_tool_calls,
)


def test_parse_dict_tool_calls_decodes_json():
    raw = [{"id": "1", "function": {"name": "github_stats", "arguments": '{"repo": "x/y"}'}}]
    assert _parse_dict_tool_calls(raw) == [
        ToolCall(id="1", name="github_stats", arguments={"repo": "x/y"}),
    ]


def test_parse_dict_tool_calls_handles_none_and_bad_json():
    assert _parse_dict_tool_calls(None) == []
    bad = [{"id": "2", "function": {"name": "x", "arguments": "not-json"}}]
    assert _parse_dict_tool_calls(bad) == [ToolCall(id="2", name="x", arguments={})]


def test_deepseek_chat_excludes_websearch_and_parses():
    client = DeepSeekChatClient(api_key="k")
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "choices": [{"message": {
            "content": "hi",
            "tool_calls": [{"id": "1", "function": {
                "name": "github_stats", "arguments": '{"repo": "x/y"}'}}],
        }}]
    }
    fn_tool = {"type": "function", "function": {"name": "github_stats"}}
    with patch("agent_radar.llm.client.requests.post", return_value=fake) as mock_post:
        resp = client.chat([{"role": "user", "content": "hi"}], [fn_tool])
    body = mock_post.call_args.kwargs["json"]
    # DeepSeek must NOT receive a web_search tool
    assert all(t.get("type") != "web_search" for t in body["tools"])
    assert body["model"] == "deepseek-chat"
    assert resp.content == "hi"
    assert resp.tool_calls == [
        ToolCall(id="1", name="github_stats", arguments={"repo": "x/y"}),
    ]
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py -v`
Expected: 6 passed (3 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/llm/client.py tests/llm/test_client.py
git commit -m "feat: DeepSeek chat client (function tools, no web_search)"
```

---

## Task 3: ResilientClient (primary → fallback switch)

**Files:**
- Modify: `agent_radar/llm/client.py` (append `ResilientClient`)
- Test: `tests/llm/test_client.py`

**Interfaces:**
- Consumes: `ChatClient` protocol, `ChatResponse`.
- Produces: `ResilientClient(primary, fallback=None, on_switch=None)` implementing `ChatClient.chat(...)`.

- [ ] **Step 1: Append `ResilientClient` to `agent_radar/llm/client.py`**

```python
class ResilientClient:
    """Wraps a primary ChatClient with an optional fallback. If the primary
    raises on chat(), marks itself degraded and routes to fallback for the
    rest of the session. `on_switch` (optional) is called once on switch."""

    def __init__(self, primary: ChatClient, fallback: ChatClient | None = None,
                 on_switch=None):
        self._primary = primary
        self._fallback = fallback
        self._degraded = False
        self._on_switch = on_switch

    def chat(self, messages, tools, tool_choice="auto") -> ChatResponse:
        if self._degraded:
            if self._fallback is None:
                raise RuntimeError("degraded but no fallback configured")
            return self._fallback.chat(messages, tools, tool_choice)
        try:
            return self._primary.chat(messages, tools, tool_choice)
        except Exception:
            if self._fallback is None:
                raise
            self._degraded = True
            if self._on_switch is not None:
                self._on_switch()
            return self._fallback.chat(messages, tools, tool_choice)
```

- [ ] **Step 2: Write the failing tests (append to `tests/llm/test_client.py`)**

```python
from agent_radar.llm.client import ChatResponse, ResilientClient


class _PrimFail:
    def chat(self, m, t, tool_choice="auto"):
        raise RuntimeError("glm down")


class _FallOk:
    def __init__(self):
        self.calls = 0

    def chat(self, m, t, tool_choice="auto"):
        self.calls += 1
        return ChatResponse(content=f"fall{self.calls}")


def test_resilient_switches_then_stays_on_fallback():
    fall = _FallOk()
    rc = ResilientClient(_PrimFail(), fall)
    assert rc.chat([], []).content == "fall1"
    assert rc.chat([], []).content == "fall2"
    assert fall.calls == 2


def test_resilient_reraises_when_no_fallback():
    rc = ResilientClient(_PrimFail(), None)
    raised = False
    try:
        rc.chat([], [])
    except RuntimeError:
        raised = True
    assert raised


def test_resilient_on_switch_called_once():
    switched = []
    rc = ResilientClient(_PrimFail(), _FallOk(),
                         on_switch=lambda: switched.append(True))
    rc.chat([], [])
    rc.chat([], [])
    assert switched == [True]
```

- [ ] **Step 3: Run tests**

Run: `.venv/Scripts/python -m pytest tests/llm/test_client.py -v`
Expected: 9 passed (6 from Task 2 + 3 new).

- [ ] **Step 4: Commit**

```bash
git add agent_radar/llm/client.py tests/llm/test_client.py
git commit -m "feat: ResilientClient with session-wide primary->fallback switch"
```

---

## Task 4: Wire fallback into CLI + crash-proof REPL

**Files:**
- Modify: `agent_radar/cli.py` (imports; add `build_client`, `run_turn`; rewrite `main`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Config` (with deepseek fields), `ZhipuChatClient`, `DeepSeekChatClient`, `ResilientClient`, `AgentLoop`, `Answer`.
- Produces: `build_client(config) -> ChatClient`; `run_turn(loop, user) -> Answer | None`.

- [ ] **Step 1: Update the import line in `agent_radar/cli.py`**

Replace the existing `from agent_radar.llm.client import ZhipuChatClient` line with:

```python
from agent_radar.llm.client import DeepSeekChatClient, ResilientClient, ZhipuChatClient
```

- [ ] **Step 2: Add `build_client` and `run_turn` functions** (place them above `main`)

```python
def build_client(config: Config):
    """Build the ChatClient: Zhipu primary, with DeepSeek fallback if configured."""
    primary = ZhipuChatClient(config.zhipu_api_key, model=config.model)
    if config.deepseek_api_key:
        fallback = DeepSeekChatClient(config.deepseek_api_key, model=config.deepseek_model)
        return ResilientClient(
            primary,
            fallback,
            on_switch=lambda: print("⚠️ GLM 不可用,已切换到 DeepSeek(本轮起无法联网搜索)"),
        )
    return primary


def run_turn(loop, user: str):
    """Run one conversation turn. Return Answer, or None on failure (after printing)."""
    try:
        return loop.run(user)
    except Exception as e:  # noqa: BLE001 - keep the REPL alive
        print(f"\n⚠️ 模型调用失败,请检查 API key/余额/网络后重试。({e})")
        return None
```

- [ ] **Step 3: Rewrite `main` to use them** (replace the existing `main` function body)

```python
def main(config: Config | None = None) -> None:
    config = config or load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    onboard_profile(conn)

    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))
    loop = AgentLoop(client, registry, max_iterations=config.max_iterations)

    print("AgentRadar 就绪。输入问题,/profile 查看画像,Ctrl+C 退出。\n")
    while True:
        try:
            user = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user:
            continue
        if user == "/profile":
            print(load_profile(conn))
            continue
        ans = run_turn(loop, user)
        if ans is None:
            continue
        print(f"\nAgentRadar: {ans.content}")
        if ans.tools_used:
            print(f"(使用工具: {', '.join(ans.tools_used)})")
        print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write the failing tests (append to `tests/test_cli.py`)**

```python
from agent_radar.agent.loop import Answer
from agent_radar.config import Config
from agent_radar.llm.client import ResilientClient, ZhipuChatClient


def _cfg(deepseek_key):
    return Config(
        zhipu_api_key="fake", github_token=None, model="glm-4",
        db_path="x.db", deepseek_api_key=deepseek_key,
    )


def test_build_client_wraps_resilient_when_deepseek_configured():
    client = cli.build_client(_cfg("ds-key"))
    assert isinstance(client, ResilientClient)


def test_build_client_returns_primary_when_no_deepseek():
    client = cli.build_client(_cfg(None))
    assert isinstance(client, ZhipuChatClient)


class _BadLoop:
    def run(self, user, history=None):
        raise RuntimeError("boom")


class _GoodLoop:
    def run(self, user, history=None):
        return Answer(content="hello", tools_used=["github_stats"])


def test_run_turn_catches_exception(capsys):
    assert cli.run_turn(_BadLoop(), "hi") is None
    assert "模型调用失败" in capsys.readouterr().out


def test_run_turn_returns_answer():
    ans = cli.run_turn(_GoodLoop(), "hi")
    assert ans.content == "hello"
    assert ans.tools_used == ["github_stats"]
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 31 passed (19 existing + 2 Task 1 + 3 Task 2 + 3 Task 3 + 4 Task 4), all green, no failures.

- [ ] **Step 6: Commit**

```bash
git add agent_radar/cli.py tests/test_cli.py
git commit -m "feat: wire GLM->DeepSeek fallback into CLI; crash-proof REPL"
```

---

## Definition of Done

- `python -m pytest -v` fully green; no real network calls.
- With both keys set: GLM works normally; if GLM is forced to fail (e.g. bad/empty key), the CLI prints the switch warning once and continues on DeepSeek for the session.
- With only GLM key: behaves exactly as before (no fallback).
- A total failure (both unavailable) prints a Chinese error and the REPL stays alive for the next turn.

## Out of Scope

- External search API for DeepSeek to regain web search (separate future work).
- Provider load balancing / cost routing.
- Per-call retry of GLM (we do session-wide switch by design).
