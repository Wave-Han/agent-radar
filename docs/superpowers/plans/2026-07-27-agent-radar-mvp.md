# AgentRadar MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conversational AI agent that uses Zhipu GLM-4 (with built-in web search) plus function-calling tools to answer a programmer's questions about AI-agent trends and produce a personalized learning path.

**Architecture:** A self-built ReAct loop drives a single agent. The model gets built-in `web_search` for real-time info plus five function tools (`github_stats`, `read_profile`, `update_profile`, `read_memory`, `write_memory`). Profile and memory persist in local SQLite. Interaction is a CLI REPL.

**Tech Stack:** Python 3.11+, `zhipuai` SDK, `requests`, `python-dotenv`, SQLite (stdlib), `pytest`.

## Global Constraints

- Python 3.11+ (uses `X | None` union syntax).
- Model: Zhipu GLM-4 via `zhipuai` SDK; requires `ZHIPU_API_KEY` in `.env`.
- Real-time search via Zhipu **built-in** `web_search` (no extra search key, no external network dependency beyond Zhipu + GitHub).
- Storage: SQLite, single-user. DB file git-ignored.
- Code identifiers and comments in English; user-facing strings (CLI prompts, agent fallback messages) in Chinese.
- TDD: failing test first, then minimal implementation, then green, then commit — one commit per logical unit.
- Each tool is a function descriptor (`SPEC`) + a `run` factory that closes over its dependencies; tools never import each other.
- No scraping of job sites in MVP.

---

## File Structure

```
ai_agent/
├── agent_radar/
│   ├── __init__.py
│   ├── config.py                 # env-driven Config
│   ├── cli.py                    # REPL + wiring
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py             # ChatClient protocol + ZhipuChatClient
│   ├── data/
│   │   ├── __init__.py
│   │   └── github_client.py      # GitHub REST client
│   ├── store/
│   │   ├── __init__.py
│   │   ├── db.py                 # connection + schema
│   │   ├── profile.py            # profile CRUD (JSON blob)
│   │   └── memory.py             # memory append/list
│   └── agent/
│       ├── __init__.py
│       ├── registry.py           # ToolRegistry
│       ├── loop.py               # AgentLoop (ReAct)
│       └── tools/
│           ├── __init__.py
│           ├── github_stats.py
│           ├── profile.py
│           └── memory.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_cli.py
│   ├── test_integration.py
│   ├── store/test_storage.py
│   ├── llm/test_client.py
│   ├── data/test_github_client.py
│   └── agent/
│       ├── test_registry.py
│       ├── test_loop.py
│       └── tools/test_github_stats.py
├── docs/superpowers/{specs,plans}/...
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Task 1: Project Skeleton + Config + Test Harness

**Files:**
- Create: `agent_radar/__init__.py`, `agent_radar/config.py`
- Create: `agent_radar/llm/__init__.py`, `agent_radar/data/__init__.py`, `agent_radar/store/__init__.py`, `agent_radar/agent/__init__.py`, `agent_radar/agent/tools/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_config.py`
- Create: `requirements.txt`, `.env.example`

**Interfaces:**
- Produces: `agent_radar.config.load_config(env_file=".env") -> Config`, where `Config` has `zhipu_api_key: str`, `github_token: str | None`, `model: str`, `db_path: str`, `max_iterations: int`.

- [ ] **Step 1: Create package init files (empty)**

Create each `__init__.py` listed above as an empty file (a one-line docstring is fine). These make `agent_radar` and its subpackages importable.

- [ ] **Step 2: Write `requirements.txt`**

```
zhipuai>=2.1.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Write `.env.example`**

```
ZHIPU_API_KEY=your_zhipu_api_key_here
GITHUB_TOKEN=optional_for_higher_github_rate_limit
AGENT_RADAR_MODEL=glm-4
AGENT_RADAR_DB_PATH=agent_radar.db
AGENT_RADAR_MAX_ITERATIONS=8
```

- [ ] **Step 4: Write `agent_radar/config.py`**

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


def load_config(env_file: str = ".env") -> Config:
    """Load config from a .env file then environment variables."""
    load_dotenv(env_file)
    return Config(
        zhipu_api_key=os.environ.get("ZHIPU_API_KEY", ""),
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        model=os.environ.get("AGENT_RADAR_MODEL", "glm-4"),
        db_path=os.environ.get("AGENT_RADAR_DB_PATH", "agent_radar.db"),
        max_iterations=int(os.environ.get("AGENT_RADAR_MAX_ITERATIONS", "8")),
    )
