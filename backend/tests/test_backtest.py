"""Backtesting engine math and API tests."""

import os
import uuid
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd
import pytest
from app.api.v1 import backtest as backtest_api
from app.models.backtest_result import RebalanceFrequency
from app.services.backtest_service import run_backtest_engine
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    email = f"backtest_test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpassword123", "full_name": "Test User"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_portfolio(
    client: AsyncClient,
    headers: dict[str, str],
    weights: tuple[float, float] = (0.6, 0.4),
) -> str:
    portfolio = (
        await client.post(
            "/api/v1/portfolios",
            json={"name": "Backtest P", "benchmark_ticker": "SPY"},
            headers=headers,
        )
    ).json()
    for ticker, weight in zip(["AAA", "BBB"], weights, strict=True):
        await client.post(
            f"/api/v1/portfolios/{portfolio['id']}/holdings",
            json={
                "ticker": ticker,
                "asset_name": ticker,
                "asset_class": "EQUITY",
                "target_weight": f"{weight:.5f}",
            },
            headers=headers,
        )
    return str(portfolio["id"])


def _backtest_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "start_date": "2020-01-01",
        "end_date": "2020-03-31",
        "rebalance_frequency": "MONTHLY",
        "initial_investment": "10000.00",
    }
    payload.update(overrides)
    return payload


class _FakeTask:
    id = "fake-backtest-task"


def _patch_backtest_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop_preflight(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(backtest_api, "_preflight_market_data", _noop_preflight)
    monkeypatch.setattr(backtest_api.run_backtest, "delay", lambda *args, **kwargs: _FakeTask())


def _returns_df(n_days: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "AAA": np.full(n_days, 0.001, dtype=np.float64),
            "BBB": np.full(n_days, 0.002, dtype=np.float64),
        },
        index=pd.date_range("2020-01-02", periods=n_days, freq="B"),
    )


async def test_backtest_constant_returns_terminal_cagr() -> None:
    returns_df = _returns_df(10)
    benchmark = pd.Series(np.full(10, 0.0015), index=returns_df.index)
    weights = np.array([0.6, 0.4], dtype=np.float64)
    result = run_backtest_engine(
        returns_df, benchmark, weights, 10_000, RebalanceFrequency.NEVER, rfr=0.0
    )

    final = 10_000 * (0.6 * (1.0 + 0.001) ** 10 + 0.4 * (1.0 + 0.002) ** 10)
    expected_cagr = (final / 10_000) ** (252 / 10) - 1
    assert result["tearsheet"]["cagr"] == pytest.approx(expected_cagr)


async def test_backtest_never_rebalance_true_buy_and_hold() -> None:
    returns_df = pd.DataFrame(
        {"AAA": [0.01, 0.01, 0.01], "BBB": [0.0, 0.0, 0.0]},
        index=pd.date_range("2020-01-02", periods=3, freq="B"),
    )
    benchmark = pd.Series([0.0, 0.0, 0.0], index=returns_df.index)
    weights = np.array([0.5, 0.5], dtype=np.float64)

    result = run_backtest_engine(
        returns_df, benchmark, weights, 10_000, RebalanceFrequency.NEVER, rfr=0.0
    )

    expected = 10_000 * (0.5 * (1.01**3) + 0.5 * 1.0)
    assert result["equity_curve"][-1]["portfolio"] == pytest.approx(expected)
    assert result["tearsheet"]["rebalance_count"] == 0


async def test_backtest_monthly_rebalance_count() -> None:
    returns_df = pd.DataFrame(
        {"AAA": np.full(65, 0.001), "BBB": np.full(65, -0.0002)},
        index=pd.date_range("2020-01-02", periods=65, freq="B"),
    )
    benchmark = pd.Series(np.full(65, 0.0005), index=returns_df.index)
    result = run_backtest_engine(
        returns_df,
        benchmark,
        np.array([0.5, 0.5], dtype=np.float64),
        10_000,
        RebalanceFrequency.MONTHLY,
        rfr=0.0,
    )

    assert result["tearsheet"]["rebalance_count"] == 3


async def test_backtest_win_rate_positive_days() -> None:
    returns_df = pd.DataFrame(
        {"AAA": [0.01, 0.01, 0.01, -0.01, -0.01], "BBB": [0, 0, 0, 0, 0]},
        index=pd.date_range("2020-01-02", periods=5, freq="B"),
    )
    benchmark = pd.Series([0, 0, 0, 0, 0], index=returns_df.index)
    result = run_backtest_engine(
        returns_df,
        benchmark,
        np.array([1.0, 0.0], dtype=np.float64),
        10_000,
        RebalanceFrequency.NEVER,
        rfr=0.0,
    )

    assert result["tearsheet"]["win_rate"] == pytest.approx(0.6)


async def test_backtest_jensen_alpha_beta_one() -> None:
    benchmark_values = np.array([0.01, -0.005, 0.008, -0.002, 0.004], dtype=np.float64)
    portfolio_values = benchmark_values + 0.001
    index = pd.date_range("2020-01-02", periods=5, freq="B")
    returns_df = pd.DataFrame({"AAA": portfolio_values}, index=index)
    benchmark = pd.Series(benchmark_values, index=index)
    result = run_backtest_engine(
        returns_df,
        benchmark,
        np.array([1.0], dtype=np.float64),
        10_000,
        RebalanceFrequency.NEVER,
        rfr=0.0,
    )

    ts = result["tearsheet"]
    assert ts["beta"] == pytest.approx(1.0)
    assert ts["alpha"] == pytest.approx(ts["cagr"] - ts["benchmark_cagr"])


