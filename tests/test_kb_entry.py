import pytest


def test_kb_main_requires_docs_kb_dir(monkeypatch, tmp_path, tmp_db):
    import agent_radar.kb as kb_mod
    from agent_radar.config import Config

    monkeypatch.chdir(tmp_path)  # no docs_kb/ here
    monkeypatch.setattr(
        kb_mod, "load_config",
        lambda *a, **k: Config(
            zhipu_api_key="k", github_token=None, model="m",
            db_path=str(tmp_path / "t.db"),
        ),
    )
    monkeypatch.setattr(kb_mod, "get_connection", lambda p: tmp_db)
    with pytest.raises(SystemExit):
        kb_mod.main()


def test_kb_main_ingests_and_prints(monkeypatch, tmp_path, tmp_db, capsys):
    import agent_radar.kb as kb_mod
    from agent_radar.config import Config

    (tmp_path / "docs_kb").mkdir()
    (tmp_path / "docs_kb" / "a.md").write_text("## 甲\n内容", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    class _FakeEmbedder:
        def embed(self, text):
            return [1.0, 0.0]

    monkeypatch.setattr(
        kb_mod, "load_config",
        lambda *a, **k: Config(
            zhipu_api_key="k", github_token=None, model="m",
            db_path=str(tmp_path / "t.db"),
        ),
    )
    monkeypatch.setattr(kb_mod, "get_connection", lambda p: tmp_db)
    monkeypatch.setattr(
        "agent_radar.llm.client.ZhipuEmbeddingClient",
        lambda api_key: _FakeEmbedder(),
    )
    kb_mod.main()
    out = capsys.readouterr().out
    assert "1 个块" in out
