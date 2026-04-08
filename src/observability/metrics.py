"""Prometheus metrics definitions."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# --- Request-level ---
incident_submissions_total = Counter(
    "incident_submissions_total",
    "Total incident submissions",
    ["status"],  # success | validation_error | server_error
)

# --- Triage ---
triage_duration_seconds = Histogram(
    "triage_duration_seconds",
    "Time to complete automated triage",
    ["severity"],
    buckets=(1, 2, 5, 10, 30, 60, 120),
)

incidents_by_severity = Counter(
    "incidents_by_severity_total",
    "Incident count grouped by severity",
    ["severity", "service"],
)

# --- LLM ---
llm_calls_total = Counter(
    "llm_calls_total",
    "LLM API calls",
    ["model", "status"],  # success | error
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Token usage per model",
    ["model", "direction"],  # input | output
)

# --- Notifications ---
notifications_total = Counter(
    "notifications_total",
    "Notification attempts",
    ["channel", "status"],  # success | failure
)
