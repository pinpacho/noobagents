"""Small parsing helpers shared across modules."""

from __future__ import annotations

import re


def extract_error_codes(text: str) -> list[str]:
    """Pull HTTP-style status codes out of free text."""
    return re.findall(r"\b[45]\d{2}\b", text)


def extract_service_mentions(text: str) -> list[str]:
    """Detect mentions of known eShop service names."""
    services = {
        "catalog", "basket", "ordering", "payment", "identity",
        "cart", "checkout", "auth", "search",
    }
    found: list[str] = []
    lower = text.lower()
    for svc in services:
        if svc in lower:
            found.append(svc)
    return sorted(set(found))


def truncate(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... (truncated — {len(text)} chars total)"
