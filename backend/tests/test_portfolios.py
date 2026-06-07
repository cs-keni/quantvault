"""Integration tests for Portfolio and Holding CRUD endpoints.

Uses the same session-scoped DB fixtures from conftest.py — all mutations are
rolled back after each test.
"""

from typing import Any

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    """Helper: register a unique user and return auth tokens."""
    import uuid

    email = f"portfolio_test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpassword123", "full_name": "Test User"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio CRUD
# ─────────────────────────────────────────────────────────────────────────────


async def test_create_portfolio(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/portfolios",
        json={"name": "My Portfolio", "benchmark_ticker": "SPY"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Portfolio"
    assert data["benchmark_ticker"] == "SPY"
    assert data["holdings"] == []


async def test_list_portfolios_only_shows_own(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    await client.post(
        "/api/v1/portfolios",
        json={"name": "P1"},
        headers=headers,
    )
    await client.post(
        "/api/v1/portfolios",
        json={"name": "P2"},
        headers=headers,
    )
    resp = await client.get("/api/v1/portfolios", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_portfolio_not_found(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    import uuid

    resp = await client.get(f"/api/v1/portfolios/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_get_portfolio_by_id(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    created = (await client.post("/api/v1/portfolios", json={"name": "P"}, headers=headers)).json()
    resp = await client.get(f"/api/v1/portfolios/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_update_portfolio(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    created = (
        await client.post("/api/v1/portfolios", json={"name": "Old"}, headers=headers)
    ).json()
    resp = await client.patch(
        f"/api/v1/portfolios/{created['id']}",
        json={"name": "New"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


async def test_delete_portfolio(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    created = (
        await client.post("/api/v1/portfolios", json={"name": "Del"}, headers=headers)
    ).json()
    resp = await client.delete(f"/api/v1/portfolios/{created['id']}", headers=headers)
    assert resp.status_code == 204
    # Verify it's gone
    resp2 = await client.get(f"/api/v1/portfolios/{created['id']}", headers=headers)
    assert resp2.status_code == 404


async def test_portfolio_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/portfolios")
    assert resp.status_code == 401


async def test_portfolio_not_accessible_by_other_user(client: AsyncClient) -> None:
    headers1 = await _register_and_login(client)
    headers2 = await _register_and_login(client)
    created = (
        await client.post("/api/v1/portfolios", json={"name": "Private"}, headers=headers1)
    ).json()
    resp = await client.get(f"/api/v1/portfolios/{created['id']}", headers=headers2)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Holding management
# ─────────────────────────────────────────────────────────────────────────────


async def _portfolio_with_holding(
    client: AsyncClient,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Helper: register user, create portfolio, add a holding."""
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "P"}, headers=headers)
    ).json()
    holding_payload = {
        "ticker": "VTI",
        "asset_name": "Vanguard Total Stock Market ETF",
        "asset_class": "EQUITY",
        "target_weight": "0.60000",
    }
    holding = (
        await client.post(
            f"/api/v1/portfolios/{portfolio['id']}/holdings",
            json=holding_payload,
            headers=headers,
        )
    ).json()
    return headers, portfolio, holding


async def test_add_holding(client: AsyncClient) -> None:
    _, _, holding = await _portfolio_with_holding(client)
    assert holding["ticker"] == "VTI"
    assert float(holding["target_weight"]) == pytest.approx(0.6, rel=1e-4)


async def test_add_holding_to_nonexistent_portfolio(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    import uuid

    resp = await client.post(
        f"/api/v1/portfolios/{uuid.uuid4()}/holdings",
        json={
            "ticker": "VTI",
            "asset_name": "VTI",
            "asset_class": "EQUITY",
            "target_weight": "0.60000",
        },
        headers=headers,
    )
    assert resp.status_code == 404


async def test_update_holding_weight(client: AsyncClient) -> None:
    headers, portfolio, holding = await _portfolio_with_holding(client)
    resp = await client.patch(
        f"/api/v1/portfolios/{portfolio['id']}/holdings/{holding['id']}",
        json={"target_weight": "0.50000"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert float(resp.json()["target_weight"]) == pytest.approx(0.5, rel=1e-4)


async def test_delete_holding(client: AsyncClient) -> None:
    headers, portfolio, holding = await _portfolio_with_holding(client)
    resp = await client.delete(
        f"/api/v1/portfolios/{portfolio['id']}/holdings/{holding['id']}",
        headers=headers,
    )
    assert resp.status_code == 204
    # Verify holding is gone: portfolio holdings should be empty
    p = (await client.get(f"/api/v1/portfolios/{portfolio['id']}", headers=headers)).json()
    assert p["holdings"] == []


async def test_holding_ticker_uppercased(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "P"}, headers=headers)
    ).json()
    holding = (
        await client.post(
            f"/api/v1/portfolios/{portfolio['id']}/holdings",
            json={
                "ticker": "vti",  # lowercase input
                "asset_name": "VTI",
                "asset_class": "EQUITY",
                "target_weight": "0.60000",
            },
            headers=headers,
        )
    ).json()
    assert holding["ticker"] == "VTI"


async def test_holding_weight_must_be_positive(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "P"}, headers=headers)
    ).json()
    resp = await client.post(
        f"/api/v1/portfolios/{portfolio['id']}/holdings",
        json={
            "ticker": "VTI",
            "asset_name": "VTI",
            "asset_class": "EQUITY",
            "target_weight": "0.00000",  # zero → validation error
        },
        headers=headers,
    )
    assert resp.status_code == 422
