from agent_radar import cli
from agent_radar.agent.loop import Answer
from agent_radar.config import Config
from agent_radar.data.github_client import GitHubClient
from agent_radar.llm.client import ResilientClient, ZhipuChatClient
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


def test_build_orchestrator_returns_orchestrator():
    from agent_radar.agent.orchestrator import Orchestrator

    class _C:
        def chat(self, m, t, tool_choice="auto"):
            from agent_radar.llm.client import ChatResponse
            return ChatResponse(content="general")

    orch = cli.build_orchestrator(_C(), object())  # registry unused at construction
    assert isinstance(orch, Orchestrator)
