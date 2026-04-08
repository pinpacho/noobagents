"""Input sanitisation utilities."""

from __future__ import annotations

import re


def sanitise_for_logging(text: str) -> str:
    """Strip characters that could break structured JSON logs."""
    text = text.replace("\r", "").replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_truncate(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
