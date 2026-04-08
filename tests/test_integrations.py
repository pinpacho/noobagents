"""Test mock integrations (ticketing, notifications)."""

from __future__ import annotations

import pytest

from src.integrations.ticketing import MockJiraService
from src.integrations.email import EmailNotificationService
from src.integrations.slack import SlackNotificationService


@pytest.mark.asyncio
async def test_mock_jira_create():
    svc = MockJiraService()
    ticket = await svc.create_ticket(
        summary="[P0] Payment gateway down",
        description="All transactions failing",
        priority="P0",
        assignee_team="Payments Team",
        labels=["auto-triage", "payment"],
    )
    assert ticket.id.startswith("SRE-")
    assert ticket.priority == "P0"
    assert ticket.status == "Open"


@pytest.mark.asyncio
async def test_mock_jira_get():
    svc = MockJiraService()
    ticket = await svc.create_ticket(
        summary="Test", description="Test", priority="P2",
        assignee_team="Platform Team",
    )
    fetched = await svc.get_ticket(ticket.id)
    assert fetched is not None
    assert fetched.id == ticket.id


@pytest.mark.asyncio
async def test_mock_jira_update():
    svc = MockJiraService()
    ticket = await svc.create_ticket(
        summary="Test", description="Test", priority="P2",
        assignee_team="Platform Team",
    )
    updated = await svc.update_ticket(ticket.id, status="Resolved")
    assert updated.status == "Resolved"


@pytest.mark.asyncio
async def test_email_mock_mode():
    """When SMTP is not configured, email should succeed in mock mode."""
    svc = EmailNotificationService()
    result = await svc.send(
        recipient="oncall@example.com",
        subject="Test incident",
        body="Some body text",
    )
    assert result.success is True
    assert "MOCK" in result.message


@pytest.mark.asyncio
async def test_slack_mock_mode():
    """When webhook URL is not configured, Slack should succeed in mock mode."""
    svc = SlackNotificationService()
    result = await svc.send(
        recipient="#incidents",
        subject="Test incident",
        body="Some body text",
    )
    assert result.success is True
    assert "MOCK" in result.message
