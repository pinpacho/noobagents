"""Embedded knowledge base for Microsoft eShop (.NET) architecture.

Provides service catalog, common failure patterns, and observability
context so the triage agent can correlate incidents with specific
e-commerce microservices.
"""

from __future__ import annotations

ESHOP_SERVICES: dict[str, dict] = {
    "catalog": {
        "name": "Product Catalog API",
        "description": "Product listings, search, and inventory queries",
        "endpoints": ["/api/catalog/items", "/api/catalog/items/{id}", "/api/catalog/search"],
        "dependencies": ["sqlserver", "redis", "elasticsearch"],
        "slo": {"availability": 99.9, "p95_latency_ms": 200},
        "team": "Search Team",
        "common_failures": [
            {
                "pattern": "search_timeout",
                "symptoms": ["elasticsearch timeout", "search latency >2 s", "504 gateway timeout"],
                "severity": "P2",
                "mitigation": "Scale Elasticsearch, check cache hit ratio, verify index health",
            },
            {
                "pattern": "catalog_db_connection_pool_exhausted",
                "symptoms": ["Timeout expired", "Connection pool exhausted", "SqlException"],
                "severity": "P1",
                "mitigation": "Increase pool size, check for query leaks, restart pods",
            },
        ],
        "observability_patterns": {
            "database_operations": {
                "typical_queries": [
                    "SELECT * FROM Products WHERE CategoryId = @p0",
                    "SELECT COUNT(*) FROM Inventory WHERE ProductId = @p0",
                ],
                "slow_query_threshold_ms": 100,
                "connection_pool_size": 50,
                "common_db_errors": ["Timeout expired", "Deadlock detected", "Connection pool exhausted"],
            },
            "api_request_patterns": {
                "typical_request_rate": "500-1000 req/s",
                "peak_hours": "10 AM–2 PM, 7 PM–10 PM",
                "status_codes": {
                    "200": "normal",
                    "404": "product not found (acceptable if < 5 %)",
                    "503": "elasticsearch down (CRITICAL)",
                    "504": "gateway timeout (CRITICAL)",
                },
            },
            "system_metrics": {
                "cpu_normal": "20-40 %",
                "memory_normal": "60-75 % of 6 GB",
                "disk_io_normal": "< 50 MB/s",
                "warning_thresholds": {"cpu": "> 80 %", "memory": "> 90 %", "disk": "> 80 % capacity"},
            },
            "concurrency": {
                "thread_pool": 100,
                "async_ops": ["search", "inventory_check"],
                "cache_hit_target": "> 80 %",
            },
        },
    },
    "basket": {
        "name": "Shopping Basket Service",
        "description": "Session-based shopping cart management backed by Redis",
        "endpoints": ["/api/basket/{userId}", "/api/basket/checkout"],
        "dependencies": ["redis"],
        "slo": {"availability": 99.95, "p95_latency_ms": 100},
        "team": "Platform Team",
        "common_failures": [
            {
                "pattern": "redis_connection_lost",
                "symptoms": ["ConnectionException", "cart_data_lost", "READONLY replica"],
                "severity": "P1",
                "mitigation": "Failover to replica, restart Redis cluster, check memory usage",
            },
            {
                "pattern": "cart_sync_race_condition",
                "symptoms": ["stale cart data", "item count mismatch"],
                "severity": "P3",
                "mitigation": "Enable optimistic locking, review concurrent writes",
            },
        ],
        "observability_patterns": {
            "database_operations": {
                "cache_ops": ["HGET basket:{userId}", "HSET basket:{userId}", "EXPIRE basket:{userId} 1800"],
                "typical_latency_ms": "5-15",
                "common_errors": ["READONLY replica", "TIMEOUT", "Connection refused", "OOM command not allowed"],
            },
            "api_request_patterns": {
                "typical_request_rate": "200-500 req/s",
                "session_duration_avg": "30 minutes",
                "cart_abandonment_normal": "60-70 %",
            },
            "system_metrics": {
                "redis_memory": "1-2 GB",
                "redis_keys_count": "10 k–50 k active sessions",
                "cpu_normal": "10-25 %",
            },
            "concurrency": {
                "async_writes": True,
                "optimistic_locking": "prevents race conditions on add/remove",
                "replication": "Redis cluster with 3 replicas",
            },
        },
    },
    "ordering": {
        "name": "Order Processing Service",
        "description": "Order creation, validation, and saga orchestration",
        "endpoints": ["/api/orders", "/api/orders/{orderId}", "/api/orders/{orderId}/cancel"],
        "dependencies": ["sqlserver", "service-bus", "payment"],
        "slo": {"availability": 99.99, "p95_latency_ms": 500},
        "team": "Ordering Team",
        "common_failures": [
            {
                "pattern": "order_stuck_in_saga",
                "symptoms": ["saga_timeout", "payment_pending > 5 min", "order stuck AwaitingValidation"],
                "severity": "P1",
                "mitigation": "Check payment service health, inspect DLQ, manually compensate saga",
            },
            {
                "pattern": "service_bus_backlog",
                "symptoms": ["message_queue_depth > 10 k", "consumer lag rising"],
                "severity": "P2",
                "mitigation": "Scale consumers, check for poison messages, purge DLQ",
            },
        ],
        "observability_patterns": {
            "database_operations": {
                "typical_queries": [
                    "INSERT INTO Orders (BuyerId, OrderDate, StatusId) VALUES (@p0, @p1, @p2)",
                    "UPDATE Orders SET StatusId = @p0 WHERE Id = @p1",
                ],
                "transaction_isolation": "ReadCommitted",
                "common_errors": ["Deadlock victim", "FK constraint violation"],
            },
            "api_request_patterns": {
                "typical_request_rate": "100-300 req/s",
                "saga_completion_p95": "3 s",
            },
            "system_metrics": {
                "cpu_normal": "30-50 %",
                "memory_normal": "50-70 %",
                "service_bus_queue_depth_normal": "< 1 000",
            },
            "concurrency": {
                "saga_pattern": "Order -> Payment -> Fulfillment (distributed transaction)",
                "compensation": "auto-refund on fulfillment failure",
                "idempotency": "OrderId used as idempotency key",
            },
        },
    },
    "payment": {
        "name": "Payment Gateway",
        "description": "Payment processing — CRITICAL REVENUE PATH",
        "endpoints": ["/api/payment/process", "/api/payment/refund"],
        "dependencies": ["stripe-api", "sqlserver"],
        "slo": {"availability": 99.99, "p95_latency_ms": 1000},
        "team": "Payments Team",
        "common_failures": [
            {
                "pattern": "payment_gateway_down",
                "symptoms": ["502 gateway timeout", "100 % payment failures", "StripeException"],
                "severity": "P0",
                "mitigation": "Check Stripe status page, enable circuit breaker, notify finance, page VP Engineering",
            },
            {
                "pattern": "payment_rate_limited",
                "symptoms": ["429 Too Many Requests from Stripe", "rate_limit_error"],
                "severity": "P1",
                "mitigation": "Implement request queuing, reduce retry frequency",
            },
            {
                "pattern": "duplicate_charges",
                "symptoms": ["customer charged twice", "missing idempotency key"],
                "severity": "P0",
                "mitigation": "Verify idempotency key enforcement, issue refunds, audit logs",
            },
        ],
        "observability_patterns": {
            "database_operations": {
                "transaction_logging": "INSERT INTO PaymentTransactions (OrderId, Amount, Status, Gateway)",
                "retry_logic": "3 retries with exponential back-off",
                "idempotency_keys": "prevents duplicate charges",
                "common_errors": ["Transaction deadlock", "FK constraint violation"],
            },
            "api_request_patterns": {
                "typical_request_rate": "50-100 req/s",
                "stripe_latency_normal": "500-1500 ms",
                "circuit_breaker": "opens after 5 consecutive failures",
                "stripe_errors": {
                    "card_declined": "user issue — not an incident",
                    "rate_limit_error": "P1 — slow down requests",
                    "api_connection_error": "P0 — gateway down",
                },
            },
            "system_metrics": {
                "success_rate_target": "> 98 %",
                "revenue_per_minute_avg": "$500-$1 000",
                "failed_payment_alert_threshold": "> 5 % failure rate triggers P0",
            },
            "concurrency": {
                "async_webhooks": "Stripe sends payment confirmations async",
                "saga_pattern": "Order -> Payment -> Fulfillment",
                "compensation": "auto-refund on fulfillment failure",
            },
        },
    },
    "identity": {
        "name": "Identity & Auth Service",
        "description": "Authentication, authorization, and user session management",
        "endpoints": ["/connect/token", "/connect/authorize", "/api/identity/validate"],
        "dependencies": ["sqlserver", "redis"],
        "slo": {"availability": 99.99, "p95_latency_ms": 150},
        "team": "Security Team",
        "common_failures": [
            {
                "pattern": "auth_failures",
                "symptoms": ["401 Unauthorized spike", "token validation failed", "JWT expired prematurely"],
                "severity": "P0",
                "mitigation": "Check signing key rotation, verify Redis session store, restart identity pods",
            },
            {
                "pattern": "session_store_down",
                "symptoms": ["Redis connection refused", "users logged out en masse"],
                "severity": "P0",
                "mitigation": "Failover Redis, check memory limits, validate cluster health",
            },
        ],
        "observability_patterns": {
            "database_operations": {
                "typical_queries": [
                    "SELECT * FROM Users WHERE Email = @p0",
                    "INSERT INTO RefreshTokens (UserId, Token, ExpiresAt)",
                ],
                "common_errors": ["Unique constraint violation", "Connection timeout"],
            },
            "api_request_patterns": {
                "typical_request_rate": "300-800 req/s",
                "token_refresh_rate": "~10 % of active sessions/min",
                "status_codes": {
                    "200": "normal auth",
                    "401": "expected for expired tokens (< 5 %)",
                    "503": "identity service down (CRITICAL)",
                },
            },
            "system_metrics": {
                "cpu_normal": "15-30 %",
                "memory_normal": "40-60 %",
                "active_sessions": "5 k–20 k",
            },
            "concurrency": {
                "token_cache_ttl": "300 s",
                "session_replication": "Redis cluster",
                "rate_limiting": "100 req/s per IP on /connect/token",
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Service aliases & lookup helpers
# ---------------------------------------------------------------------------
_SERVICE_ALIASES: dict[str, str] = {
    "cart": "basket",
    "shopping cart": "basket",
    "checkout": "ordering",
    "orders": "ordering",
    "order": "ordering",
    "auth": "identity",
    "authentication": "identity",
    "login": "identity",
    "search": "catalog",
    "products": "catalog",
    "pay": "payment",
    "payments": "payment",
    "stripe": "payment",
}


def lookup_service(name: str) -> dict | None:
    """Find a service by exact key or common alias (case-insensitive)."""
    key = name.strip().lower()
    if key in ESHOP_SERVICES:
        return ESHOP_SERVICES[key]
    alias_key = _SERVICE_ALIASES.get(key)
    if alias_key:
        return ESHOP_SERVICES[alias_key]
    # Fuzzy: check if the name appears inside any service description
    for svc in ESHOP_SERVICES.values():
        if key in svc["description"].lower() or key in svc["name"].lower():
            return svc
    return None


def get_all_services_summary() -> str:
    """Return a concise multi-line summary of all services (for LLM context)."""
    lines: list[str] = []
    for key, svc in ESHOP_SERVICES.items():
        slo = svc["slo"]
        lines.append(
            f"- **{svc['name']}** (`{key}`): {svc['description']}  "
            f"SLO: {slo['availability']}% avail, p95 {slo['p95_latency_ms']}ms  "
            f"Team: {svc['team']}"
        )
    return "\n".join(lines)
