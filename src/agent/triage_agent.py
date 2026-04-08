"""Core SRE Triage Agent built with Pydantic AI.

Uses Gemini 2.0 Flash for orchestration and fast triage, with optional
escalation to Claude Sonnet for complex log/image analysis.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache

from pydantic_ai import Agent, RunContext

from src.agent.prompts import TRIAGE_SYSTEM_PROMPT
from src.agent.state import TriageResult
from src.config import get_settings
from src.knowledge.ecommerce_context import ESHOP_SERVICES, lookup_service
from src.knowledge.severity_rules import SEVERITY_RULES, rule_based_severity_hint
from src.observability.metrics import (
    incidents_by_severity,
    llm_calls_total,
    triage_duration_seconds,
)
from src.observability.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


# ── Dependency container passed to every tool call ─────────────────────────

@dataclass
class TriageDeps:
    """Runtime dependencies injected into every tool call."""

    incident_id: str
    description: str
    attachment_path: str | None = None
    attachment_type: str | None = None
    attachment_analysis: str | None = None  # pre-computed image/log analysis


# ── Lazy agent construction (avoids API-key check at import time) ──────────

_agent: Agent[TriageDeps, TriageResult] | None = None


def _get_agent() -> Agent[TriageDeps, TriageResult]:
    global _agent
    if _agent is not None:
        return _agent

    settings = get_settings()
    model_name = f"google-gla:{settings.gemini_model}"

    _agent = Agent(
        model_name,
        output_type=TriageResult,
        system_prompt=TRIAGE_SYSTEM_PROMPT,
        deps_type=TriageDeps,
        retries=2,
    )

    # Register tools on the agent instance
    _agent.tool(query_service_context)
    _agent.tool(get_severity_guidelines)
    _agent.tool(get_attachment_analysis)
    _agent.tool(get_severity_hint)

    return _agent


# ── Tools ──────────────────────────────────────────────────────────────────


async def query_service_context(ctx: RunContext[TriageDeps], service_name: str) -> str:
    """Look up an eShop service from the knowledge base.

    Returns service metadata including SLOs, common failures, and
    observability patterns that help correlate the incident.
    """
    with tracer.start_as_current_span("tool.query_service_context") as span:
        span.set_attribute("service_name", service_name)
        svc = lookup_service(service_name)
        if svc is None:
            return (
                f"Service '{service_name}' not found in the eShop catalog. "
                f"Known services: {', '.join(ESHOP_SERVICES.keys())}"
            )
        return json.dumps(svc, indent=2, default=str)


async def get_severity_guidelines(ctx: RunContext[TriageDeps], proposed_severity: str) -> str:
    """Retrieve the severity classification rules for a given level (P0-P4).

    Use this to validate your severity assessment against official criteria.
    """
    level = proposed_severity.upper()
    rules = SEVERITY_RULES.get(level)
    if rules is None:
        return f"Unknown severity '{level}'. Valid levels: P0, P1, P2, P3, P4."
    return (
        f"**{level} - {rules['label']}**\n"
        f"Criteria: {', '.join(rules['criteria'])}\n"
        f"Response time: {rules['response_time']}\n"
        f"Escalation: {rules['escalation']}"
    )


async def get_attachment_analysis(ctx: RunContext[TriageDeps]) -> str:
    """Retrieve the pre-computed analysis of the incident attachment
    (screenshot or log file). Returns 'No attachment' if none was provided.
    """
    if ctx.deps.attachment_analysis:
        return ctx.deps.attachment_analysis
    return "No attachment was provided with this incident."


async def get_severity_hint(ctx: RunContext[TriageDeps]) -> str:
    """Quick keyword-based severity estimate to guide your classification."""
    hint = rule_based_severity_hint(ctx.deps.description)
    return f"Keyword-based severity hint: {hint}. Validate this against the full criteria."


# ── Main entry-point ───────────────────────────────────────────────────────


async def run_triage(
    *,
    incident_id: str,
    description: str,
    attachment_path: str | None = None,
    attachment_type: str | None = None,
) -> TriageResult:
    """Execute the full triage pipeline and return a structured result."""
    with tracer.start_as_current_span("agent.run_triage") as span:
        span.set_attribute("incident_id", incident_id)
        start = time.monotonic()

        # Pre-analyse attachment (outside the agent so we can choose the model)
        attachment_analysis: str | None = None
        if attachment_path:
            attachment_analysis = await _preprocess_attachment(
                attachment_path, attachment_type or ""
            )

        deps = TriageDeps(
            incident_id=incident_id,
            description=description,
            attachment_path=attachment_path,
            attachment_type=attachment_type,
            attachment_analysis=attachment_analysis,
        )

        prompt = f"Triage incident {incident_id}:\n\n{description}"
        if attachment_analysis:
            prompt += f"\n\n--- Attachment analysis ---\n{attachment_analysis}"

        agent = _get_agent()
        result = await agent.run(prompt, deps=deps)
        triage = result.output

        elapsed = time.monotonic() - start
        triage_duration_seconds.labels(severity=triage.severity).observe(elapsed)
        incidents_by_severity.labels(
            severity=triage.severity, service=triage.affected_service
        ).inc()
        llm_calls_total.labels(model="gemini-flash", status="success").inc()

        span.set_attribute("severity", triage.severity)
        span.set_attribute("affected_service", triage.affected_service)
        span.set_attribute("confidence", triage.confidence)

        logger.info(
            "Triage completed",
            extra={
                "incident_id": incident_id,
                "severity": triage.severity,
                "service": triage.affected_service,
                "confidence": triage.confidence,
                "elapsed_s": round(elapsed, 2),
            },
        )
        return triage


async def _preprocess_attachment(path: str, mime: str) -> str:
    """Analyse an attachment before passing it to the agent.

    Uses the severity of keyword hints to decide whether to use
    Gemini Flash (cheap) or Claude Sonnet (deep).
    """
    from src.utils.multimodal import analyse_image, parse_log_file

    if mime.startswith("image/"):
        result = await analyse_image(path, use_advanced=False)
        return result.get("analysis", "")

    # Treat as log/text file
    result = await parse_log_file(path, deep_analysis=False)
    parts = [f"Log file: {result['total_lines']} lines, {result['error_count']} errors"]
    if result.get("sample_errors"):
        parts.append("Sample errors:\n" + "\n".join(result["sample_errors"][:10]))
    if result.get("trace_ids"):
        parts.append("Trace IDs: " + ", ".join(result["trace_ids"]))
    return "\n".join(parts)
