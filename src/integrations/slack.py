"""Slack notification integration.

Uses a real webhook URL when configured; otherwise falls back to a
mock implementation that logs the message.
"""

from __future__ import annotations

import logging

import httpx

from src.config import get_settings
from src.integrations.base import NotificationResult, NotificationService

logger = logging.getLogger(__name__)


class SlackNotificationService(NotificationService):
    """Posts messages to Slack via incoming webhook."""

    async def send(
        self,
        *,
        recipient: str,  # channel name, e.g. "#incidents"
        subject: str,
        body: str,
    ) -> NotificationResult:
        settings = get_settings()
        webhook_url = settings.slack_webhook_url

        payload = {
            "channel": recipient,
            "username": "SRE Triage Agent",
            "icon_emoji": ":rotating_light:",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": subject},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": body},
                },
            ],
        }

        if not webhook_url:
            # Mock mode
            logger.info(
                "[MOCK] Slack notification",
                extra={"channel": recipient, "subject": subject, "body": body[:200]},
            )
            return NotificationResult(
                channel="slack",
                success=True,
                message=f"[MOCK] Sent to {recipient}",
                recipient=recipient,
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
            logger.info("Slack notification sent", extra={"channel": recipient})
            return NotificationResult(
                channel="slack",
                success=True,
                message="Sent",
                recipient=recipient,
            )
        except Exception as exc:
            logger.error(
                "Slack notification failed",
                extra={"channel": recipient, "error": str(exc)},
            )
            return NotificationResult(
                channel="slack",
                success=False,
                message=str(exc),
                recipient=recipient,
            )
