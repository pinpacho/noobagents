"""Mock Jira ticketing integration.

Stores tickets in-memory for the demo.  Follows the same interface as
a real Jira/Linear SDK so it can be swapped without code changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.integrations.base import Ticket, TicketingService

logger = logging.getLogger(__name__)

# In-memory ticket store (reset on restart — fine for demo)
_TICKET_STORE: dict[str, Ticket] = {}
_COUNTER = 0


def _next_key() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"SRE-{_COUNTER:04d}"


class MockJiraService(TicketingService):
    """Mocked Jira/Linear service that stores tickets in memory."""

    async def create_ticket(
        self,
        *,
        summary: str,
        description: str,
        priority: str,
        assignee_team: str,
        labels: list[str] | None = None,
    ) -> Ticket:
        ticket_id = _next_key()
        ticket = Ticket(
            id=ticket_id,
            url=f"https://jira.example.com/browse/{ticket_id}",
            summary=summary,
            description=description,
            priority=priority,
            status="Open",
            assignee_team=assignee_team,
            labels=labels or [],
        )
        _TICKET_STORE[ticket_id] = ticket
        logger.info(
            "Ticket created",
            extra={
                "ticket_id": ticket_id,
                "priority": priority,
                "team": assignee_team,
            },
        )
        return ticket

    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        return _TICKET_STORE.get(ticket_id)

    async def update_ticket(self, ticket_id: str, **fields) -> Ticket | None:
        ticket = _TICKET_STORE.get(ticket_id)
        if ticket is None:
            return None
        for k, v in fields.items():
            if hasattr(ticket, k):
                setattr(ticket, k, v)
        logger.info("Ticket updated", extra={"ticket_id": ticket_id, **fields})
        return ticket
