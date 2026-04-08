"""FastAPI dependency-injection helpers."""

from __future__ import annotations

from src.integrations.email import EmailNotificationService
from src.integrations.slack import SlackNotificationService
from src.integrations.ticketing import MockJiraService


def get_ticketing_service() -> MockJiraService:
    return MockJiraService()


def get_slack_service() -> SlackNotificationService:
    return SlackNotificationService()


def get_email_service() -> EmailNotificationService:
    return EmailNotificationService()
