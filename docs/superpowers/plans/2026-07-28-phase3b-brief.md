# Phase 3b (Brief + Email) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `python -m agent_radar.brief` that runs the trend/jobs/industry experts into a combined weekly brief and emails it via SMTP (or prints it if SMTP is unconfigured).

**Architecture:** New `notify.py` (`smtplib` sender) + `brief.py` (`generate_brief` reuses `EXPERT_PROMPTS` + `AgentLoop` + shared client/registry; `main` wires it). Config gains optional SMTP fields. No new dependencies (stdlib `smtplib`).

**Tech Stack:** Python 3.11+, stdlib `smtplib`/`email`, pytest.

## Global Constraints

- Python 3.11+.
- **No new dependencies** — use stdlib `smtplib` + `email.message`.
- Brief reuses existing experts (`EXPERT_PROMPTS` + `AgentLoop` + `ResilientClient` + `registry`); `AgentLoop` is not modified.
- Brief covers **trend + jobs + industry only** (no `learning`).
- No SMTP config → **print only, do not send**.
- `send_email` must **not raise** on failure — return `False` (email failures must not crash the brief).
- Code identifiers/comments in English; user-facing strings (prompts, prints) in Chinese.
- TDD: failing test first → minimal impl → green → commit — one commit per task.
- All tests mock the network — no real SMTP or model calls.

---

## Task 1: SMTP config fields

**Files:**
- Modify: `agent_radar/config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` gains `smtp_host: str | None`, `smtp_port: int = 0`, `smtp_user: str | None`, `smtp_pass: str | None`, `email_to: str | None`; `load_config()` reads `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `EMAIL_TO`.

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
    smtp_host: str | None = None
    smtp_port: int = 0
    smtp_user: str | None = None
    smtp_pass: str | None = None
    email_to: str | None = None


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
        smtp_host=os.environ.get("SMTP_HOST") or None,
        smtp_port=int(os.environ.get("SMTP_PORT", "0") or "0"),
        smtp_user=os.environ.get("SMTP_USER") or None,
        smtp_pass=os.environ.get("SMTP_PASS") or None,
        email_to=os.environ.get("EMAIL_TO") or None,
    )
```

- [ ] **Step 2: Replace `.env.example` with**

```
ZHIPU_API_KEY=your_zhipu_api_key_here
GITHUB_TOKEN=optional_for_higher_github_rate_limit
AGENT_RADAR_MODEL=glm-4
AGENT_RADAR_DB_PATH=agent_radar.db
AGENT_RADAR_MAX_ITERATIONS=8
DEEPSEEK_API_KEY=optional_for_auto_fallback_when_glm_fails
AGENT_RADAR_DEEPSEEK_MODEL=deepseek-chat
# Email brief (optional) — leave blank to just print the brief instead
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your_email@qq.com
SMTP_PASS=your_smtp_authorization_code
EMAIL_TO=recipient@example.com
```

- [ ] **Step 3: Append tests to `tests/test_config.py`**

```python
def test_load_config_reads_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "u@q.com")
    monkeypatch.setenv("SMTP_PASS", "pass")
    monkeypatch.setenv("EMAIL_TO", "to@x.com")
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.smtp_host == "smtp.qq.com"
    assert cfg.smtp_port == 465
    assert cfg.smtp_user == "u@q.com"
    assert cfg.smtp_pass == "pass"
    assert cfg.email_to == "to@x.com"


def test_load_config_smtp_defaults_none(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.smtp_host is None
    assert cfg.smtp_port == 0
    assert cfg.email_to is None
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 5 passed (3 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add agent_radar/config.py .env.example tests/test_config.py
git commit -m "feat: SMTP config fields for email brief"
```

---

## Task 2: Email notifier (`notify.py`)

**Files:**
- Create: `agent_radar/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `Config` (smtp_host/port/user/pass, email_to).
- Produces: `send_email(subject: str, body: str, config: Config) -> bool`. Returns `False` (no raise) when unconfigured or on any SMTP error.

- [ ] **Step 1: Write the failing test `tests/test_notify.py`**

```python
from unittest.mock import MagicMock, patch