```

- [ ] **Step 5: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures."""
import sqlite3

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """A fresh on-disk SQLite connection for storage tests."""
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
```

- [ ] **Step 6: Write the failing test `tests/test_config.py`**

```python
from agent_radar.config import load_config


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    monkeypatch.setenv("GITHUB_TOKEN", "g")
    monkeypatch.setenv("AGENT_RADAR_MODEL", "glm-4-plus")
    cfg = load_config(env_file="/does/not/exist")  # skip file, fall back to env
    assert cfg.zhipu_api_key == "k"
    assert cfg.github_token == "g"
    assert cfg.model == "glm-4-plus"
    assert cfg.max_iterations == 8
```

- [ ] **Step 7: Create venv, install deps, run the test**

```bash
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash; use .venv\Scripts\activate on cmd
python -m pip install -r requirements.txt
python -m pytest tests/test_config.py -v
```
Expected: 1 passed.

- [ ] **Step 8: Commit**

```bash
git add agent_radar/ tests/ requirements.txt .env.example
git commit -m "feat: project skeleton, config loader, test harness"
```

---

## Task 2: SQLite Storage Layer (db / profile / memory)

**Files:**
- Create: `agent_radar/store/db.py`, `agent_radar/store/profile.py`, `agent_radar/store/memory.py`
- Test: `tests/store/test_storage.py`

**Interfaces:**
- Produces: `db.get_connection(db_path) -> Connection`, `db.init_db(conn) -> None`
- Produces: `profile.load_profile(conn) -> dict`, `profile.save_profile(conn, dict) -> dict`, `profile.patch_profile(conn, dict) -> dict`
- Produces: `memory.append_memory(conn, role, content) -> None`, `memory.list_recent(conn, n=10) -> list[dict]`

- [ ] **Step 1: Write `agent_radar/store/db.py`**

```python
"""SQLite connection management and schema initialization."""
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts TEXT NOT NULL
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()
```

- [ ] **Step 2: Write `agent_radar/store/profile.py`**

```python
"""User profile storage: single row (id=1) holding a JSON blob."""
import json
import sqlite3


def load_profile(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT data FROM profile WHERE id = 1").fetchone()
    return json.loads(row["data"]) if row else {}


def save_profile(conn: sqlite3.Connection, profile: dict) -> dict:
    conn.execute(
        "INSERT INTO profile (id, data) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
        (json.dumps(profile, ensure_ascii=False),),
    )
    conn.commit()
    return load_profile(conn)


def patch_profile(conn: sqlite3.Connection, updates: dict) -> dict:
    merged = load_profile(conn)
    merged.update(updates)
    return save_profile(conn, merged)
```

- [ ] **Step 3: Write `agent_radar/store/memory.py`**

```python
"""Conversation memory: append-only log with recent-N retrieval."""
import sqlite3
from datetime import datetime, timezone


def append_memory(conn: sqlite3.Connection, role: str, content: str) -> None:
    conn.execute(
        "INSERT INTO memory (role, content, ts) VALUES (?, ?, ?)",
        (role, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def list_recent(conn: sqlite3.Connection, n: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content, ts FROM memory ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    out = [{"role": r["role"], "content": r["content"], "ts": r["ts"]} for r in rows]
    return list(reversed(out))
```

- [ ] **Step 4: Write the failing test `tests/store/test_storage.py`**

```python
from agent_radar.store.db import init_db
from agent_radar.store.profile import load_profile, save_profile, patch_profile
from agent_radar.store.memory import append_memory, list_recent


def test_profile_empty_then_save_then_patch(tmp_db):
    init_db(tmp_db)
    assert load_profile(tmp_db) == {}
    save_profile(tmp_db, {"role": "backend", "years": 3})
    assert load_profile(tmp_db) == {"role": "backend", "years": 3}
    patch_profile(tmp_db, {"goal": "ai-agent"})
    assert load_profile(tmp_db) == {
        "role": "backend", "years": 3, "goal": "ai-agent",
    }


def test_memory_append_keeps_chronological_order(tmp_db):
    init_db(tmp_db)
    assert list_recent(tmp_db) == []
    append_memory(tmp_db, "user", "first")
    append_memory(tmp_db, "assistant", "second")
    items = list_recent(tmp_db, 5)
    assert [m["content"] for m in items] == ["first", "second"]
```

