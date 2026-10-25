"""Notification e-mail through SMTP; the standard library client runs in a thread so the worker stays async."""

import asyncio
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings

SENDER_NAME = "SmartAzMİU"


class MailUnavailableError(Exception):
    """The SMTP server could not be reached or refused the message for now; retry later."""


class Mailer(Protocol):
    async def send(self, to: str, subject: str, text: str) -> None: ...


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, to: str, subject: str, text: str) -> None:
        message = EmailMessage()
        username, _, domain = self.settings.mail_from.partition("@")
        message["From"] = Address(SENDER_NAME, username, domain)
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        await asyncio.to_thread(self._deliver, message)

    def _deliver(self, message: EmailMessage) -> None:
        settings = self.settings
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailUnavailableError(type(exc).__name__) from exc
