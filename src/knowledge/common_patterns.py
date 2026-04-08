"""Common failure patterns across the eShop platform.

Used by the triage agent to quickly match incoming incidents against
known issues and suggest mitigations.
"""

from __future__ import annotations

COMMON_LOG_PATTERNS: list[dict] = [
    {
        "regex": r"(?i)(System\.Net\.Http\.HttpRequestException|HttpClient.*timeout)",
        "description": "HTTP client timeout — downstream service unreachable",
        "likely_services": ["catalog", "payment", "ordering"],
        "suggested_check": "Verify target service health, check DNS resolution, inspect network policies",
    },
    {
        "regex": r"(?i)(SqlException|connection\s+pool\s+exhausted|deadlock\s+victim)",
        "description": "SQL Server connectivity or contention issue",
        "likely_services": ["catalog", "ordering", "payment", "identity"],
        "suggested_check": "Check SQL connection pool metrics, look for long-running transactions",
    },
    {
        "regex": r"(?i)(Redis.*ConnectionException|READONLY|OOM\s+command)",
        "description": "Redis failure — session/cache store unavailable",
        "likely_services": ["basket", "identity"],
        "suggested_check": "Check Redis cluster health, memory usage, and replica status",
    },
    {
        "regex": r"(?i)(StripeException|payment.*failed|gateway.*timeout)",
        "description": "Payment gateway failure",
        "likely_services": ["payment"],
        "suggested_check": "Check Stripe status page, circuit breaker state, retry queue depth",
    },
    {
        "regex": r"(?i)(401\s+Unauthorized|JWT.*expired|token.*invalid)",
        "description": "Authentication / authorization failure",
        "likely_services": ["identity"],
        "suggested_check": "Check signing key rotation, Redis session store, token expiry config",
    },
    {
        "regex": r"(?i)(OutOfMemoryException|OOM|killed\s+process)",
        "description": "Out-of-memory crash",
        "likely_services": ["catalog", "ordering", "basket"],
        "suggested_check": "Check pod memory limits, look for memory leaks, review recent deployments",
    },
    {
        "regex": r"(?i)(503\s+Service\s+Unavailable|readiness\s+probe\s+failed)",
        "description": "Service unavailable — pod not ready",
        "likely_services": ["catalog", "basket", "ordering", "payment", "identity"],
        "suggested_check": "Check K8s pod status, readiness probes, recent deployments",
    },
    {
        "regex": r"(?i)(elasticsearch.*timeout|index.*not.*found)",
        "description": "Elasticsearch issue affecting search",
        "likely_services": ["catalog"],
        "suggested_check": "Check ES cluster health, shard allocation, index status",
    },
    {
        "regex": r"(?i)(message.*queue|service.*bus|dead.*letter|DLQ)",
        "description": "Message queue issue — ordering saga may be stuck",
        "likely_services": ["ordering"],
        "suggested_check": "Check queue depth, DLQ count, consumer lag",
    },
    {
        "regex": r"(?i)(certificate|TLS|SSL|handshake.*fail)",
        "description": "TLS / certificate issue",
        "likely_services": ["identity", "payment"],
        "suggested_check": "Check certificate expiry, TLS configuration, trust chain",
    },
]


SAMPLE_LOG_ENTRIES: dict[str, str] = {
    "payment_gateway_timeout": (
        "2026-04-08T14:32:11.456Z ERROR [PaymentService] "
        "System.Net.Http.HttpRequestException: Connection timed out "
        "while calling https://api.stripe.com/v1/charges\n"
        "2026-04-08T14:32:11.457Z ERROR [PaymentService] "
        "CircuitBreaker OPEN for StripeGateway after 5 consecutive failures\n"
        "2026-04-08T14:32:11.458Z WARN  [OrderingSaga] "
        "Payment step timed out for OrderId=ORD-98712 — compensating"
    ),
    "redis_failure": (
        "2026-04-08T09:15:03.201Z ERROR [BasketService] "
        "StackExchange.Redis.RedisConnectionException: "
        "It was not possible to connect to the redis server(s)\n"
        "2026-04-08T09:15:03.202Z WARN  [BasketService] "
        "Cart data unavailable for userId=usr-44123 — returning empty basket\n"
        "2026-04-08T09:15:04.100Z ERROR [IdentityService] "
        "Session store unavailable — falling back to cookie-only auth"
    ),
    "catalog_search_slow": (
        "2026-04-08T11:45:22.890Z WARN  [CatalogAPI] "
        "Elasticsearch query took 4532ms (threshold: 200ms) "
        "for query='wireless headphones'\n"
        "2026-04-08T11:45:23.000Z ERROR [CatalogAPI] "
        "Elasticsearch timeout for shard [catalog-products][2] "
        "— returning partial results"
    ),
}
