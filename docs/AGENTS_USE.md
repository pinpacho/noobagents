# AGENTS_USE.md — SRE Incident Intake & Triage Agent

## 1. Agent Overview

| Field | Value |
|-------|-------|
| **Name** | SRE Incident Intake & Triage Agent |
| **Purpose** | Automate the full incident lifecycle — intake, AI-powered triage, ticket creation, team notifications, and resolution tracking — for e-commerce platforms running on Microsoft eShop (.NET) microservices |
| **Tech Stack** | FastAPI, Pydantic AI 0.8, Gemini 2.5 Flash-Lite, Claude Sonnet, SQLite (async), OpenTelemetry, Prometheus |
| **Input** | Text description + optional image/log file attachment |
| **Output** | Structured triage (severity P0–P4, affected service, root cause hypothesis, mitigation steps) + Jira ticket + Slack/email alerts |

### Problem Statement

Manual incident triage costs 5–15 minutes per incident. On-call engineers spend that time reading logs, classifying severity, creating tickets, and paging stakeholders — time that should be spent resolving the issue. At scale, this delay compounds: a P0 payment outage loses ~$1,000/min in revenue while an engineer is still creating the ticket.

### How This Agent Solves It

The agent reduces mean-time-to-acknowledgement (MTTA) from minutes to seconds:

1. **Multimodal Ingestion** — Accepts text + screenshots or log files via a single API call
2. **AI-Powered Triage** — Gemini 2.5 Flash-Lite classifies severity using embedded eShop domain knowledge; Claude Sonnet handles deep log/image analysis for complex incidents
3. **Automated Ticketing** — Creates structured Jira tickets with root-cause hypothesis and ordered mitigation steps
4. **Multi-Channel Notifications** — Alerts the on-call team via Slack and email with full context
5. **Resolution Flow** — When the incident is resolved, notifies the original reporter automatically

---

## 2. Agents & Capabilities

### 2.1 Core Triage Agent

The system uses a **single Pydantic AI agent** with four specialised tools, orchestrated by Gemini 2.5 Flash-Lite. The agent produces a structured `TriageResult` output with guaranteed schema compliance.

```
┌────────────────────────────────────────┐
│      Pydantic AI Triage Agent          │
│      Model: Gemini 2.5 Flash-Lite           │
│      Output: TriageResult (typed)      │
│                                        │
│  Tools:                                │
│  ┌──────────────────────────────────┐  │
│  │ 1. query_service_context        │  │
│  │ 2. get_severity_guidelines      │  │
│  │ 3. get_attachment_analysis      │  │
│  │ 4. get_severity_hint            │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

### 2.2 Tool Descriptions

| Tool | Purpose | Span Name |
|------|---------|-----------|
| `query_service_context` | Retrieves metadata for an eShop service (SLOs, common failures, team, dependencies) from the embedded knowledge base | `tool.query_service_context` |
| `get_severity_guidelines` | Returns the official P0–P4 classification criteria for a proposed severity level so the agent can validate its assessment | `tool.get_severity_guidelines` |
| `get_attachment_analysis` | Returns pre-computed image or log-file analysis (done before the agent runs, using the appropriate LLM) | `tool.get_attachment_analysis` |
| `get_severity_hint` | Runs a fast keyword-based severity estimate to anchor the agent's classification | `tool.get_severity_hint` |

### 2.3 Hybrid LLM Strategy

The agent uses **two LLMs** selected per-task for optimal cost and quality:

| Model | Use Case | Cost | Latency |
|-------|----------|------|---------|
| **Gemini 2.5 Flash-Lite** | Agent orchestration, fast triage, ticketing, notifications | ~$0.075/1M tokens | ~1–3s |
| **Claude Sonnet** | Deep log analysis, image analysis for complex incidents, root-cause identification | ~$3/1M tokens | ~3–8s |

**Routing logic** (`src/utils/multimodal.py`):
- Default: Gemini Flash for all image/log analysis (fast, cost-effective)
- Escalation: Claude Sonnet when `use_advanced=True` (set for P0/P1 or when initial analysis confidence is low)
- ~80% of operations use Flash; ~20% escalate to Sonnet

### 2.4 Structured Output

The agent produces a `TriageResult` Pydantic model with guaranteed fields:

```python
class TriageResult(BaseModel):
    severity: str              # P0 | P1 | P2 | P3 | P4
    affected_service: str      # catalog | basket | ordering | payment | identity
    summary: str               # One-paragraph technical summary
    root_cause_hypothesis: str # Best-guess root cause
    recommended_team: str      # Team assignment
    mitigation_steps: list[str]# Ordered immediate actions
    confidence: float          # 0.0–1.0
    user_impact: str           # Human-readable impact description
