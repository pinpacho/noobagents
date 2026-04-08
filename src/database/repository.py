"""Data-access layer for incidents – thin wrapper over SQLAlchemy async."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.database.models import Base, IncidentModel, IncidentStatus

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Create the engine, session factory, and tables (if needed)."""
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    assert _session_factory is not None, "Database not initialised – call init_db() first"
    return _session_factory


def generate_incident_id() -> str:
    return uuid.uuid4().hex[:16]


# ── CRUD ────────────────────────────────────────────────────────────────────

async def create_incident(
    *,
    reporter_email: str,
    description: str,
    attachment_path: str | None = None,
    attachment_type: str | None = None,
) -> IncidentModel:
    factory = _get_session_factory()
    incident = IncidentModel(
        id=generate_incident_id(),
        reporter_email=reporter_email,
        description=description,
        attachment_path=attachment_path,
        attachment_type=attachment_type,
        status=IncidentStatus.SUBMITTED,
        timeline=[],
    )
    incident.add_timeline_event("Incident submitted")
    async with factory() as session:
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
    return incident


async def get_incident(incident_id: str) -> IncidentModel | None:
    factory = _get_session_factory()
    async with factory() as session:
        return await session.get(IncidentModel, incident_id)


async def update_incident(incident_id: str, **fields) -> IncidentModel | None:
    factory = _get_session_factory()
    async with factory() as session:
        incident = await session.get(IncidentModel, incident_id)
        if incident is None:
            return None
        for key, value in fields.items():
            setattr(incident, key, value)
        incident.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(incident)
        return incident


async def add_timeline_event(incident_id: str, event: str) -> None:
    factory = _get_session_factory()
    async with factory() as session:
        incident = await session.get(IncidentModel, incident_id)
        if incident:
            incident.add_timeline_event(event)
            await session.commit()


async def resolve_incident(incident_id: str, resolution: str) -> IncidentModel | None:
    factory = _get_session_factory()
    async with factory() as session:
        incident = await session.get(IncidentModel, incident_id)
        if incident is None:
            return None
        incident.status = IncidentStatus.RESOLVED
        incident.resolution = resolution
        incident.resolved_at = datetime.now(timezone.utc)
        incident.add_timeline_event(f"Resolved: {resolution}")
        await session.commit()
        await session.refresh(incident)
        return incident


async def list_incidents(
    *,
    status: IncidentStatus | None = None,
    limit: int = 50,
) -> list[IncidentModel]:
    factory = _get_session_factory()
    async with factory() as session:
        stmt = select(IncidentModel).order_by(IncidentModel.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(IncidentModel.status == status)
        result = await session.execute(stmt)
        return list(result.scalars().all())