- [ ] **Step 5: Run tests, verify pass**

Run: `python -m pytest tests/store/test_storage.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add agent_radar/store/ tests/store/
git commit -m "feat: SQLite storage layer (db schema, profile, memory)"
```

---

## Task 3: LLM Client (Zhipu GLM + built-in web search)

**Files:**
- Create: `agent_radar/llm/client.py`
- Test: `tests/llm/test_client.py`

**Interfaces:**
- Produces: dataclasses `ToolCall(id, name, arguments: dict)`, `ChatResponse(content: str | None, tool_calls: list[ToolCall], raw)`
- Produces: `ZhipuChatClient(api_key, model="glm-4", enable_websearch=True)` with `.chat(messages, tools, tool_choice="auto") -> ChatResponse`
- Helper `_parse_tool_calls(raw) -> list[ToolCall]` (pure, unit-tested).

- [ ] **Step 1: Write `agent_radar/llm/client.py`**

```python
"""LLM chat client: protocol, Zhipu GLM implementation, tool-call parsing."""
import json
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: object | None = None


class ChatClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict],
             tool_choice: str = "auto") -> ChatResponse: ...


def _parse_tool_calls(raw_tool_calls) -> list[ToolCall]:
    """Parse Zhipu/OpenAI-style tool_calls into ToolCall dataclasses."""
    calls: list[ToolCall] = []
    for tc in raw_tool_calls or []:
        fn = tc.function
        try:
            args = json.loads(fn.arguments) if getattr(fn, "arguments", None) else {}
        except (TypeError, ValueError):
            args = {}
        calls.append(ToolCall(id=tc.id, name=fn.name, arguments=args))
    return calls


class ZhipuChatClient:
    """Zhipu GLM client: function calling + built-in web search."""

    def __init__(self, api_key: str, model: str = "glm-4",
                 enable_websearch: bool = True):
        from zhipuai import ZhipuAI  # lazy import so tests can stub it
        self._client = ZhipuAI(api_key=api_key)
        self._model = model
        self._enable_websearch = enable_websearch

    def _build_tools(self, function_tools: list[dict]) -> list[dict]:
        tools: list[dict] = []
        if self._enable_websearch:
            tools.append({
                "type": "web_search",
                "web_search": {"enable": True, "search_result": True},
            })
        tools.extend(function_tools)
        return tools

    def chat(self, messages, tools, tool_choice="auto") -> ChatResponse:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=self._build_tools(tools),
            tool_choice=tool_choice,
        )
        msg = resp.choices[0].message
        return ChatResponse(
            content=getattr(msg, "content", None),
            tool_calls=_parse_tool_calls(getattr(msg, "tool_calls", None)),
            raw=resp,
        )
```

- [ ] **Step 2: Write the failing test `tests/llm/test_client.py`**

```python
import json

from agent_radar.llm.client import _parse_tool_calls, ZhipuChatClient, ToolCall


class _Fn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _RawTC:
    def __init__(self, id_, name, arguments):
        self.id = id_
        self.function = _Fn(name, arguments)


def test_parse_tool_calls_decodes_json_arguments():
    raw = [_RawTC("1", "github_stats", json.dumps({"repo": "langchain-ai/langchain"}))]
    assert _parse_tool_calls(raw) == [
        ToolCall(id="1", name="github_stats",
                 arguments={"repo": "langchain-ai/langchain"}),
    ]


def test_parse_tool_calls_handles_none_and_bad_json():
    assert _parse_tool_calls(None) == []
    assert _parse_tool_calls([_RawTC("2", "x", "not-json")]) == [
        ToolCall(id="2", name="x", arguments={}),
    ]


def test_build_tools_prepends_websearch():
    # Bypass __init__ to avoid needing a real API key / SDK.
    client = ZhipuChatClient.__new__(ZhipuChatClient)
    client._enable_websearch = True
    fn = {"type": "function", "function": {"name": "github_stats"}}
    built = client._build_tools([fn])
    assert built[0]["type"] == "web_search"
    assert built[1] == fn
```

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/llm/test_client.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add agent_radar/llm/ tests/llm/
git commit -m "feat: LLM client (Zhipu GLM + built-in web search, tool-call parsing)"
```

---

## Task 4: GitHub Client + `github_stats` Tool

**Files:**
- Create: `agent_radar/data/github_client.py`, `agent_radar/agent/tools/github_stats.py`
- Test: `tests/data/test_github_client.py`, `tests/agent/tools/test_github_stats.py`

**Interfaces:**
- Produces: `GitHubClient(token=None)` with `.get_repo(owner, repo) -> dict` (keys: `full_name, stars, forks, open_issues, description, language, url`)
- Produces: `github_stats.SPEC` (function schema) and `github_stats.make_tool(client) -> Callable[[repo: str], str]`.

- [ ] **Step 1: Write `agent_radar/data/github_client.py`**

```python
"""Thin GitHub REST client returning the fields we care about."""
import requests


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self._headers = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def get_repo(self, owner: str, repo: str) -> dict:
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        resp = requests.get(url, headers=self._headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "full_name": data["full_name"],
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "open_issues": data["open_issues_count"],
            "description": data.get("description"),
            "language": data.get("language"),
            "url": data["html_url"],
        }
