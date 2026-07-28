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
