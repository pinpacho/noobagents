"""Pydantic models representing triage results (structured agent output)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """Structured output produced by the NOOBS Agent."""

    severity: str = Field(
        description="Severity level: P0 | P1 | P2 | P3 | P4"
    )
    affected_service: str = Field(
        description="Primary eShop service affected (catalog, basket, ordering, payment, identity)"
    )
    summary: str = Field(
        description="One-paragraph technical summary of the incident"
    )
    root_cause_hypothesis: str = Field(
        description="Best-guess root cause based on available evidence"
    )
    recommended_team: str = Field(
        description="Team that should handle this incident"
    )
    mitigation_steps: list[str] = Field(
        description="Ordered list of immediate actions the on-call team should take"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Agent's confidence in the assessment (0.0–1.0)",
    )
    user_impact: str = Field(
        default="Unknown",
        description="Estimated user impact — e.g. 'All checkout attempts failing'",
    )
