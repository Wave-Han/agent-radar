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
