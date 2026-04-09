"""FastAPI route definitions for the SRE NOOBS Agent."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from src.agent.triage_agent import run_triage
from src.api.models import (
    HealthResponse,
    IncidentResolveRequest,
    IncidentResponse,
    IncidentSubmitResponse,
)
from src.config import get_settings
from src.database.models import IncidentStatus
from src.database.repository import (
    add_timeline_event,
    create_incident,
    get_incident,
    list_incidents,
    resolve_incident,
    update_incident,
)
from src.integrations.email import EmailNotificationService
from src.integrations.slack import SlackNotificationService
from src.integrations.storage import save_upload
from src.integrations.ticketing import MockJiraService
from src.middleware.guardrails import PromptInjectionDetector, sanitise_text
from src.middleware.validation import validate_upload
from src.observability.metrics import incident_submissions_total, notifications_total
from src.observability.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

router = APIRouter()

_injection_detector = PromptInjectionDetector()
_ticketing = MockJiraService()
_slack = SlackNotificationService()
_email = EmailNotificationService()


# ── Health ──────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        service=settings.app_name,
    )


# ── Submit Incident ─────────────────────────────────────────────────────────

@router.post(
    "/incidents/submit",
    response_model=IncidentSubmitResponse,
    status_code=201,
    tags=["Incidents"],
)
async def submit_incident(
    background_tasks: BackgroundTasks,
    description: str = Form(..., min_length=20, max_length=5000),
    reporter_email: str = Form(...),
    file: UploadFile | None = File(None),
):
    """Submit an incident report for automated triage.

    Accepts a text description and an optional attachment (image or log file).
    Triage runs asynchronously; poll ``GET /incidents/{id}`` for results.
    """
    with tracer.start_as_current_span("api.submit_incident") as span:
        # ── Guardrails ──
        settings = get_settings()
        if settings.enable_prompt_injection_detection:
            is_safe, patterns = _injection_detector.scan(description)
            if not is_safe:
                incident_submissions_total.labels(status="rejected_injection").inc()
                raise HTTPException(
                    status_code=400,
                    detail=f"Input contains suspicious patterns and was rejected. Matched: {patterns}",
                )

        description = sanitise_text(description)

        # ── File upload ──
        file = await validate_upload(file)
        attachment_path: str | None = None
        attachment_type: str | None = None
        if file:
            attachment_path, attachment_type = await save_upload(file)

        # ── Persist ──
        incident = await create_incident(
            reporter_email=reporter_email,
            description=description,
            attachment_path=attachment_path,
            attachment_type=attachment_type,
        )
        span.set_attribute("incident_id", incident.id)
        incident_submissions_total.labels(status="accepted").inc()

        # ── Kick off triage in background ──
        background_tasks.add_task(
            _run_triage_pipeline,
            incident.id,
            description,
            attachment_path,
            attachment_type,
        )

        return IncidentSubmitResponse(
            incident_id=incident.id,
            status=incident.status.value,
            message="Incident received — triage is running in the background.",
        )


# ── Get Incident ────────────────────────────────────────────────────────────

@router.get("/incidents/{incident_id}", response_model=IncidentResponse, tags=["Incidents"])
async def get_incident_details(incident_id: str):
    incident = await get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse.model_validate(incident)


# ── List Incidents ──────────────────────────────────────────────────────────

@router.get("/incidents", response_model=list[IncidentResponse], tags=["Incidents"])
async def list_all_incidents(limit: int = 50):
    incidents = await list_incidents(limit=limit)
    return [IncidentResponse.model_validate(i) for i in incidents]


# ── Resolve Incident ────────────────────────────────────────────────────────

@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=IncidentResponse,
    tags=["Incidents"],
)
async def resolve_incident_endpoint(incident_id: str, body: IncidentResolveRequest):
    """Mark an incident as resolved and notify the original reporter."""
    with tracer.start_as_current_span("api.resolve_incident") as span:
        span.set_attribute("incident_id", incident_id)

        incident = await resolve_incident(incident_id, body.resolution)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Notify the reporter
        email_result = await _email.send(
            recipient=incident.reporter_email,
            subject=f"[Resolved] Incident {incident_id}",
            body=(
                f"Your reported incident has been resolved.\n\n"
                f"Resolution: {body.resolution}\n\n"
                f"Ticket: {incident.ticket_url or 'N/A'}"
            ),
        )
        notifications_total.labels(channel="email", status="success" if email_result.success else "failure").inc()

        await add_timeline_event(incident_id, f"Reporter notified of resolution via email ({email_result.message})")

        # Refresh and return
        incident = await get_incident(incident_id)
        return IncidentResponse.model_validate(incident)


# ── Background triage pipeline ──────────────────────────────────────────────

async def _run_triage_pipeline(
    incident_id: str,
    description: str,
    attachment_path: str | None,
    attachment_type: str | None,
) -> None:
    """Full background pipeline: triage → ticket → notify."""
    try:
        await update_incident(incident_id, status=IncidentStatus.ANALYZING)
        await add_timeline_event(incident_id, "Triage started")

        # 1. Run the AI NOOBS Agent
        triage = await run_triage(
            incident_id=incident_id,
            description=description,
            attachment_path=attachment_path,
            attachment_type=attachment_type,
        )

        await update_incident(
            incident_id,
            status=IncidentStatus.TRIAGED,
            severity=triage.severity,
            affected_service=triage.affected_service,
            triage_summary=triage.summary,
            root_cause_hypothesis=triage.root_cause_hypothesis,
            recommended_team=triage.recommended_team,
            confidence=triage.confidence,
        )
        await add_timeline_event(
            incident_id,
            f"Triaged as {triage.severity} — {triage.affected_service} — confidence {triage.confidence:.0%}",
        )

        # 2. Create ticket
        ticket = await _ticketing.create_ticket(
            summary=f"[{triage.severity}] {triage.summary[:120]}",
            description=(
                f"**Incident:** {incident_id}\n"
                f"**Severity:** {triage.severity}\n"
                f"**Service:** {triage.affected_service}\n"
                f"**Root cause:** {triage.root_cause_hypothesis}\n\n"
                f"**Mitigation steps:**\n"
                + "\n".join(f"- {s}" for s in triage.mitigation_steps)
            ),
            priority=triage.severity,
            assignee_team=triage.recommended_team,
            labels=["auto-triage", triage.affected_service],
        )
        await update_incident(
            incident_id,
            status=IncidentStatus.TICKET_CREATED,
            ticket_id=ticket.id,
            ticket_url=ticket.url,
        )
        await add_timeline_event(incident_id, f"Ticket created: {ticket.id}")

        # 3. Notify team
        notification_body = (
            f"*Incident:* `{incident_id}`\n"
            f"*Severity:* {triage.severity}\n"
            f"*Service:* {triage.affected_service}\n"
            f"*Summary:* {triage.summary}\n"
            f"*Ticket:* {ticket.url}"
        )

        slack_result = await _slack.send(
            recipient="#incidents",
            subject=f"[{triage.severity}] New Incident: {incident_id}",
            body=notification_body,
        )
        notifications_total.labels(
            channel="slack", status="success" if slack_result.success else "failure"
        ).inc()

        email_result = await _email.send(
            recipient=f"oncall-{triage.recommended_team.lower().replace(' ', '-')}@example.com",
            subject=f"[{triage.severity}] Incident {incident_id}: {triage.summary[:80]}",
            body=notification_body,
        )
        notifications_total.labels(
            channel="email", status="success" if email_result.success else "failure"
        ).inc()

        await update_incident(
            incident_id,
            status=IncidentStatus.NOTIFIED,
            notifications_sent={
                "slack": {"success": slack_result.success, "message": slack_result.message},
                "email": {"success": email_result.success, "message": email_result.message},
            },
        )
        await add_timeline_event(incident_id, "Team notified via Slack and email")

    except Exception:
        logger.exception("Triage pipeline failed for %s", incident_id)
        await add_timeline_event(incident_id, "Triage pipeline failed — see server logs")
        await update_incident(incident_id, status=IncidentStatus.SUBMITTED)