```

- [ ] **Step 2: Write the failing test `tests/data/test_github_client.py`**

```python
from unittest.mock import MagicMock, patch

from agent_radar.data.github_client import GitHubClient


def test_get_repo_parses_fields():
    client = GitHubClient(token="t")
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "full_name": "o/r", "stargazers_count": 10, "forks_count": 2,
        "open_issues_count": 1, "description": "d", "language": "Python",
        "html_url": "https://github.com/o/r",
    }
    with patch("agent_radar.data.github_client.requests.get", return_value=fake):
        stats = client.get_repo("o", "r")
    assert stats["stars"] == 10
    assert stats["forks"] == 2
    assert stats["url"] == "https://github.com/o/r"
```

- [ ] **Step 3: Run test, verify pass**

Run: `python -m pytest tests/data/test_github_client.py -v`
Expected: 1 passed.

- [ ] **Step 4: Write `agent_radar/agent/tools/github_stats.py`**

```python
"""github_stats tool: returns repo stars/forks/language for 'owner/repo'."""
from agent_radar.data.github_client import GitHubClient

SPEC = {
    "type": "function",
    "function": {
        "name": "github_stats",
        "description": (
            "Fetch GitHub repository popularity (stars, forks, primary language) "
            "for a repo given as 'owner/repo'. Use this to judge how hot a "
            "framework/library is."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' form, e.g. 'langchain-ai/langchain'.",
                }
            },
            "required": ["repo"],
        },
    },
}


def make_tool(client: GitHubClient):
    def run(repo: str) -> str:
        owner, _, name = repo.partition("/")
        if not name:
            return f"Invalid repo '{repo}'. Use the 'owner/repo' form."
        try:
            s = client.get_repo(owner, name)
        except Exception as e:  # noqa: BLE001 - error surfaced back to the model
            return f"GitHub lookup failed for '{repo}': {e}"
        return (
            f"{s['full_name']}: {s['stars']} stars, {s['forks']} forks, "
            f"language={s['language']}. {s['description'] or ''} {s['url']}"
        )
    return run
```

- [ ] **Step 5: Write the failing test `tests/agent/tools/test_github_stats.py`**

```python
from agent_radar.agent.tools.github_stats import make_tool, SPEC


class _FakeGitHub:
    def get_repo(self, owner, repo):
        return {
            "full_name": f"{owner}/{repo}", "stars": 1234, "forks": 56,
            "open_issues": 7, "description": "fake desc", "language": "Python",
            "url": f"https://github.com/{owner}/{repo}",
        }


def test_spec_name():
    assert SPEC["function"]["name"] == "github_stats"


def test_run_formats_stats():
    out = make_tool(_FakeGitHub())("langchain-ai/langchain")
    assert "1234 stars" in out
    assert "Python" in out
    assert "https://github.com/langchain-ai/langchain" in out


def test_run_rejects_missing_slash():
    out = make_tool(_FakeGitHub())("no-slash")
    assert "Invalid" in out