```

---

## 3. Architecture & Orchestration

### 3.1 Request Flow

```
Client ──POST /incidents/submit──▶ FastAPI
                                      │
                        ┌─────────────▼──────────────┐
                        │  1. Guardrails              │
                        │  - Prompt injection scan    │
                        │  - Input sanitisation       │
                        │  - File validation (MIME,   │
                        │    size ≤ 10 MB)            │
                        └─────────────┬──────────────┘
                                      │
                        ┌─────────────▼──────────────┐
                        │  2. Persist to SQLite       │
                        │  - status: SUBMITTED        │
                        │  - Return incident_id       │
                        └─────────────┬──────────────┘
                                      │
                        ┌─────────────▼──────────────┐
                        │  3. Background Pipeline     │
                        │  ┌────────────────────────┐ │
                        │  │ a. Pre-process attach.  │ │
                        │  │    (Gemini/Claude)      │ │
                        │  ├────────────────────────┤ │
                        │  │ b. Run triage agent     │ │
                        │  │    (Gemini Flash +      │ │
                        │  │     4 tools)            │ │
                        │  ├────────────────────────┤ │
                        │  │ c. Create Jira ticket   │ │
                        │  ├────────────────────────┤ │
                        │  │ d. Notify team          │ │
                        │  │    (Slack + Email)      │ │
                        │  └────────────────────────┘ │
                        └────────────────────────────┘

