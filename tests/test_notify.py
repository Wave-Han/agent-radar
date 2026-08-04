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
