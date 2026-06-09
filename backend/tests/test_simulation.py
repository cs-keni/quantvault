"""Monte Carlo simulation math, validation, and API tests."""

import uuid
from typing import Any

import numpy as np
import pytest
from app.api.v1 import simulation as simulation_api
from app.schemas.simulation import SimulationRequest
from app.services.simulation_service import run_monte_carlo
from httpx import AsyncClient
from pydantic import ValidationError


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    email = f"simulation_test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpassword123", "full_name": "Test User"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tickers": ["VTI", "BND"],
        "weights": [0.6, 0.4],
        "period": "1y",
        "initial_investment": 10_000.0,
        "years": 10,
        "n_simulations": 100,
        "annual_contribution": 1_000.0,
        "seed": 42,
    }
    payload.update(overrides)
    return payload


class _FakeTask:
    id = "fake-task-id"


def _patch_celery_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        simulation_api.run_simulation,
        "apply_async",
        lambda *args, **kwargs: _FakeTask(),
    )


async def test_monte_carlo_same_seed_reproducible() -> None:
    metrics = {"annualized_return": 0.08, "annualized_volatility": 0.15}
    first = run_monte_carlo(metrics, 10_000, 5, 100, 500, seed=123)
    second = run_monte_carlo(metrics, 10_000, 5, 100, 500, seed=123)

    assert first == second


async def test_monte_carlo_different_seeds_differ() -> None:
    metrics = {"annualized_return": 0.08, "annualized_volatility": 0.15}
    first = run_monte_carlo(metrics, 10_000, 5, 100, 500, seed=123)
    second = run_monte_carlo(metrics, 10_000, 5, 100, 500, seed=456)

    assert first["final_value_distribution"] != second["final_value_distribution"]


async def test_monte_carlo_t_distribution_differs_from_normal_same_seed() -> None:
    metrics = {"annualized_return": 0.08, "annualized_volatility": 0.15}
    result = run_monte_carlo(metrics, 10_000, 1, 25, 0, seed=123)

    rng = np.random.default_rng(123)
    daily_mu = metrics["annualized_return"] / 252
    daily_sigma = metrics["annualized_volatility"] / np.sqrt(252)
    normal_returns = daily_mu + daily_sigma * rng.normal(size=(252, 25))
    normal_final = 10_000 * np.cumprod(1.0 + normal_returns, axis=0)[-1]

    assert not np.allclose(result["final_value_distribution"], normal_final.tolist())


async def test_zero_volatility_paths_follow_deterministic_compounding() -> None:
    metrics = {"annualized_return": 0.0504, "annualized_volatility": 0.0}
    result = run_monte_carlo(metrics, 10_000, 1, 5, 0, seed=123)
    daily_mu = metrics["annualized_return"] / 252
    expected = 10_000 * (1.0 + daily_mu) ** np.arange(1, 253)

    for path in result["sample_paths"]:
        assert np.allclose(path, expected, rtol=0, atol=1e-8)


async def test_contribution_count_is_exactly_years_when_returns_are_zero() -> None:
    metrics = {"annualized_return": 0.0, "annualized_volatility": 0.0}
    no_contrib = run_monte_carlo(metrics, 10_000, 10, 20, 0, seed=123)
    with_contrib = run_monte_carlo(metrics, 10_000, 10, 20, 1_000, seed=123)

    difference = (
        np.array(with_contrib["final_value_distribution"])
        - np.array(no_contrib["final_value_distribution"])
    )
    assert np.allclose(difference, 10_000.0)


async def test_probability_of_profit_accounts_for_contributions() -> None:
    metrics = {"annualized_return": 0.0, "annualized_volatility": 0.0}
    result = run_monte_carlo(metrics, 10_000, 1, 10, 1_000, seed=123)

    assert result["probability_of_profit"] == 0.0


async def test_sample_paths_always_returns_twenty_paths() -> None:
    metrics = {"annualized_return": 0.08, "annualized_volatility": 0.15}
    result = run_monte_carlo(metrics, 10_000, 2, 7, 0, seed=123)

    assert len(result["sample_paths"]) == 20


async def test_percentile_outcomes_keys() -> None:
    metrics = {"annualized_return": 0.08, "annualized_volatility": 0.15}
    result = run_monte_carlo(metrics, 10_000, 2, 50, 0, seed=123)

    assert set(result["percentile_outcomes"]) == {5, 10, 25, 50, 75, 90, 95}


async def test_simulation_request_rejects_too_many_simulations() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(_payload(n_simulations=1001))


async def test_simulation_request_rejects_too_many_years() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(_payload(years=31))


async def test_simulation_request_rejects_zero_years() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(_payload(years=0))


async def test_simulation_request_rejects_weights_not_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(_payload(weights=[0.3, 0.3]))


async def test_simulation_request_rejects_negative_weight() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest.model_validate(_payload(weights=[1.1, -0.1]))


async def test_simulation_post_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/simulation/monte-carlo", json=_payload())
    assert resp.status_code == 401


async def test_simulation_post_valid_request_returns_pending(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_celery_dispatch(monkeypatch)
    headers = await _register_and_login(client)

    resp = await client.post("/api/v1/simulation/monte-carlo", json=_payload(), headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["simulation_id"]
    assert uuid.UUID(body["task_id"])
    assert body["status"] == "PENDING"


async def test_simulation_get_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/simulation/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_simulation_get_wrong_user_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_celery_dispatch(monkeypatch)
    headers_a = await _register_and_login(client)
    headers_b = await _register_and_login(client)
    created = (
        await client.post("/api/v1/simulation/monte-carlo", json=_payload(), headers=headers_a)
    ).json()

    resp = await client.get(f"/api/v1/simulation/{created['simulation_id']}", headers=headers_b)

    assert resp.status_code == 404


async def test_simulation_get_pending_status_has_null_result(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_celery_dispatch(monkeypatch)
    headers = await _register_and_login(client)
    created = (
        await client.post("/api/v1/simulation/monte-carlo", json=_payload(), headers=headers)
    ).json()

    resp = await client.get(f"/api/v1/simulation/{created['simulation_id']}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["simulation_id"] == created["simulation_id"]
    assert body["status"] == "PENDING"
    assert body["result"] is None
    assert body["error"] is None


async def test_simulation_get_unknown_id_returns_404(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.get(f"/api/v1/simulation/{uuid.uuid4()}", headers=headers)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_simulation_post_with_other_users_portfolio_returns_404(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_celery_dispatch(monkeypatch)
    # Create portfolio under user A
    headers_a = await _register_and_login(client)
    portfolio_resp = await client.post(
        "/api/v1/portfolios",
        json={"name": "User A Portfolio"},
        headers=headers_a,
    )
    assert portfolio_resp.status_code == 201
    portfolio_id = portfolio_resp.json()["id"]

    # User B attempts to submit a simulation referencing user A's portfolio_id
    headers_b = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/simulation/monte-carlo",
        json=_payload(portfolio_id=portfolio_id),
        headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_simulation_request_rejects_duplicate_tickers() -> None:
    with pytest.raises(ValidationError):
        SimulationRequest(
            tickers=["AAPL", "aapl"],
            weights=[0.5, 0.5],
        )