```

- [ ] **Step 6: Run tests, verify pass**

Run: `python -m pytest tests/agent/tools/test_github_stats.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add agent_radar/data/github_client.py agent_radar/agent/tools/github_stats.py tests/data tests/agent
git commit -m "feat: GitHub client + github_stats tool"
```

---

## Task 5: Profile/Memory Tools + Tool Registry

**Files:**
- Create: `agent_radar/agent/tools/profile.py`, `agent_radar/agent/tools/memory.py`, `agent_radar/agent/registry.py`
- Test: `tests/agent/test_registry.py`, `tests/agent/tools/test_profile_tools.py`

**Interfaces:**
- Produces: `profile.{READ_SPEC, UPDATE_SPEC, make_read_tool(conn), make_update_tool(conn)}`
- Produces: `memory.{READ_SPEC, WRITE_SPEC, make_read_tool(conn), make_write_tool(conn)}`
- Produces: `registry.ToolRegistry` with `.register(spec, fn)`, `.get(name)`, `.to_tools_param() -> list[dict]`, `.execute(name, arguments: dict) -> str`, `.names() -> list[str]`.

- [ ] **Step 1: Write `agent_radar/agent/tools/profile.py`**

```python
"""Profile tools: read / update the single-user profile."""
import json

READ_SPEC = {
    "type": "function",
    "function": {
        "name": "read_profile",
        "description": "Read the current user profile (role, skills, years, goal).",
        "parameters": {"type": "object", "properties": {}},
    },
}

UPDATE_SPEC = {
    "type": "function",
    "function": {
        "name": "update_profile",
        "description": "Update the user profile with new fields (e.g. role, skills, years, goal).",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {"type": "object", "description": "Profile fields to set/overwrite."}
            },
            "required": ["fields"],
        },
    },
}


def make_read_tool(conn):
    def run() -> str:
        from agent_radar.store.profile import load_profile
        return json.dumps(load_profile(conn), ensure_ascii=False)
    return run


def make_update_tool(conn):
    def run(fields: dict) -> str:
        from agent_radar.store.profile import patch_profile
        updated = patch_profile(conn, fields)
        return "Profile updated: " + json.dumps(updated, ensure_ascii=False)
    return run
```

- [ ] **Step 2: Write `agent_radar/agent/tools/memory.py`**

```python
"""Memory tools: read recent items / append a short summary."""
import json

READ_SPEC = {
    "type": "function",
    "function": {
        "name": "read_memory",
        "description": "Read recent conversation memory items (oldest-first).",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "How many recent items."}},
        },
    },
}