Client ──POST /incidents/{id}/resolve──▶ Resolve + notify reporter
```

### 3.2 State Machine

Each incident progresses through a well-defined state machine:

```
SUBMITTED → ANALYZING → TRIAGED → TICKET_CREATED → NOTIFIED → IN_PROGRESS → RESOLVED → CLOSED
```

Every transition is recorded as a timeline event in the database, providing a full audit trail.

### 3.3 Agent Configuration

```python
# Lazy initialisation — avoids API key validation at import time
_agent = Agent(
    model_name="google-gla:gemini-2.0-flash",
    output_type=TriageResult,
    system_prompt=TRIAGE_SYSTEM_PROMPT,  # Includes full eShop service catalog
    deps_type=TriageDeps,
    retries=2,
)
```

Key design decisions:
- **Lazy construction**: Agent is built on first use, not at import time, to avoid requiring API keys during testing
- **Dependency injection**: `TriageDeps` dataclass carries incident context to every tool call via `RunContext`
- **Retries**: 2 automatic retries on LLM failures before propagating the error

---

## 4. Context Engineering

### 4.1 Embedded Knowledge Base (Not RAG)

Rather than using vector search, the agent has a **deterministic, embedded knowledge base** with full eShop service context. This was chosen for:
- **Reliability**: No vector DB to manage; no retrieval failures
- **Speed**: In-memory lookups, zero latency
- **Determinism**: Same query always returns the same context

### 4.2 eShop Service Catalog

Five microservices with rich operational metadata:

| Service | SLO | Team | Critical Path? |
|---------|-----|------|---------------|
| **Product Catalog API** | 99.9% avail, 200ms p95 | Search Team | No |
| **Shopping Basket Service** | 99.95% avail, 100ms p95 | Platform Team | Yes (revenue) |
| **Order Processing Service** | 99.99% avail, 500ms p95 | Ordering Team | Yes (revenue) |
| **Payment Gateway** | 99.99% avail, 1000ms p95 | Payments Team + VP Eng | Yes (critical) |
| **Identity & Auth Service** | 99.99% avail, 150ms p95 | Security Team | Yes (blocks all) |

Each service entry includes:
- **Common failure patterns** with symptoms, expected severity, and owning team
- **Observability patterns**: typical DB operations, API request rates, system metric baselines, concurrency settings
- **Dependencies**: upstream/downstream service map for cascading failure analysis

### 4.3 Severity Classification Rules

The agent's system prompt includes structured P0–P4 rules:

| Level | Response Time | Example Criteria | Escalation |
|-------|--------------|-------------------|------------|
| **P0** | 5 min | Payment down, auth outage, revenue > $1k/min | VP Engineering |
| **P1** | 15 min | Core service > 50% errors, cart down | Engineering Manager |
| **P2** | 1 hour | Non-critical degraded, < 10% users | Team Lead |
| **P3** | 4 hours | Minor issues, UI glitches | On-call Engineer |
| **P4** | Next sprint | Cosmetic, feature requests | Backlog |

### 4.4 Context Injection Strategy

The system prompt is constructed dynamically at module load time:

```python
TRIAGE_SYSTEM_PROMPT = f"""\
You are an expert SRE Incident Triage Specialist...

## eShop Service Catalog
{get_all_services_summary()}  # Injected at import time

## Classification Guidelines
P0 – Critical (respond in 5 min)
  Payment gateway down, checkout broken...
...
"""
```

Additionally, the `get_severity_hint` tool provides a fast keyword-based pre-classification that anchors the LLM's severity assessment, reducing hallucinated severity levels.

---

## 5. Use Cases

### Use Case 1: P0 — Payment Gateway Outage

**Input:**
```json
{
  "description": "Payment gateway returning 502 errors for all transactions. Checkout completely broken. Users seeing gateway timeout errors. Revenue impact estimated at $2000/min.",
  "reporter_email": "oncall@payments.com"
}
```

**Agent Execution:**
1. `get_severity_hint` → Returns "P0" (keywords: "payment", "502", "broken", "revenue")
2. `query_service_context("payment")` → Retrieves Payment Gateway metadata (SLO 99.99%, Stripe dependency, circuit breaker config)
3. `get_severity_guidelines("P0")` → Validates P0 criteria match
4. Agent produces structured output

**Output:**
```json
{
  "severity": "P0",
  "affected_service": "payment",
  "summary": "Payment Gateway experiencing complete outage with 502 errors on all transaction endpoints. Revenue impact >$2000/min.",
  "root_cause_hypothesis": "Stripe API connection failure or circuit breaker tripped after consecutive 5xx responses from upstream gateway",
  "recommended_team": "Payments Team + VP Engineering",
  "mitigation_steps": [
    "Check Stripe status page for ongoing incidents",
    "Inspect circuit breaker state — reset if stuck open",
    "Check network connectivity to Stripe API endpoints",
    "Review recent deployments to payment service",
    "Enable payment queue for retry if available"
  ],
  "confidence": 0.92,
  "user_impact": "All checkout attempts failing — 100% of purchase flow blocked"
}
```

**Downstream Actions:**
- Jira ticket SRE-0001 created with full context
- Slack #incidents notified
- On-call email sent to payments-team@example.com

### Use Case 2: P2 — Catalog Search Degradation

**Input:**
```
Description: "Search results loading slowly, p95 latency at 3.2s (normally 200ms). Started ~30 minutes ago. Only affects product search, browsing and cart still work fine."
Attachment: search_latency_graph.png
```

**Agent Execution:**
1. Attachment pre-processed with Gemini Flash → extracts latency spike from 200ms to 3.2s
2. `get_severity_hint` → Returns "P2" (keywords: "slow", "latency")
3. `query_service_context("catalog")` → Elasticsearch dependency flagged
4. Agent combines graph data + service context → P2 classification

**Output:** P2, Catalog API, Search Team assigned, suggests checking Elasticsearch cluster health and index shards.

### Use Case 3: P3 — Minor UI Issue

**Input:**
```
Description: "Product images on the catalog page are displaying with incorrect aspect ratios on mobile devices. No errors in console, just visual distortion."
```

**Agent Execution:**
1. `get_severity_hint` → Returns "P3" (no critical keywords)
2. `query_service_context("catalog")` → Catalog API context
3. No attachment → `get_attachment_analysis` returns "No attachment"

**Output:** P3, Catalog API, Search Team, suggests CSS fix for responsive image sizing. No immediate paging required.

---

## 6. Observability

### 6.1 Distributed Tracing (OpenTelemetry → Jaeger)

Every request generates a complete trace through the pipeline:

```
incident.submit (root span)
├── api.submit_incident
│   ├── guardrails.scan
│   └── database.create_incident
└── triage_pipeline (background)
    ├── multimodal.analyse_image (or parse_log_file)
    ├── agent.run_triage
    │   ├── tool.query_service_context
    │   ├── tool.get_severity_hint
    │   ├── tool.get_severity_guidelines
    │   └── tool.get_attachment_analysis
    ├── ticketing.create_ticket
    ├── notification.slack
    └── notification.email
