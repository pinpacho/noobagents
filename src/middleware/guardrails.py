"""Security guardrails: prompt-injection detection and input sanitisation."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that strongly indicate prompt injection attempts
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(previous|above|all|prior)\s+instructions",
        r"disregard\s+(previous|above|all|prior)\s+instructions",
        r"you\s+are\s+now\s+a",
        r"new\s+instruction",
        r"system\s*prompt",
        r"\bact\s+as\b",
        r"\\n\\nHuman:",
        r"\\n\\nAssistant:",
        r"<\|im_start\|>",
        r"<\|system\|>",
        r"###\s*Instruction",
        r"IMPORTANT:\s*ignore",
        r"override\s+(the\s+)?previous",
    ]
]


class PromptInjectionDetector:
    """Scans user-supplied text for known prompt-injection patterns."""

    def scan(self, text: str) -> tuple[bool, list[str]]:
        """Return (is_safe, matched_patterns).

        ``is_safe`` is True when no injection patterns are found.
        """
        matches: list[str] = []
        for pat in _INJECTION_PATTERNS:
            if pat.search(text):
                matches.append(pat.pattern)
        if matches:
            logger.warning(
                "Prompt injection patterns detected",
                extra={"patterns": matches, "preview": text[:120]},
            )
        return len(matches) == 0, matches


def sanitise_text(text: str) -> str:
    """Light sanitisation — remove control characters that could break log
    formatting or confuse model tokenisation, but keep the text useful."""
    # Collapse multiple newlines; strip carriage returns
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove null bytes
    text = text.replace("\x00", "")
    return text.strip()