from agent_radar.config import Config
from agent_radar.notify import send_email


def _cfg(host="smtp.qq.com", port=465, user="u@q.com", password="p", to="to@x.com"):
    return Config(
        zhipu_api_key="x", github_token=None, model="glm-4", db_path="x.db",
        smtp_host=host, smtp_port=port, smtp_user=user, smtp_pass=password, email_to=to,
    )


def test_send_email_returns_false_when_unconfigured():
    cfg = Config(zhipu_api_key="x", github_token=None, model="glm-4", db_path="x.db")
    assert send_email("s", "b", cfg) is False


def test_send_email_success_calls_smtp():
    fake_server = MagicMock()
    fake_server.__enter__ = MagicMock(return_value=fake_server)
    fake_server.__exit__ = MagicMock(return_value=None)
    with patch("agent_radar.notify.smtplib.SMTP_SSL", return_value=fake_server) as mock_smtp:
        ok = send_email("subj", "body", _cfg())
    assert ok is True
    assert mock_smtp.call_args.args[0] == "smtp.qq.com"
    fake_server.login.assert_called_once_with("u@q.com", "p")
    fake_server.send_message.assert_called_once()
    sent_msg = fake_server.send_message.call_args.args[0]
    assert sent_msg["Subject"] == "subj"
    assert sent_msg["From"] == "u@q.com"
    assert sent_msg["To"] == "to@x.com"


def test_send_email_returns_false_on_exception():
    with patch("agent_radar.notify.smtplib.SMTP_SSL", side_effect=RuntimeError("boom")):
        ok = send_email("s", "b", _cfg())
    assert ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_radar.notify'`.

- [ ] **Step 3: Write `agent_radar/notify.py`**

```python
"""Email notification via SMTP (standard library smtplib)."""
import smtplib
import ssl
from email.message import EmailMessage

from agent_radar.config import Config


def send_email(subject: str, body: str, config: Config) -> bool:
    """Send an email. Returns True on success, False if unconfigured or on error."""
    if not (config.smtp_host and config.smtp_user and config.smtp_pass and config.email_to):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.smtp_user
    msg["To"] = config.email_to
    msg.set_content(body)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            config.smtp_host, config.smtp_port or 465, context=context, timeout=30
        ) as server:
            server.login(config.smtp_user, config.smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001 - email failure must not crash the brief
        print(f"邮件发送失败: {e}")
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_notify.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_radar/notify.py tests/test_notify.py
git commit -m "feat: SMTP email notifier (stdlib smtplib)"
```

---

## Task 3: Brief generator + entrypoint (`brief.py`)

**Files:**
- Create: `agent_radar/brief.py`
- Test: `tests/test_brief.py`

**Interfaces:**
- Consumes: `EXPERT_PROMPTS` (from `agent.experts`), `AgentLoop(client, registry, max_iterations, system_prompt).run(question)`, `Config`, `send_email`.
- Produces: `REPORT_DIMS`, `generate_brief(client, registry, max_iterations=8) -> str`, `main(config=None)`.

- [ ] **Step 1: Write the failing test `tests/test_brief.py`**

```python
from agent_radar.agent.experts import EXPERT_PROMPTS
from agent_radar.agent.registry import ToolRegistry
from agent_radar.brief import REPORT_DIMS, _is_smtp_configured, generate_brief
from agent_radar.config import Config
from agent_radar.llm.client import ChatResponse


class _SectionClient:
    """Returns a canned answer per expert turn, recording each system prompt."""
    def __init__(self):
        self.systems = []
        self._replies = iter(["趋势段", "就业段", "行业段"])

    def chat(self, messages, tools, tool_choice="auto"):
        self.systems.append(messages[0]["content"])
        return ChatResponse(content=next(self._replies))


def test_report_dims_are_three_expected():
    assert [d for d, _ in REPORT_DIMS] == ["trend", "jobs", "industry"]


def test_generate_brief_has_header_and_three_sections():
    brief = generate_brief(_SectionClient(), ToolRegistry())
    assert brief.startswith("# AgentRadar 周报")
    assert "## 技术趋势" in brief
    assert "## 就业行情" in brief
    assert "## 行业动态" in brief
    assert "趋势段" in brief and "就业段" in brief and "行业段" in brief


def test_generate_brief_uses_each_expert_prompt_in_order():
    client = _SectionClient()
    generate_brief(client, ToolRegistry())
    assert client.systems == [
        EXPERT_PROMPTS["trend"],
        EXPERT_PROMPTS["jobs"],
        EXPERT_PROMPTS["industry"],
    ]


def test_is_smtp_configured():
    full = Config(
        zhipu_api_key="x", github_token=None, model="m", db_path="d",
        smtp_host="h", smtp_port=465, smtp_user="u", smtp_pass="p", email_to="t",
    )
    empty = Config(zhipu_api_key="x", github_token=None, model="m", db_path="d")
    assert _is_smtp_configured(full) is True
    assert _is_smtp_configured(empty) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_brief.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_radar.brief'`.