```

**Custom span attributes:**
- `incident_id`, `severity`, `affected_service`, `confidence` on triage spans
- `service_name` on knowledge-base lookups
- `model_used`, `token_count` on LLM calls

**Access:** Jaeger UI at `http://localhost:16686` — search for service `sre-triage-agent`

### 6.2 Structured JSON Logging

All logs are emitted as structured JSON via `python-json-logger`:

```json
{
  "timestamp": "2026-04-08T14:23:01.123Z",
  "level": "INFO",
  "logger": "src.api.routes",
  "message": "Triage completed",
  "incident_id": "inc_abc123",
  "severity": "P0",
  "service": "payment",
  "confidence": 0.92,
  "elapsed_s": 4.21
}
```

Benefits:
- Machine-parseable for log aggregation (ELK, Loki, CloudWatch)
- Every log includes the incident context fields
- Noisy third-party loggers (httpx, httpcore) are suppressed to WARNING level

### 6.3 Prometheus Metrics

Available at `GET /metrics`:

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `incident_submissions_total` | Counter | `status` | Track accepted vs. rejected submissions |
| `triage_duration_seconds` | Histogram | `severity` | Measure triage latency (buckets: 1s–120s) |
| `incidents_by_severity_total` | Counter | `severity`, `service` | Severity distribution per service |
| `llm_calls_total` | Counter | `model`, `status` | LLM API call tracking |
| `llm_tokens_total` | Counter | `model`, `direction` | Token usage (input/output) |
| `notifications_total` | Counter | `channel`, `status` | Slack/email delivery tracking |

---

## 7. Security & Guardrails

### 7.1 Prompt Injection Detection

The `PromptInjectionDetector` scans all user-supplied text against 13 regex patterns before it reaches the LLM:

```python
PATTERNS = [
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
```

**Behaviour:** Returns HTTP 400 with matched patterns listed. The rejection is logged as a warning with the input preview for security audit.

### 7.2 Input Sanitisation

After injection scanning, `sanitise_text()` applies:
- Null byte removal (`\x00`)
- Carriage return stripping
- Consecutive newline collapse (3+ → 2)

### 7.3 File Upload Validation

| Check | Limit | Action on Violation |
|-------|-------|-------------------|
| File size | ≤ 10 MB | HTTP 400 |
| MIME type | Whitelist: `image/png`, `image/jpeg`, `text/plain`, `text/x-log`, `application/x-log` | HTTP 400 |
| File storage | UUID-based filenames, isolated uploads directory | Prevents path traversal |

### 7.4 Additional Security Measures

- **Non-root container execution**: Docker runs as UID 1000 (`appuser`)
- **Rate limiting**: Configurable via `RATE_LIMIT_PER_MINUTE` (default: 30)
- **No secret leakage**: API keys loaded from environment variables, never logged
- **Input length limits**: Description field: 20–5,000 characters

---

