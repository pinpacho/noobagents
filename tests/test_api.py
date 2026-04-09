"""Test API endpoints (health, submit, get, resolve)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "SRE NOOBS Agent"


@pytest.mark.asyncio
async def test_submit_incident_validation_short_description(client):
    """Description below min_length (20) should be rejected."""
    resp = await client.post(
        "/incidents/submit",
        data={"description": "too short", "reporter_email": "a@b.com"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_incident_missing_email(client):
    """Missing reporter_email field should be rejected."""
    resp = await client.post(
        "/incidents/submit",
        data={"description": "x" * 25},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_incident(client):
    resp = await client.get("/incidents/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_incidents_empty(client):
    resp = await client.get("/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_resolve_nonexistent(client):
    resp = await client.post(
        "/incidents/nonexistent/resolve",
        json={"resolution": "Fixed the thing"},
    )
    assert resp.status_code == 404
