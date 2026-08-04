from agent_radar.config import load_config


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    monkeypatch.setenv("GITHUB_TOKEN", "g")
    monkeypatch.setenv("AGENT_RADAR_MODEL", "glm-4-plus")
    cfg = load_config(env_file="/does/not/exist")
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
