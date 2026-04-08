"""Multimodal processing — image analysis (Gemini/Claude) and log parsing."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

from src.config import get_settings
from src.observability.metrics import llm_calls_total, llm_tokens_total
from src.observability.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


# ── Image analysis ──────────────────────────────────────────────────────────

_IMAGE_PROMPT = """\
Analyse this incident-related image. Extract every piece of technical data:
1. Error messages or stack traces visible
2. Service names or API endpoints
3. Metric values, graph anomalies, or dashboard readings
4. HTTP status codes
5. Timestamps (if visible)
Be precise and technical. Return a structured list of findings."""


async def analyse_image(
    image_path: str,
    *,
    use_advanced: bool = False,
) -> dict:
    """Analyse an image using Gemini Flash or Claude Sonnet.

    Args:
        image_path: Filesystem path to the image.
        use_advanced: When True, use Claude Sonnet for deeper analysis.
    """
    with tracer.start_as_current_span("multimodal.analyse_image") as span:
        span.set_attribute("image_path", image_path)
        span.set_attribute("use_advanced", use_advanced)

        settings = get_settings()
        image_bytes = Path(image_path).read_bytes()

        if use_advanced and settings.anthropic_api_key:
            return await _analyse_image_claude(image_bytes, settings)
        return await _analyse_image_gemini(image_bytes, settings)


async def _analyse_image_gemini(image_bytes: bytes, settings) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.google_api_key)

    # Detect media type from magic bytes
    media_type = "image/png" if image_bytes[:4] == b"\x89PNG" else "image/jpeg"

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            _IMAGE_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=media_type),
        ],
    )
    llm_calls_total.labels(model="gemini-flash", status="success").inc()
    text = response.text or ""
    return {
        "analysis": text,
        "model_used": "gemini-flash",
        "confidence": "high" if len(text) > 100 else "low",
    }


async def _analyse_image_claude(image_bytes: bytes, settings) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(image_bytes).decode()
    media_type = "image/png" if image_bytes[:4] == b"\x89PNG" else "image/jpeg"

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _IMAGE_PROMPT},
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                ],
            }
        ],
    )
    llm_calls_total.labels(model="claude-sonnet", status="success").inc()
    llm_tokens_total.labels(model="claude-sonnet", direction="input").inc(response.usage.input_tokens)
    llm_tokens_total.labels(model="claude-sonnet", direction="output").inc(response.usage.output_tokens)
    text = response.content[0].text
    return {
        "analysis": text,
        "model_used": "claude-sonnet",
        "confidence": "very_high",
    }


# ── Log-file parsing ───────────────────────────────────────────────────────

async def parse_log_file(
    log_path: str,
    *,
    deep_analysis: bool = False,
) -> dict:
    """Parse a .log / .txt file for error patterns, trace IDs, timestamps."""
    with tracer.start_as_current_span("multimodal.parse_log_file") as span:
        span.set_attribute("log_path", log_path)

        text = Path(log_path).read_text(errors="replace")
        lines = text.splitlines()

        errors = [l for l in lines if re.search(r"(?i)\bERROR\b|Exception", l)]
        warnings = [l for l in lines if re.search(r"(?i)\bWARN", l)]
        trace_ids = list(
            {m.group(1) for l in lines for m in [re.search(r"(?i)trace[_-]?id[=:]\s*([a-f0-9-]+)", l)] if m}
        )

        result: dict = {
            "total_lines": len(lines),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "sample_errors": errors[:15],
            "trace_ids": trace_ids[:10],
        }

        span.set_attribute("error_count", len(errors))

        # Optional: deep analysis with Claude Sonnet
        if deep_analysis and errors:
            settings = get_settings()
            if settings.anthropic_api_key:
                result["deep_analysis"] = await _deep_log_analysis(errors[:25], settings)

        return result


async def _deep_log_analysis(errors: list[str], settings) -> dict:
    """Use Claude Sonnet for advanced log correlation and root-cause analysis."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    sample = "\n".join(errors)
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyse these error logs from an eShop (.NET) microservice cluster.\n\n"
                    f"{sample}\n\n"
                    "Provide:\n"
                    "1. Root cause hypothesis\n"
                    "2. Which eShop service is likely affected "
                    "(Catalog / Basket / Ordering / Payment / Identity)\n"
                    "3. Cascading failure risk assessment\n"
                    "4. Immediate mitigation steps"
                ),
            }
        ],
    )
    llm_calls_total.labels(model="claude-sonnet", status="success").inc()
    return {
        "root_cause_hypothesis": response.content[0].text,
        "model_used": "claude-sonnet",
    }
