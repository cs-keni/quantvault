"""Integration tests for /api/v1/analysis endpoints.

These tests exercise validation, auth, and authorization paths only —
they do not call the market data service (network/Redis required).
Full pipeline tests (requiring live data) are tagged @pytest.mark.integration
and skipped by default (set INTEGRATION_TESTS=1 to enable).
"""

import uuid

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    import uuid as _uuid

    email = f"analysis_test_{_uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpassword123", "full_name": "Test User"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


_VALID_HOLDINGS = [
    {"ticker": "VTI", "weight": 0.6},
    {"ticker": "BND", "weight": 0.4},
]

_VALID_PAYLOAD: dict = {
    "holdings": _VALID_HOLDINGS,
    "period": "1y",
    "confidence": 0.95,
    "benchmark_ticker": "SPY",
}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/analysis/metrics (ad-hoc)
# ─────────────────────────────────────────────────────────────────────────────


async def test_adhoc_metrics_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/analysis/metrics", json=_VALID_PAYLOAD)
    assert resp.status_code == 401


async def test_adhoc_metrics_invalid_period(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/analysis/metrics",
        json={**_VALID_PAYLOAD, "period": "99y"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_adhoc_metrics_weights_dont_sum_to_one(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    payload = {
        **_VALID_PAYLOAD,
        "holdings": [
            {"ticker": "VTI", "weight": 0.3},
            {"ticker": "BND", "weight": 0.3},
        ],
    }
    resp = await client.post("/api/v1/analysis/metrics", json=payload, headers=headers)
    assert resp.status_code == 422


async def test_adhoc_metrics_invalid_benchmark_ticker(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/analysis/metrics",
        json={**_VALID_PAYLOAD, "benchmark_ticker": "invalid ticker!"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_adhoc_metrics_confidence_too_low(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/analysis/metrics",
        json={**_VALID_PAYLOAD, "confidence": 0.0},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_adhoc_metrics_confidence_too_high(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/analysis/metrics",
        json={**_VALID_PAYLOAD, "confidence": 1.0},
        headers=headers,
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/analysis/portfolios/{id}/metrics (saved portfolio)
# ─────────────────────────────────────────────────────────────────────────────


async def test_saved_metrics_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/analysis/portfolios/{uuid.uuid4()}/metrics")
    assert resp.status_code == 401


async def test_saved_metrics_not_found(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.get(
        f"/api/v1/analysis/portfolios/{uuid.uuid4()}/metrics",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_saved_metrics_ownership_isolation(client: AsyncClient) -> None:
    """User B cannot access User A's portfolio metrics."""
    headers_a = await _register_and_login(client)
    headers_b = await _register_and_login(client)
    portfolio = (
        await client.post(
            "/api/v1/portfolios", json={"name": "Private"}, headers=headers_a
        )
    ).json()
    resp = await client.get(
        f"/api/v1/analysis/portfolios/{portfolio['id']}/metrics",
        headers=headers_b,
    )
    assert resp.status_code == 404


async def test_saved_metrics_empty_portfolio_returns_422(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "Empty"}, headers=headers)
    ).json()
    resp = await client.get(
        f"/api/v1/analysis/portfolios/{portfolio['id']}/metrics",
        headers=headers,
    )
    assert resp.status_code == 422


async def test_saved_metrics_invalid_confidence_zero(client: AsyncClient) -> None:
    """confidence=0 would cause IndexError in VaR; Query(gt=0) rejects with 422."""
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "P"}, headers=headers)
    ).json()
    await client.post(
        f"/api/v1/portfolios/{portfolio['id']}/holdings",
        json={
            "ticker": "VTI",
            "asset_name": "VTI",
            "asset_class": "EQUITY",
            "target_weight": "1.00000",
        },
        headers=headers,
    )
    resp = await client.get(
        f"/api/v1/analysis/portfolios/{portfolio['id']}/metrics",
        params={"confidence": 0.0},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_saved_metrics_invalid_period(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "P"}, headers=headers)
    ).json()
    await client.post(
        f"/api/v1/portfolios/{portfolio['id']}/holdings",
        json={
            "ticker": "VTI",
            "asset_name": "VTI",
            "asset_class": "EQUITY",
            "target_weight": "1.00000",
        },
        headers=headers,
    )
    resp = await client.get(
        f"/api/v1/analysis/portfolios/{portfolio['id']}/metrics",
        params={"period": "99y"},
        headers=headers,
    )
    assert resp.status_code == 422
