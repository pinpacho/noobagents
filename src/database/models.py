"""SQLAlchemy models for incident tracking."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IncidentStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    ANALYZING = "analyzing"
    TRIAGED = "triaged"
    TICKET_CREATED = "ticket_created"
    NOTIFIED = "notified"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentModel(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), default=IncidentStatus.SUBMITTED
    )

    # Reporter info
    reporter_email: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attachment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Triage results
    severity: Mapped[str | None] = mapped_column(String(4), nullable=True)
    affected_service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    triage_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_team: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Ticket info
    ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Notifications
    notifications_sent: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Resolution
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timeline
    timeline: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def add_timeline_event(self, event: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        if self.timeline is None:
            self.timeline = []
        self.timeline = [*self.timeline, {"timestamp": ts, "event": event}]
