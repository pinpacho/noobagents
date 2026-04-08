"""FastAPI application entry-point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import make_asgi_app

from src.api.routes import router
from src.config import get_settings
from src.database.repository import close_db, init_db
from src.middleware.error_handler import register_exception_handlers
from src.observability.logging_config import setup_logging
from src.observability.tracing import setup_tracing, shutdown_tracing

# Logging must be configured before anything else emits log lines
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting SRE Triage Agent")
    setup_tracing()
    await init_db()
    yield
    await close_db()
    shutdown_tracing()
    logger.info("SRE Triage Agent stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-ready SRE Incident Intake & Triage Agent for e-commerce platforms",
        lifespan=lifespan,
    )

    # Routes
    app.include_router(router)

    # Prometheus metrics at /metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # OpenTelemetry auto-instrumentation for FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Global error handlers
    register_exception_handlers(app)

    return app


app = create_app()
