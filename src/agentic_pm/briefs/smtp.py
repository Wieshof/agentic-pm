"""Send briefs via SMTP. Settings come from the environment only.

AGENT_PM_SMTP_HOST, AGENT_PM_SMTP_PORT (default 587), AGENT_PM_SMTP_USER,
AGENT_PM_SMTP_PASSWORD, AGENT_PM_SMTP_FROM. STARTTLS is used unless
AGENT_PM_SMTP_STARTTLS=0.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class SMTPConfigError(ValueError):
    pass


def sender_address(env: dict[str, str] | None = None) -> str:
    env = dict(os.environ) if env is None else env
    return env.get("AGENT_PM_SMTP_FROM", "agent-pm@localhost")


def send(msg: EmailMessage, env: dict[str, str] | None = None) -> None:
    env = dict(os.environ) if env is None else env
    host = env.get("AGENT_PM_SMTP_HOST")
    if not host:
        raise SMTPConfigError("AGENT_PM_SMTP_HOST is not set")
    port = int(env.get("AGENT_PM_SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if env.get("AGENT_PM_SMTP_STARTTLS", "1") != "0":
            smtp.starttls()
        if user := env.get("AGENT_PM_SMTP_USER"):
            smtp.login(user, env.get("AGENT_PM_SMTP_PASSWORD", ""))
        smtp.send_message(msg)
