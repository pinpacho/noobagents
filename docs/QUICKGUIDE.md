# Quick Start Guide

Get the SRE NOOBS Agent running in 5 minutes.

## Prerequisites

- Docker & Docker Compose
- A Google API key (for Gemini 2.5 Flash-Lite) — [Get one here](https://aistudio.google.com/apikey)
- (Optional) An Anthropic API key for deep log analysis with Claude Sonnet

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/pinpacho/noobagents.git
cd noobagents
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your API keys:

```bash
GOOGLE_API_KEY=your-google-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here   # optional
```

### 3. Start the services

```bash
docker compose up --build
```

This starts:
- **App** on `http://localhost:8000` (API + Swagger docs)
- **Jaeger** on `http://localhost:16686` (distributed traces)

### 4. Verify it's running

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status": "ok", "version": "0.1.0", "service": "SRE NOOBS Agent"}
```

---

## Try It Out

### Submit an incident (text only)

```bash
curl -X POST http://localhost:8000/incidents/submit \
  -F "description=Payment gateway returning 502 errors for all transactions. Checkout completely broken. Revenue impact estimated at 2000 dollars per minute." \
  -F "reporter_email=oncall@example.com"
```

Response:
```json
{
  "incident_id": "inc_abc123...",
  "status": "submitted",
  "message": "Incident received — triage is running in the background."
}
```

### Submit with a screenshot

```bash
curl -X POST http://localhost:8000/incidents/submit \
  -F "description=Search latency spiking to 3 seconds. See attached Grafana screenshot." \
  -F "reporter_email=dev@example.com" \
  -F "file=@screenshot.png"
```

### Submit with a log file

```bash
curl -X POST http://localhost:8000/incidents/submit \
  -F "description=Basket service throwing Redis connection errors. See attached logs." \
  -F "reporter_email=platform@example.com" \
  -F "file=@error.log"
```

### Check triage results

```bash
curl http://localhost:8000/incidents/{incident_id}
```

Wait a few seconds for the background triage to complete. The response includes:
- `severity` — P0, P1, P2, P3, or P4
- `affected_service` — Which eShop service is impacted
- `triage_summary` — What happened and why
- `root_cause_hypothesis` — Best-guess root cause
- `recommended_team` — Who should fix it
- `ticket_id` — Auto-created Jira ticket
- `notifications_sent` — Slack and email delivery status

### Resolve an incident

```bash
curl -X POST http://localhost:8000/incidents/{incident_id}/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution": "Restarted payment service pod, Stripe connectivity restored"}'
```

This marks the incident as resolved and sends an email to the original reporter.

### List all incidents

```bash
curl http://localhost:8000/incidents
```

---

## Explore

| What | Where |
|------|-------|
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **Jaeger Traces** | http://localhost:16686 → Search for `sre-triage-agent` |
| **Prometheus Metrics** | http://localhost:8000/metrics |
| **Health Check** | http://localhost:8000/health |

---

## Optional: Slack & Email Notifications

To receive real notifications, configure in `.env`:

**Slack:**
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx
```

**Email (SMTP):**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=sre-agent@yourcompany.com
```

Without these, notifications run in **mock mode** — they log the notification intent without actually sending.

---

## Local Development (without Docker)

```bash
# Requires Python 3.12 and uv
uv sync
cp .env.example .env
# Edit .env with your API keys
uv run uvicorn src.main:app --reload --port 8000
```

Run tests:
```bash
uv run pytest tests/ -v
```

---

## Shut Down

```bash
docker compose down
```

To also remove stored data:
```bash
docker compose down -v
```
