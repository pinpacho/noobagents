# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the app locally
uv run uvicorn src.main:app --reload --port 8000

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_api.py -v

# Run a single test
uv run pytest tests/test_knowledge.py::TestServiceLookup::test_exact_key -v

# Lint
uv run ruff check .
uv run ruff format --check .

# Docker (app + Jaeger)
docker compose up --build
```

## Architecture

This is a FastAPI application that automates SRE incident triage for e-commerce platforms using Pydantic AI agents. The entry point is `src/main.py` which creates the FastAPI app via `create_app()`.

### Request Flow

```
POST /incidents/submit
  → Prompt injection scan (src/middleware/guardrails.py)
  → Input sanitisation + file validation (src/middleware/validation.py)
  → Persist incident to SQLite (src/database/repository.py)
  → Return 201 immediately
  → Background pipeline kicks off:
      1. Pre-process attachment with Gemini Flash or Claude Sonnet (src/utils/multimodal.py)
      2. Run Pydantic AI NOOBS Agent (src/agent/triage_agent.py)
      3. Create mock Jira ticket (src/integrations/ticketing.py)
      4. Notify team via Slack + email (src/integrations/slack.py, email.py)
      5. Update incident status at each step
```

### Key Design Patterns

**Lazy agent construction**: The Pydantic AI agent (`src/agent/triage_agent.py`) is built on first use via `_get_agent()`, not at import time. This prevents API key validation errors during testing. Tools are registered programmatically with `_agent.tool()`.

**Attachment preprocessing is decoupled from the agent**: Images/logs are analysed in `_preprocess_attachment()` *before* the agent runs, and the text result is injected as context. This lets us pick Gemini Flash vs Claude Sonnet per-attachment without the agent knowing about model routing.

**Dependency injection via RunContext**: `TriageDeps` dataclass carries incident context to every tool call. Tools receive it as `ctx: RunContext[TriageDeps]`.

**Mock-by-default integrations**: Slack and email silently fall back to logging when webhook URLs / SMTP credentials are absent. No configuration needed for local development.

**Incident state machine**: Each incident progresses through `SUBMITTED → ANALYZING → TRIAGED → TICKET_CREATED → NOTIFIED → RESOLVED`. Every transition appends to a JSON timeline array on the database model.

### Pydantic AI Specifics

- Agent uses `output_type=TriageResult` (not `result_type` — renamed in pydantic-ai 0.8.x)
- Access results via `result.output` (not `result.data`)
- Agent model string format: `"google-gla:{model_name}"`
- The system prompt in `src/agent/prompts.py` embeds the full eShop service catalog at module load time via `get_all_services_summary()`

### Testing

- Tests use an isolated SQLite database (`test_incidents.db`) cleaned up after each fixture
- `conftest.py` sets environment variables and clears the `get_settings()` LRU cache before tests
- The async test client uses `httpx.ASGITransport(app=app)` — no network I/O
- All async tests require `@pytest.mark.asyncio`

### Observability

Three pillars wired in `src/observability/`:
- **Tracing**: OpenTelemetry → Jaeger via OTLP/HTTP. Custom spans use `get_tracer(__name__)`.
- **Logging**: Structured JSON via `python-json-logger`. Always use `extra={}` for context fields.
- **Metrics**: Prometheus counters/histograms mounted at `/metrics`.

### Knowledge Base

`src/knowledge/ecommerce_context.py` contains an embedded (not RAG) catalog of 5 eShop microservices. `lookup_service()` handles aliases ("cart" → basket, "auth" → identity) and fuzzy matching. The full catalog is injected into the agent's system prompt.