- [ ] **Step 3: Write `agent_radar/brief.py`**

```python
"""Generate a trend+jobs+industry brief and (optionally) email it."""
from agent_radar.agent.experts import EXPERT_PROMPTS
from agent_radar.agent.loop import AgentLoop, Answer
from agent_radar.config import Config, load_config
from agent_radar.notify import send_email

REPORT_DIMS = [("trend", "技术趋势"), ("jobs", "就业行情"), ("industry", "行业动态")]

_BRIEF_QUESTION = (
    "请用 3-5 条要点,生成本周 AI agent 领域{title}的最新简报,"
    "附关键来源链接与时效说明。"
)


def generate_brief(client, registry, max_iterations: int = 8) -> str:
    """Run trend/jobs/industry experts and assemble a combined brief."""
    sections = []
    for dim, title in REPORT_DIMS:
        expert = AgentLoop(
            client,
            registry,
            max_iterations=max_iterations,
            system_prompt=EXPERT_PROMPTS[dim],
        )
        ans: Answer = expert.run(_BRIEF_QUESTION.format(title=title))
        sections.append(f"## {title}\n\n{ans.content}")
    header = "# AgentRadar 周报\n\nAI agent 领域本周趋势 / 就业 / 行业简报。"
    return header + "\n\n" + "\n\n".join(sections)


def _is_smtp_configured(config: Config) -> bool:
    return bool(
        config.smtp_host
        and config.smtp_user
        and config.smtp_pass
        and config.email_to
    )


def main(config: Config | None = None) -> None:
    # Lazy imports to keep `brief` importable without pulling the full CLI graph.
    from agent_radar.cli import build_client, build_registry
    from agent_radar.data.github_client import GitHubClient
    from agent_radar.store.db import get_connection, init_db

    config = config or load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))

    print("生成简报中(可能需要几十秒)...")
    brief = generate_brief(client, registry, max_iterations=config.max_iterations)

    if _is_smtp_configured(config):
        ok = send_email("AgentRadar 周报", brief, config)
        if ok:
            print("已发送邮件。")
        else:
            print("邮件发送失败,简报见下:")
            print(brief)
    else:
        print("未配置 SMTP,简报如下:\n")
        print(brief)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 55 passed (46 existing + 2 Task 1 + 3 Task 2 + 4 Task 3), all green, no failures.

- [ ] **Step 5: Commit**

```bash
git add agent_radar/brief.py tests/test_brief.py
git commit -m "feat: weekly brief generator + entrypoint"
```

---

## Definition of Done

- `python -m pytest -v` fully green (55 passed); no real network calls.
- `generate_brief` runs trend/jobs/industry experts in order, each with its expert prompt, and assembles a `# AgentRadar 周报` document.
- `send_email` returns `True`/`False` and never raises; succeeds through mocked SMTP.
- With SMTP configured: `main` emails the brief; without: prints it.
- Manual smoke test (GLM + SMTP keys): `python -m agent_radar.brief` produces a real brief and sends it.

## Out of Scope

- Scheduled/cron triggering (manual run; schedule via OS task scheduler).
- Other channels (WeChat / Feishu / DingTalk).
- Web UI (Phase 3c).
- `learning` section in the brief.
