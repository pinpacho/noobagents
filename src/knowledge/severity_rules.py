"""Severity classification rules for e-commerce incidents (P0–P4)."""

from __future__ import annotations

SEVERITY_RULES: dict[str, dict] = {
    "P0": {
        "label": "Critical",
        "criteria": [
            "Payment service completely down",
            "Checkout flow broken for all users",
            "Authentication failures preventing login",
            "Data corruption or security breach",
            "Revenue impact > $1 000 / min",
        ],
        "response_time": "5 minutes",
        "escalation": "VP Engineering + On-call manager",
        "keywords": [
            "payment down", "payment failure", "checkout broken", "auth down",
            "login failure", "data breach", "502", "503", "100%",
            "all users", "critical", "outage", "security",
        ],
    },
    "P1": {
        "label": "High",
        "criteria": [
            "Core service degraded (> 50 % error rate)",
            "Cart / ordering service unavailable",
            "Significant latency spike (> 10× baseline)",
            "Revenue impact $100–$1 000 / min",
        ],
        "response_time": "15 minutes",
        "escalation": "Engineering Manager + On-call",
        "keywords": [
            "degraded", "high error rate", "cart down", "ordering failed",
            "redis down", "connection lost", "timeout", "saga stuck",
            "queue backlog", "rate limit",
        ],
    },
    "P2": {
        "label": "Medium",
        "criteria": [
            "Non-critical service degraded",
            "Search / catalog slow or partially failing",
            "Affects < 10 % of users",
        ],
        "response_time": "1 hour",
        "escalation": "Team Lead",
        "keywords": [
            "slow", "search timeout", "partial", "intermittent",
            "some users", "catalog", "latency", "elasticsearch",
        ],
    },
    "P3": {
        "label": "Low",
        "criteria": [
            "Minor functional issues",
            "UI glitches not blocking purchase",
            "No measurable revenue impact",
        ],
        "response_time": "4 hours",
        "escalation": "On-call Engineer",
        "keywords": [
            "minor", "ui bug", "glitch", "cosmetic",
            "non-blocking", "edge case",
        ],
    },
    "P4": {
        "label": "Informational",
        "criteria": [
            "Cosmetic issues",
            "Feature requests mislabelled as incidents",
            "Documentation gaps",
        ],
        "response_time": "Next sprint",
        "escalation": "Backlog",
        "keywords": [
            "cosmetic", "feature request", "documentation",
            "low priority", "nice to have",
        ],
    },
}


def rule_based_severity_hint(description: str) -> str:
    """Return a quick best-guess severity based on keyword matching.

    This is used as a *hint* to the LLM, not as the final classification.
    """
    desc_lower = description.lower()
    for level in ("P0", "P1", "P2", "P3", "P4"):
        for kw in SEVERITY_RULES[level]["keywords"]:
            if kw in desc_lower:
                return level
    return "P3"  # default
