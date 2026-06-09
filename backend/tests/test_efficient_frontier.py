"""Efficient frontier math and API tests."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from app.api.v1 import analysis
from app.core.database import get_db
from app.core.redis import get_redis
from app.dependencies import get_current_user
from app.main import create_app
from app.services.optimization_service import (
    find_max_sharpe_portfolio,
    find_min_variance_portfolio,
    generate_efficient_frontier,
)
from celery.result import EagerResult
from httpx import ASGITransport, AsyncClient


class _FakeRedis:
    async def get(self, key: str) -> None:
        return None


async def _fake_db() -> object:
    return object()


async def _fake_redis() -> _FakeRedis:
    return _FakeRedis()


async def _fake_user() -> object:
    return object()


def _frontier_result_dict() -> dict[str, object]:
    return {
        "tickers": ["VTI", "BND"],
        "period": "1y",
        "risk_free_rate": 0.04,
        "frontier": [
            {
                "annual_return": 0.05,
                "annual_volatility": 0.08,
                "sharpe_ratio": 0.125,
                "weights": {"VTI": 0.6, "BND": 0.4},
            }
        ],
        "min_variance": {
            "annual_return": 0.03,
            "annual_volatility": 0.05,
            "sharpe_ratio": -0.2,
            "weights": {"VTI": 0.2, "BND": 0.8},
        },
        "max_sharpe": {
            "annual_return": 0.07,
            "annual_volatility": 0.09,
            "sharpe_ratio": 0.333,
            "weights": {"VTI": 0.8, "BND": 0.2},
        },
        "dropped_tickers": [],
        "n_trading_days": 252,
    }


@asynccontextmanager
async def _frontier_client(*, authenticated: bool) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_redis] = _fake_redis
    if authenticated:
        app.dependency_overrides[get_current_user] = _fake_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def _frontier_returns_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "A": [
                0.010,
                -0.004,
                0.008,
                -0.003,
                0.012,
                -0.005,
                0.006,
                -0.002,
                0.009,
                -0.001,
            ]
            * 3,
            "B": [
                0.004,
                -0.002,
                0.003,
                0.000,
                0.005,
                -0.001,
                0.002,
                0.001,
                0.004,
                0.000,
            ]
            * 3,
            "C": [
                0.002,
                0.003,
                -0.001,
                0.002,
                0.001,
                0.004,
                -0.002,
                0.003,
                0.001,
                0.002,
            ]
            * 3,
        },
        index=pd.date_range("2023-01-02", periods=30, freq="B"),
    )


async def test_frontier_points_have_valid_long_only_weights() -> None:
    points = generate_efficient_frontier(_frontier_returns_df(), rfr=0.0, n_points=25)

    assert 0 < len(points) <= 25
    for point in points:
        weights = np.array(list(point.weights.values()), dtype=np.float64)
        assert np.isclose(weights.sum(), 1.0, atol=1e-6)
        assert np.all(weights >= -1e-9)


async def test_min_variance_has_lower_vol_than_equal_weight() -> None:
    returns_df = _frontier_returns_df()
    weights, _, min_vol = find_min_variance_portfolio(returns_df)
    equal_weights = np.full(len(returns_df.columns), 1.0 / len(returns_df.columns))
    cov_annual = returns_df.cov().to_numpy(dtype=np.float64) * 252
    equal_vol = float(np.sqrt(equal_weights.T @ cov_annual @ equal_weights))

    assert np.isclose(weights.sum(), 1.0, atol=1e-6)
    assert min_vol <= equal_vol + 1e-9


async def test_max_sharpe_weights_valid_and_beats_individual_assets() -> None:
    returns_df = _frontier_returns_df()
    weights, annual_return, annual_vol, sharpe = find_max_sharpe_portfolio(returns_df, rfr=0.0)

    mean_daily = returns_df.mean().to_numpy(dtype=np.float64)
    std_daily = returns_df.std(ddof=1).to_numpy(dtype=np.float64)
    individual_returns = mean_daily * 252
    individual_vols = std_daily * np.sqrt(252)
    individual_sharpes = individual_returns / individual_vols

    assert np.isclose(weights.sum(), 1.0, atol=1e-6)
    assert np.all(weights >= -1e-9)
    assert annual_return > 0
    assert annual_vol > 0
    assert sharpe >= float(np.max(individual_sharpes)) - 1e-6


async def test_two_asset_min_variance_matches_analytic_solution() -> None:
    returns_df = pd.DataFrame(
        {
            "HIGH_VAR": [0.01, -0.01, 0.01, -0.01, 0.0] * 10,
            "LOW_VAR": [0.005, 0.005, -0.005, -0.005, 0.0] * 10,
        }
    )
    cov = returns_df.cov().to_numpy(dtype=np.float64) * 252
    var_a = cov[0, 0]
    var_b = cov[1, 1]
    cov_ab = cov[0, 1]
    expected_a = (var_b - cov_ab) / (var_a + var_b - 2 * cov_ab)

    weights, _, _ = find_min_variance_portfolio(returns_df)

    assert np.isclose(weights[0], expected_a, atol=1e-5)
    assert np.isclose(weights[1], 1.0 - expected_a, atol=1e-5)


async def test_frontier_post_requires_auth() -> None:
    async with _frontier_client(authenticated=False) as client:
        resp = await client.post(
            "/api/v1/analysis/frontier",
            json={"tickers": ["VTI", "BND"], "period": "1y"},
        )
    assert resp.status_code == 401


async def test_frontier_post_duplicate_tickers_after_normalization() -> None:
    async with _frontier_client(authenticated=True) as client:
        resp = await client.post(
            "/api/v1/analysis/frontier",
            json={"tickers": ["AAPL", "aapl"], "period": "1y"},
        )
    assert resp.status_code == 422


async def test_frontier_post_rejects_less_than_two_tickers() -> None:
    async with _frontier_client(authenticated=True) as client:
        resp = await client.post(
            "/api/v1/analysis/frontier",
            json={"tickers": ["AAPL"], "period": "1y"},
        )
    assert resp.status_code == 422


async def test_frontier_post_rejects_invalid_period() -> None:
    async with _frontier_client(authenticated=True) as client:
        resp = await client.post(
            "/api/v1/analysis/frontier",
            json={"tickers": ["AAPL", "MSFT"], "period": "99y"},
        )
    assert resp.status_code == 422


async def test_frontier_post_rejects_more_than_thirty_tickers() -> None:
    tickers = [f"T{i}" for i in range(31)]
    async with _frontier_client(authenticated=True) as client:
        resp = await client.post(
            "/api/v1/analysis/frontier",
            json={"tickers": tickers, "period": "1y"},
        )
    assert resp.status_code == 422


async def test_frontier_get_requires_auth() -> None:
    async with _frontier_client(authenticated=False) as client:
        resp = await client.get("/api/v1/analysis/frontier/task-id")
    assert resp.status_code == 401


async def test_frontier_get_failure_serializes_exception(
    monkeypatch,
) -> None:
    class FakeResult:
        state = "FAILURE"
        info = RuntimeError("worker exploded")

    monkeypatch.setattr(analysis.celery_app, "AsyncResult", lambda task_id: FakeResult())

    async with _frontier_client(authenticated=True) as client:
        resp = await client.get("/api/v1/analysis/frontier/task-id")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"] == "worker exploded"


async def test_frontier_post_eager_mode_returns_success_without_broker(
    monkeypatch,
) -> None:
    calls: list[tuple[str, object]] = []

    def fake_apply(*args: object, **kwargs: object) -> EagerResult:
        calls.append(("apply", kwargs))
        return EagerResult("task-id", _frontier_result_dict(), "SUCCESS")

    def fake_apply_async(*args: object, **kwargs: object) -> None:
        calls.append(("apply_async", kwargs))

    monkeypatch.setattr(analysis.celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(analysis.compute_frontier, "apply", fake_apply)
    monkeypatch.setattr(analysis.compute_frontier, "apply_async", fake_apply_async)

    response = await analysis.submit_frontier(
        analysis.FrontierRequest(tickers=["VTI", "BND"], period="1y"),
        object(),
        _FakeRedis(),
    )

    assert response.status == "SUCCESS"
    assert response.task_id is None
    assert response.result is not None
    assert response.result.tickers == ["VTI", "BND"]
    assert [call[0] for call in calls] == ["apply"]


async def test_frontier_post_worker_mode_uses_apply_async(
    monkeypatch,
) -> None:
    calls: list[tuple[str, object]] = []

    class FakeAsyncTask:
        id = "ignored-by-route"

    def fake_apply(*args: object, **kwargs: object) -> None:
        calls.append(("apply", kwargs))

    def fake_apply_async(*args: object, **kwargs: object) -> FakeAsyncTask:
        calls.append(("apply_async", kwargs))
        return FakeAsyncTask()

    monkeypatch.setattr(analysis.celery_app.conf, "task_always_eager", False)
    monkeypatch.setattr(analysis.compute_frontier, "apply", fake_apply)
    monkeypatch.setattr(analysis.compute_frontier, "apply_async", fake_apply_async)

    response = await analysis.submit_frontier(
        analysis.FrontierRequest(tickers=["VTI", "BND"], period="1y"),
        object(),
        _FakeRedis(),
    )

    assert response.status == "PENDING"
    assert response.task_id is not None
    assert [call[0] for call in calls] == ["apply_async"]
