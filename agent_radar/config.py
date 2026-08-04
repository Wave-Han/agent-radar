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
