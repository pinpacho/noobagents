"""OpenTelemetry tracing setup — exports to Jaeger via OTLP/HTTP."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.config import get_settings

logger = logging.getLogger(__name__)

_provider: TracerProvider | None = None


def setup_tracing() -> None:
    """Initialise the global TracerProvider and OTLP exporter."""
    global _provider
    settings = get_settings()

    resource = Resource.create({"service.name": settings.otel_service_name})
    _provider = TracerProvider(resource=resource)

    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
    exporter = OTLPSpanExporter(endpoint=endpoint)
    _provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(_provider)

    logger.info(
        "OpenTelemetry tracing configured",
        extra={"endpoint": endpoint, "service": settings.otel_service_name},
    )


def shutdown_tracing() -> None:
    if _provider:
        _provider.shutdown()


def get_tracer(name: str = __name__) -> trace.Tracer:
    return trace.get_tracer(name)
