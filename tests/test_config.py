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
