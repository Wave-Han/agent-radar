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