WRITE_SPEC = {
    "type": "function",
    "function": {
        "name": "write_memory",
        "description": "Append a short summary/fact to long-term memory for future turns.",
        "parameters": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
}


def make_read_tool(conn):
    def run(n: int = 10) -> str:
        from agent_radar.store.memory import list_recent
        return json.dumps(list_recent(conn, n), ensure_ascii=False)
    return run


def make_write_tool(conn):
    def run(content: str) -> str:
        from agent_radar.store.memory import append_memory
        append_memory(conn, "assistant", content)
        return "Saved to memory."
    return run
```

- [ ] **Step 3: Write `agent_radar/agent/registry.py`**

```python
"""Tool registry: register schemas, export for the model, dispatch calls."""
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    spec: dict
    fn: Callable[..., str]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, spec: dict, fn: Callable[..., str]) -> None:
        name = spec["function"]["name"]
        self._tools[name] = Tool(name, spec, fn)

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def to_tools_param(self) -> list[dict]:
        return [t.spec for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools[name]
        try:
            return tool.fn(**arguments)
        except Exception as e:  # noqa: BLE001 - return error string to the model
            return f"Tool '{name}' failed: {e}"

    def names(self) -> list[str]:
        return list(self._tools)
```

- [ ] **Step 4: Write the failing test `tests/agent/test_registry.py`**

```python
from agent_radar.agent.registry import ToolRegistry


def _spec(name):
    return {"type": "function", "function": {
        "name": name, "parameters": {"type": "object", "properties": {}}}}


def test_register_export_and_dispatch():
    reg = ToolRegistry()
    reg.register(_spec("echo"), lambda **kw: "echoed")
    assert reg.to_tools_param() == [_spec("echo")]
    assert reg.execute("echo", {}) == "echoed"


def test_execute_returns_error_string_on_exception():
    reg = ToolRegistry()

    def boom(**kw):
        raise RuntimeError("nope")

    reg.register(_spec("boom"), boom)
    out = reg.execute("boom", {})
    assert "failed" in out and "nope" in out
```

- [ ] **Step 5: Write the failing test `tests/agent/tools/test_profile_tools.py`**

```python
from agent_radar.store.db import init_db
from agent_radar.agent.tools.profile import make_read_tool, make_update_tool


def test_update_then_read(tmp_db):
    init_db(tmp_db)
    upd = make_update_tool(tmp_db)
    rd = make_read_tool(tmp_db)
    msg = upd(fields={"role": "backend", "years": 3})
    assert "backend" in msg
    assert "backend" in rd()
```

- [ ] **Step 6: Run tests, verify pass**

Run: `python -m pytest tests/agent -v`
Expected: 3 passed (registry 2 + profile tools 1).

- [ ] **Step 7: Commit**

```bash
git add agent_radar/agent/tools/profile.py agent_radar/agent/tools/memory.py agent_radar/agent/registry.py tests/agent
git commit -m "feat: profile/memory tools and tool registry"
```

---

## Task 6: Agent ReAct Loop

**Files:**
- Create: `agent_radar/agent/loop.py`
- Test: `tests/agent/test_loop.py`

**Interfaces:**
- Consumes: `ChatClient.chat(messages, tools, tool_choice)`, `ToolRegistry.to_tools_param()`, `ToolRegistry.execute(name, arguments)`
- Produces: `loop.AgentLoop(client, registry, max_iterations=8, system_prompt=SYSTEM_PROMPT)` with `.run(user_message, history=None) -> Answer`; `loop.SYSTEM_PROMPT` sets the persona and personalization rules.
- Produces: `loop.Answer(content: str, tools_used: list[str], citations: list[str])`

- [ ] **Step 1: Write `agent_radar/agent/loop.py`**

```python
"""Self-built ReAct loop: think -> call tools -> observe -> repeat -> answer."""
import json
from dataclasses import dataclass, field

from agent_radar.agent.registry import ToolRegistry
from agent_radar.llm.client import ChatClient

SYSTEM_PROMPT = """你是 AgentRadar,面向程序员的 AI agent 行情与学习方向顾问。

工作方式:
1. 用内置 web_search 实时了解 AI agent 领域的技术趋势、框架热度、行业动态。
2. 回答前先用 read_profile 了解用户背景;若用户在提问中透露了新背景,用 update_profile 记录。
3. 基于用户背景给出个性化、可执行的学习方向/路径建议:分阶段、标优先级、附资源链接。
4. 可用 github_stats 核实具体仓库热度。
5. 涉及事实/数据时在正文中附出来源链接;信息可能过时时明确说明时效。
用简体中文回答,先给结论再展开。"""


@dataclass
class Answer:
    content: str
    tools_used: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)


def _assistant_message(content, tool_calls) -> dict:
    msg: dict = {"role": "assistant"}
    if content:
        msg["content"] = content
    if tool_calls:
        msg["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name,
                          "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
            for tc in tool_calls
        ]
    return msg