## 8. Scalability

The current implementation is designed for hackathon demonstration but includes clear scaling paths. See [SCALING.md](SCALING.md) for a detailed analysis.

### Current Limits

| Dimension | Current | Bottleneck |
|-----------|---------|------------|
| Throughput | ~100 incidents/day | SQLite write lock, single-process |
| Concurrent triage | 1 at a time | Background task queue |
| Service catalog | 5 services | In-memory dict |
| File storage | Local disk | Single volume mount |

### Scaling Dimensions (documented in SCALING.md)

1. **High Throughput (10k+ incidents/day)**: PostgreSQL, Redis queue, Celery workers, horizontal scaling
2. **Large Service Catalog (100+ services)**: Vector DB (pgvector), RAG over historical incidents
3. **Multi-Region**: Geo-distributed DB, regional LLM endpoints, CDN for static assets
4. **Cost Optimization**: Prompt caching, model routing by severity, batch processing for P3/P4

### Architecture Decisions That Enable Scaling

- **Repository pattern**: Database access layer is swappable — switch SQLite → PostgreSQL by changing one connection string
- **Pluggable integrations**: `TicketingService` and `NotificationService` abstract base classes allow swapping mock → real Jira/PagerDuty
- **Stateless API**: No server-side sessions; incident state lives in the database
- **OpenTelemetry**: Already instrumented — connect to any OTLP-compatible backend (Datadog, Grafana Tempo, AWS X-Ray)

---

## 9. Lessons Learned

### What Worked Well

1. **Pydantic AI's structured output** — The `output_type=TriageResult` pattern eliminated parsing failures. The agent always returns valid, typed data that downstream code can consume directly. No regex extraction, no JSON parsing, no schema validation after the fact.

2. **Embedded knowledge > RAG for bounded domains** — With only 5 services, an in-memory dictionary with aliases and fuzzy matching is faster, more reliable, and simpler than maintaining a vector database. The `lookup_service()` function handles typos and aliases (e.g., "cart" → basket, "auth" → identity) deterministically.

3. **Hybrid LLM strategy** — Using Gemini Flash for 80% of operations and Claude Sonnet for complex analysis kept costs low without sacrificing quality on critical P0/P1 incidents. The decision to pre-process attachments before the agent runs (rather than giving the agent vision capabilities directly) simplifies the architecture.

4. **Background triage pipeline** — Running triage as a FastAPI `BackgroundTask` means the API responds instantly (< 100ms) while the 5–15 second LLM processing happens asynchronously. Users poll for results.

### What We Would Change

1. **Task queue instead of BackgroundTasks** — FastAPI `BackgroundTasks` are tied to the process lifecycle. A crash during triage loses the job silently. In production, we would use Celery + Redis or arq for persistent, retryable task execution.

2. **Email validation on Form fields** — FastAPI's `Form()` parameters don't run Pydantic validators like `EmailStr`. We would add explicit email validation in the route handler or switch to a JSON request body.

3. **Circuit breaker for LLM calls** — Currently, a Gemini API outage causes all triage to fail. Adding a circuit breaker with automatic fallback to the keyword-based severity hint would maintain basic functionality during LLM downtime.

4. **Streaming triage updates** — Rather than polling `GET /incidents/{id}`, a WebSocket or SSE endpoint would give real-time progress updates as the pipeline advances through each stage.

### Key Technical Insights

- **Lazy agent initialisation matters**: Pydantic AI validates the API key at agent construction time. Building the agent at module-level breaks testing and cold-start scenarios. Our `_get_agent()` singleton pattern defers construction to first use.

- **`output_type` vs `result_type`**: Pydantic AI 0.8.x renamed `result_type` to `output_type` and `result.data` to `result.output`. This is the kind of breaking change that costs hours if you're working from outdated examples.

- **Pre-processing attachments outside the agent**: Rather than giving the agent vision tools, we pre-analyse images/logs and inject the analysis as text context. This keeps the agent's tool interface simple and allows us to choose the model per-task (Flash for quick reads, Sonnet for deep analysis).
