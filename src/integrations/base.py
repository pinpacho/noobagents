"""Abstract interfaces for integrations — enables easy swapping between
mock and real implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Ticket:
    id: str
    url: str
    summary: str
    description: str
    priority: str
    status: str
    assignee_team: str
    labels: list[str]


@dataclass
class NotificationResult:
    channel: str  # "slack", "email"
    success: bool
    message: str
    recipient: str = ""


class TicketingService(ABC):
    @abstractmethod
    async def create_ticket(
        self,
        *,
        summary: str,
        description: str,
        priority: str,
        assignee_team: str,
        labels: list[str] | None = None,
    ) -> Ticket: ...

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Ticket | None: ...

    @abstractmethod
    async def update_ticket(self, ticket_id: str, **fields) -> Ticket | None: ...


class NotificationService(ABC):
    @abstractmethod
    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
    ) -> NotificationResult: ...