class AgentLoop:
    def __init__(self, client: ChatClient, registry: ToolRegistry,
                 max_iterations: int = 8, system_prompt: str = SYSTEM_PROMPT):
        self._client = client
        self._registry = registry
        self._max = max_iterations
        self._system_prompt = system_prompt

    def run(self, user_message: str, history: list[dict] | None = None) -> Answer:
        messages: list[dict] = [{"role": "system", "content": self._system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        for _ in range(self._max):
            resp = self._client.chat(messages, self._registry.to_tools_param())
            messages.append(_assistant_message(resp.content, resp.tool_calls))
            if not resp.tool_calls:
                return Answer(content=resp.content or "", tools_used=tools_used)
            for tc in resp.tool_calls:
                tools_used.append(tc.name)
                result = self._registry.execute(tc.name, tc.arguments)
                messages.append({
                    "role": "tool", "tool_call_id": tc.id, "content": result,
                })

        return Answer(
            content="(达到最大推理轮数,请缩小问题范围后重试。)",
            tools_used=tools_used,
        )
```

- [ ] **Step 2: Write the failing test `tests/agent/test_loop.py`**

```python
from agent_radar.agent.loop import AgentLoop
from agent_radar.agent.registry import ToolRegistry
from agent_radar.llm.client import ChatResponse, ToolCall


class FakeClient:
    """Replays a scripted sequence of ChatResponses."""
    def __init__(self, sequence):
        self._seq = list(sequence)
        self._i = 0

    def chat(self, messages, tools, tool_choice="auto"):
        resp = self._seq[self._i]
        self._i += 1
        return resp


def _resp(content=None, tool_calls=None):
    return ChatResponse(content=content, tool_calls=tool_calls or [])


def _echo_registry():
    reg = ToolRegistry()
    reg.register(
        {"type": "function", "function": {
            "name": "echo", "parameters": {"type": "object", "properties": {}}}},
        lambda **kw: "ECHO",
    )
    return reg


def test_loop_runs_tool_then_answers():
    client = FakeClient([
        _resp(tool_calls=[ToolCall(id="1", name="echo", arguments={})]),
        _resp(content="done"),
    ])
    ans = AgentLoop(client, _echo_registry()).run("hi")
    assert ans.content == "done"
    assert ans.tools_used == ["echo"]


def test_loop_caps_at_max_iterations():
    # Always requests a tool call -> never terminates naturally.
    forever = _resp(tool_calls=[ToolCall(id="1", name="echo", arguments={})])
    client = FakeClient([forever] * 10)
    ans = AgentLoop(client, _echo_registry(), max_iterations=2).run("hi")
    assert "最大" in ans.content
    assert ans.tools_used == ["echo", "echo"]


def test_loop_sends_system_prompt_first():
    seen = {}

    class _C:
        def chat(self, messages, tools, tool_choice="auto"):
            seen["first_role"] = messages[0]["role"]
            seen["first_text"] = messages[0]["content"]
            return ChatResponse(content="ok")

    AgentLoop(_C(), _echo_registry()).run("hi")
    assert seen["first_role"] == "system"
    assert "AgentRadar" in seen["first_text"]
```

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/agent/test_loop.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add agent_radar/agent/loop.py tests/agent/test_loop.py
git commit -m "feat: agent ReAct loop with tool dispatch and iteration cap"
```

---

## Task 7: CLI Wiring + Onboarding

**Files:**
- Create: `agent_radar/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: all prior components.
- Produces: `cli.build_registry(conn, github) -> ToolRegistry`, `cli.onboard_profile(conn) -> None`, `cli.main()`.

- [ ] **Step 1: Write `agent_radar/cli.py`**

```python
"""CLI REPL: wiring, first-run profile onboarding, conversation loop."""
from agent_radar.agent.loop import AgentLoop
from agent_radar.agent.registry import ToolRegistry
from agent_radar.agent.tools import github_stats as gh_tool
from agent_radar.agent.tools import memory as memory_tool
from agent_radar.agent.tools import profile as profile_tool
from agent_radar.config import Config, load_config
from agent_radar.data.github_client import GitHubClient
from agent_radar.llm.client import ZhipuChatClient
from agent_radar.store.db import get_connection, init_db
from agent_radar.store.profile import load_profile, patch_profile


def build_registry(conn, github: GitHubClient) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(gh_tool.SPEC, gh_tool.make_tool(github))
    reg.register(profile_tool.READ_SPEC, profile_tool.make_read_tool(conn))
    reg.register(profile_tool.UPDATE_SPEC, profile_tool.make_update_tool(conn))
    reg.register(memory_tool.READ_SPEC, memory_tool.make_read_tool(conn))
    reg.register(memory_tool.WRITE_SPEC, memory_tool.make_write_tool(conn))
    return reg


def onboard_profile(conn) -> None:
    """Ask a few questions on first run; skip if a role is already set."""
    if load_profile(conn).get("role"):
        return
    print("== 首次使用,简单了解一下你(留空可跳过)==")
    fields = {}
    role = input("你当前的岗位/方向(如 Java 后端、学生): ").strip()
    years = input("经验年限: ").strip()
    goal = input("你想达成的目标(如 转 AI agent): ").strip()
    if role:
        fields["role"] = role
    if years:
        fields["years"] = years
    if goal:
        fields["goal"] = goal
    if fields:
        patch_profile(conn, fields)
        print("已记录你的背景。\n")


def main(config: Config | None = None) -> None:
    config = config or load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    onboard_profile(conn)

    client = ZhipuChatClient(config.zhipu_api_key, model=config.model)
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
        ans = loop.run(user)
        print(f"\nAgentRadar: {ans.content}")
        if ans.tools_used:
            print(f"(使用工具: {', '.join(ans.tools_used)})")
        print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing test `tests/test_cli.py`**

```python
from agent_radar import cli
from agent_radar.data.github_client import GitHubClient
from agent_radar.store.db import init_db
from agent_radar.store.profile import save_profile


def test_build_registry_registers_all_tools(tmp_db):
    init_db(tmp_db)
    reg = cli.build_registry(tmp_db, GitHubClient())
    assert {
        "github_stats", "read_profile", "update_profile",
        "read_memory", "write_memory",
    } <= set(reg.names())


def test_onboard_skips_when_role_exists(tmp_db, monkeypatch):
    init_db(tmp_db)
    save_profile(tmp_db, {"role": "backend"})
    # If onboard prompts, this raises and fails the test.
    monkeypatch.setattr(
        "builtins.input",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not prompt")),
    )
    cli.onboard_profile(tmp_db)
```

- [ ] **Step 3: Run tests, verify pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add agent_radar/cli.py tests/test_cli.py
git commit -m "feat: CLI wiring, first-run onboarding, REPL"
```

---

## Task 8: Integration Test + README

**Files:**
- Create: `tests/test_integration.py`, `README.md`

**Interfaces:**
- Consumes: the full stack via fakes (no real network in CI).

- [ ] **Step 1: Write `tests/test_integration.py`** — a full loop run with a fake model + fake GitHub, asserting the tool result flows into the final answer.

```python
from agent_radar.agent.loop import AgentLoop
from agent_radar.cli import build_registry
from agent_radar.llm.client import ChatResponse, ToolCall
from agent_radar.store.db import init_db


class _FakeGitHub:
    def get_repo(self, owner, repo):
        return {
            "full_name": f"{owner}/{repo}", "stars": 999, "forks": 10,
            "open_issues": 0, "description": "agent framework", "language": "Python",
            "url": f"https://github.com/{owner}/{repo}",
        }


class _ScriptedClient:
    def __init__(self):
        self.turn = 0

    def chat(self, messages, tools, tool_choice="auto"):
        self.turn += 1
        if self.turn == 1:
            return ChatResponse(tool_calls=[
                ToolCall(id="1", name="github_stats",
                         arguments={"repo": "langchain-ai/langchain"}),
            ])
        # Turn 2: assert the tool observation reached the model, then answer.
        assert any(
            m.get("role") == "tool" and "999 stars" in m.get("content", "")
            for m in messages
        ), "tool result not fed back to the model"
        return ChatResponse(content="LangChain 有 999 stars,生态成熟,值得入门。")


def test_full_loop_uses_tool_observation(tmp_db):
    init_db(tmp_db)
    loop = AgentLoop(_ScriptedClient(), build_registry(tmp_db, _FakeGitHub()))
    ans = loop.run("langchain 现在值得学吗?")
    assert "999 stars" in ans.content
    assert ans.tools_used == ["github_stats"]
```

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest -v`
Expected: all tests pass (≈14).

- [ ] **Step 3: Write `README.md`**

````markdown
# AgentRadar

对话式 AI agent:实时追踪 AI agent 领域行情与趋势,并基于你的个人画像给出学习方向建议。

## 能力(MVP)
- 实时联网搜索(智谱 GLM 内置 web_search)
- GitHub 仓库热度查询(`github_stats` 工具)
- 用户画像 + 对话记忆(SQLite 持久化)
- 强个性化学习路径建议

## 安装
```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
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

## 测试
```bash
python -m pytest -v
```

## 架构
单 agent + 多工具(ReAct 循环)。详见 `docs/superpowers/specs/`。
````

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py README.md
git commit -m "test: end-to-end loop with fakes; add README"
```

---

## Definition of Done (MVP)

- `python -m pytest -v` is fully green (no real network required).
- `python -m agent_radar.cli` launches, onboards on first run, and answers a real question using GLM-4's built-in web search (manual smoke test with a valid `ZHIPU_API_KEY`).
- Profile persists across restarts; `/profile` shows it.
- All commits are small and logically scoped.

## Out of Scope (later phases)

- Job-market and industry-news dimensions (Phase 2).
- Multi-agent orchestration, scheduled briefings, web UI (Phase 3).
- Vector-based long-term memory retrieval.
