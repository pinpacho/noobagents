"""Pydantic request / response models for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Requests ────────────────────────────────────────────────────────────────

class IncidentSubmitRequest(BaseModel):
    description: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Detailed description of the incident",
    )
    reporter_email: EmailStr = Field(
        ..., description="Email of the person reporting the incident"
    )


class IncidentResolveRequest(BaseModel):
    resolution: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Description of how the incident was resolved",
    )


# ── Responses ───────────────────────────────────────────────────────────────

class IncidentResponse(BaseModel):
    id: str
    status: str
    reporter_email: str
    description: str
    severity: str | None = None
    affected_service: str | None = None
    triage_summary: str | None = None
    root_cause_hypothesis: str | None = None
    recommended_team: str | None = None
    confidence: float | None = None
    ticket_id: str | None = None
    ticket_url: str | None = None
    notifications_sent: dict | None = None
    resolution: str | None = None
    timeline: list[dict] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class IncidentSubmitResponse(BaseModel):
    incident_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
