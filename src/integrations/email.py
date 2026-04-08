"""Email notification integration.

Uses real SMTP when configured; otherwise logs the email content.
"""

from __future__ import annotations

import logging
from email.mime.text import MIMEText

import aiosmtplib

from src.config import get_settings
from src.integrations.base import NotificationResult, NotificationService

logger = logging.getLogger(__name__)


class EmailNotificationService(NotificationService):
    """Sends email via SMTP (real or mock)."""

    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
    ) -> NotificationResult:
        settings = get_settings()

        if not settings.smtp_host:
            logger.info(
                "[MOCK] Email notification",
                extra={"to": recipient, "subject": subject, "body": body[:200]},
            )
            return NotificationResult(
                channel="email",
                success=True,
                message=f"[MOCK] Email to {recipient}",
                recipient=recipient,
            )

        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email
        msg["To"] = recipient

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=True,
            )
            logger.info("Email sent", extra={"to": recipient, "subject": subject})
            return NotificationResult(
                channel="email",
                success=True,
                message="Sent",
                recipient=recipient,
            )
        except Exception as exc:
            logger.error(
                "Email send failed",
                extra={"to": recipient, "error": str(exc)},
            )
            return NotificationResult(
                channel="email",
                success=False,
                message=str(exc),
                recipient=recipient,
            )
