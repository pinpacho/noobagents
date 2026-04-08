"""Test the e-commerce knowledge base and severity rules."""

from __future__ import annotations

from src.knowledge.ecommerce_context import ESHOP_SERVICES, lookup_service, get_all_services_summary
from src.knowledge.severity_rules import rule_based_severity_hint


class TestServiceLookup:
    def test_exact_key(self):
        assert lookup_service("payment") is not None
        assert lookup_service("payment")["name"] == "Payment Gateway"

    def test_alias(self):
        assert lookup_service("cart") is not None
        assert lookup_service("cart")["name"] == "Shopping Basket Service"

    def test_alias_auth(self):
        svc = lookup_service("auth")
        assert svc is not None
        assert "Identity" in svc["name"]

    def test_fuzzy_match(self):
        svc = lookup_service("Product")
        assert svc is not None

    def test_unknown_service(self):
        assert lookup_service("nonexistent_service_xyz") is None

    def test_all_services_have_required_keys(self):
        for key, svc in ESHOP_SERVICES.items():
            assert "name" in svc
            assert "description" in svc
            assert "endpoints" in svc
            assert "dependencies" in svc
            assert "slo" in svc
            assert "team" in svc
            assert "common_failures" in svc

    def test_summary_not_empty(self):
        summary = get_all_services_summary()
        assert len(summary) > 100
        assert "payment" in summary.lower()


class TestSeverityHint:
    def test_p0_payment_down(self):
        assert rule_based_severity_hint("payment down, 100% errors") == "P0"

    def test_p1_degraded(self):
        assert rule_based_severity_hint("service degraded with high error rate") == "P1"

    def test_p2_slow(self):
        assert rule_based_severity_hint("search is slow for some users") == "P2"

    def test_p3_minor(self):
        assert rule_based_severity_hint("minor UI bug on product page") == "P3"

    def test_default_p3(self):
        assert rule_based_severity_hint("something vague happened") == "P3"
