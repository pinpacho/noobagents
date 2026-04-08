# SRE Incident Intake & Triage Agent

An AI-powered agent that automates incident intake, triage, ticketing, and notifications for e-commerce platforms running on the Microsoft eShop (.NET) microservice architecture.

## Problem

Manual incident triage is slow and error-prone. On-call engineers spend valuable minutes reading logs, classifying severity, creating tickets, and notifying stakeholders — time that should be spent resolving the issue.

## Solution

This agent automates the full incident lifecycle:

1. **Multimodal Ingestion** — Accepts text descriptions + screenshots or log files
2. **AI-Powered Triage** — Gemini 2.0 Flash classifies severity (P0–P4) using eShop domain knowledge; Claude Sonnet handles deep log analysis
3. **Automated Ticketing** — Creates structured Jira tickets with root-cause hypothesis and mitigation steps
4. **Multi-Channel Notifications** — Alerts the on-call team via Slack and email
5. **Resolution Flow** — Notifies the original reporter when the incident is resolved

## Architecture

```
                    ┌──────────────────────────┐
                    │   POST /incidents/submit  │
                    │   (text + image/log)      │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │  Validation & Guardrails  │
                    │  (prompt injection check) │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │  Pydantic AI Triage Agent │
                    │  ┌─────────────────────┐  │
                    │  │ Gemini 2.0 Flash    │  │
                    │  │ (orchestration)     │  │
                    │  └─────────────────────┘  │
                    │  Tools:                    │
                    │  - query_service_context   │
                    │  - get_severity_guidelines │
                    │  - get_attachment_analysis │
                    │  - get_severity_hint       │
                    └──────┬───────────┬────────┘
                           │           │
              ┌────────────▼──┐  ┌─────▼──────────┐
              │ Create Ticket │  │ Send Alerts     │
              │ (Mock Jira)   │  │ (Slack + Email) │
              └───────────────┘  └────────────────┘
                                         │
                    ┌────────────────────▼─────────────┐
                    │  POST /incidents/{id}/resolve     │
                    │  → Notify reporter via email      │
                    └──────────────────────────────────┘

        Observability: OpenTelemetry → Jaeger │ Structured JSON Logs │ Prometheus
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI (Python 3.12) |
| **Agent** | Pydantic AI 0.8 |
| **LLM (fast)** | Gemini 2.0 Flash |
| **LLM (deep)** | Claude Sonnet 3.5 |
| **Database** | SQLite (async via aiosqlite) |
| **Tracing** | OpenTelemetry → Jaeger |
| **Logging** | Structured JSON (python-json-logger) |
| **Metrics** | Prometheus |
| **Ticketing** | Mock Jira (swappable interface) |
| **Notifications** | Slack webhooks + SMTP email |
| **Deployment** | Docker Compose + uv |

## Quick Start

```bash
git clone https://github.com/pinpacho/noobagents.git
cd sre-triage-agent
cp .env.example .env
# Edit .env → set GOOGLE_API_KEY (required) and optionally ANTHROPIC_API_KEY
docker compose up --build
```

Then:
- **API docs**: http://localhost:8000/docs
- **Jaeger UI**: http://localhost:16686
- **Prometheus metrics**: http://localhost:8000/metrics

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/incidents/submit` | Submit an incident (text + optional file) |
| `GET` | `/incidents/{id}` | Get incident details and triage results |
| `GET` | `/incidents` | List all incidents |
| `POST` | `/incidents/{id}/resolve` | Resolve and notify reporter |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

## E-Commerce Context

The agent is pre-loaded with knowledge of 5 eShop microservices:

- **Catalog API** — Product search, inventory (SLO: 99.9%)
- **Basket Service** — Shopping cart via Redis (SLO: 99.95%)
- **Ordering Service** — Order saga orchestration (SLO: 99.99%)
- **Payment Gateway** — Stripe integration, critical revenue path (SLO: 99.99%)
- **Identity Service** — Auth, JWT tokens, sessions (SLO: 99.99%)

Each service includes SLOs, common failure patterns, observability baselines, and team assignments.

## Project Structure

```
src/
├── main.py                # FastAPI app entry-point
├── config.py              # Pydantic BaseSettings
├── api/                   # Routes, request/response models
├── agent/                 # Pydantic AI triage agent + tools
├── knowledge/             # eShop service catalog, severity rules
├── integrations/          # Ticketing (mock), Slack, Email
├── middleware/             # Guardrails, validation, error handling
├── observability/         # OpenTelemetry, logging, Prometheus
├── database/              # SQLAlchemy models, repository
└── utils/                 # Multimodal processing, parsers
```

## Documentation

- [AGENTS_USE.md](docs/AGENTS_USE.md) — Agent capabilities, use cases, observability, security
- [SCALING.md](docs/SCALING.md) — How this scales to 10k+ incidents/day
- [QUICKGUIDE.md](docs/QUICKGUIDE.md) — 5-minute setup guide

## License

MIT — see [LICENSE](LICENSE).