async def test_backtest_calmar_none_when_no_drawdown() -> None:
    returns_df = _returns_df(8)
    benchmark = pd.Series(np.full(8, 0.001), index=returns_df.index)
    result = run_backtest_engine(
        returns_df,
        benchmark,
        np.array([0.5, 0.5], dtype=np.float64),
        10_000,
        RebalanceFrequency.NEVER,
        rfr=0.0,
    )

    assert result["tearsheet"]["max_drawdown"] == 0.0
    assert result["tearsheet"]["calmar"] is None


async def test_backtest_all_negative_returns_declines() -> None:
    returns_df = pd.DataFrame(
        {"AAA": np.full(8, -0.01), "BBB": np.full(8, -0.02)},
        index=pd.date_range("2020-01-02", periods=8, freq="B"),
    )
    benchmark = pd.Series(np.full(8, -0.01), index=returns_df.index)
    result = run_backtest_engine(
        returns_df,
        benchmark,
        np.array([0.5, 0.5], dtype=np.float64),
        10_000,
        RebalanceFrequency.NEVER,
        rfr=0.0,
    )

    equity = [point["portfolio"] for point in result["equity_curve"]]
    assert result["tearsheet"]["max_drawdown"] < 0
    assert all(next_value < current for current, next_value in pairwise(equity))


async def test_backtest_post_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"/api/v1/portfolios/{uuid.uuid4()}/backtests", json=_backtest_payload())
    assert resp.status_code == 401


async def test_backtest_post_valid_request_returns_pending(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers)

    resp = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/backtests",
        json=_backtest_payload(),
        headers=headers,
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["backtest_id"]
    assert body["task_id"] == "fake-backtest-task"
    assert body["status"] == "PENDING"


async def test_backtest_post_non_owned_portfolio_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers_a = await _register_and_login(client)
    headers_b = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers_a)

    resp = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/backtests",
        json=_backtest_payload(),
        headers=headers_b,
    )

    assert resp.status_code == 404


async def test_backtest_post_empty_portfolio_returns_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers = await _register_and_login(client)
    portfolio = (
        await client.post("/api/v1/portfolios", json={"name": "Empty"}, headers=headers)
    ).json()

    resp = await client.post(
        f"/api/v1/portfolios/{portfolio['id']}/backtests",
        json=_backtest_payload(),
        headers=headers,
    )

    assert resp.status_code == 422


async def test_backtest_post_weights_not_sum_to_one_returns_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers, weights=(0.3, 0.3))

    resp = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/backtests",
        json=_backtest_payload(),
        headers=headers,
    )

    assert resp.status_code == 422


async def test_backtest_get_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/portfolios/{uuid.uuid4()}/backtests/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_backtest_get_wrong_user_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers_a = await _register_and_login(client)
    headers_b = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers_a)
    created = (
        await client.post(
            f"/api/v1/portfolios/{portfolio_id}/backtests",
            json=_backtest_payload(),
            headers=headers_a,
        )
    ).json()

    resp = await client.get(
        f"/api/v1/portfolios/{portfolio_id}/backtests/{created['backtest_id']}",
        headers=headers_b,
    )

    assert resp.status_code == 404


async def test_backtest_get_pending_has_null_results(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers)
    created = (
        await client.post(
            f"/api/v1/portfolios/{portfolio_id}/backtests",
            json=_backtest_payload(),
            headers=headers,
        )
    ).json()

    resp = await client.get(
        f"/api/v1/portfolios/{portfolio_id}/backtests/{created['backtest_id']}",
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["tearsheet"] is None
    assert body["daily_returns"] is None
    assert body["equity_curve"] is None


async def test_backtest_get_unknown_id_returns_404(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    resp = await client.get(
        f"/api/v1/portfolios/{uuid.uuid4()}/backtests/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_backtest_list_summary_excludes_arrays(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers)
    await client.post(
        f"/api/v1/portfolios/{portfolio_id}/backtests",
        json=_backtest_payload(),
        headers=headers,
    )

    resp = await client.get(f"/api/v1/portfolios/{portfolio_id}/backtests", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "equity_curve" not in body[0]
    assert "daily_returns" not in body[0]


async def test_backtest_list_wrong_user_empty(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_backtest_dependencies(monkeypatch)
    headers_a = await _register_and_login(client)
    headers_b = await _register_and_login(client)
    portfolio_id = await _create_portfolio(client, headers_a)
    await client.post(
        f"/api/v1/portfolios/{portfolio_id}/backtests",
        json=_backtest_payload(),
        headers=headers_a,
    )

    resp = await client.get(f"/api/v1/portfolios/{portfolio_id}/backtests", headers=headers_b)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.skipif(not os.getenv("INTEGRATION_TESTS"), reason="Set INTEGRATION_TESTS=1")
async def test_backtest_spy_live_smoke() -> None:
    pytest.skip("Live yfinance backtest smoke is enabled only during manual integration runs.")
