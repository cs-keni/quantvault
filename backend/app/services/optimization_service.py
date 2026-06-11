"""Efficient frontier optimization and Celery task orchestration.

This module owns Markowitz mean-variance optimization. Routes validate and
dispatch; all financial math lives here. The optimizer uses arithmetic expected
returns in constraints because they are linear in weights, then reports
geometrically compounded annual returns in API-facing points.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pandas as pd
import redis
from celery.exceptions import SoftTimeLimitExceeded
from scipy.optimize import minimize

from app.celery_app import celery_app
from app.core.config import settings
from app.schemas.portfolio import FrontierPoint, FrontierResult
from app.services.market_data_service import MarketDataService

_logger = logging.getLogger(__name__)

_TRADING_DAYS = 252
_VOL_FLOOR = 1e-8
_FRONTIER_CACHE_TTL = 86_400


def build_frontier_cache_key(tickers: list[str], period: str) -> str:
    """Return the Redis cache key for a frontier request.

    Tickers are uppercased and sorted so `(AAPL, MSFT)` and `(msft, aapl)`
    share one cached optimization result. The risk-free rate is intentionally
    excluded; a 24-hour stale Sharpe ratio is acceptable for this MVP cache.
    """
    normalized = sorted(ticker.upper() for ticker in tickers)
    return f"qv:opt:frontier:{','.join(normalized)}:{period}"


def serialize_frontier_result(result: FrontierResult) -> str:
    """Serialize a frontier result to the stable JSON shape stored in Redis."""
    return result.model_dump_json()


def deserialize_frontier_result(raw: bytes | str) -> FrontierResult:
    """Deserialize a cached frontier result from Redis JSON."""
    payload = raw.decode() if isinstance(raw, bytes) else raw
    return FrontierResult.model_validate_json(payload)


def _validate_returns_df(returns_df: pd.DataFrame) -> None:
    if returns_df.empty:
        raise ValueError("returns_df must contain at least one row of returns")
    if len(returns_df.columns) < 2:
        raise ValueError("efficient frontier requires at least two assets")


def _annual_arithmetic_return(
    weights: npt.NDArray[np.float64],
    mean_daily_returns: npt.NDArray[np.float64],
) -> float:
    """Arithmetic annual expected return used by linear MPT constraints.

    Formula:
        E[R_p, annual] = 252 * (w.T @ mu_daily)

    This is the optimizer's target-return convention because it is linear in
    weights; using geometric compounding inside the constraint would make the
    target-return constraint non-linear and unstable for SLSQP.
    """
    return float(np.dot(weights, mean_daily_returns) * _TRADING_DAYS)


def _annual_geometric_return(
    weights: npt.NDArray[np.float64],
    mean_daily_returns: npt.NDArray[np.float64],
) -> float:
    """Geometrically compounded annual return for user-facing output.

    Formula:
        mean_daily_portfolio = w.T @ mu_daily
        annual_return = (1 + mean_daily_portfolio)^252 - 1

    This is the financially interpretable reported return: repeated daily mean
    compounding over a 252-trading-day year.
    """
    mean_daily_portfolio = float(np.dot(weights, mean_daily_returns))
    return float((1.0 + mean_daily_portfolio) ** _TRADING_DAYS - 1.0)


def _annual_volatility(
    weights: npt.NDArray[np.float64],
    cov_annual: npt.NDArray[np.float64],
) -> float:
    """Annualized portfolio volatility from the covariance matrix.

    Formula:
        sigma_p = sqrt(w.T @ (Cov_daily * 252) @ w)

    Volatility is the Markowitz risk measure minimized along the efficient
    frontier.
    """
    variance = float(weights.T @ cov_annual @ weights)
    return float(np.sqrt(max(variance, 0.0)))


def _sharpe_ratio(annual_return_arith: float, annual_vol: float, rfr: float) -> float:
    """Sharpe ratio using arithmetic expected return from the optimizer.

    Formula:
        Sharpe = (E[R_p] - R_f) / sigma_p

    Returns 0.0 when volatility is effectively zero to avoid unstable division
    from constant-return series.
    """
    if annual_vol <= _VOL_FLOOR:
        return 0.0
    return (annual_return_arith - rfr) / annual_vol


def _normalize_solver_weights(weights: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    clipped = np.clip(weights, 0.0, 1.0).astype(np.float64)
    total = float(clipped.sum())
    if total <= 0.0:
        raise ValueError("optimizer returned all-zero weights")
    return cast(npt.NDArray[np.float64], clipped / total)


def _frontier_point(
    tickers: list[str],
    weights: npt.NDArray[np.float64],
    mean_daily_returns: npt.NDArray[np.float64],
    cov_annual: npt.NDArray[np.float64],
    rfr: float,
) -> FrontierPoint:
    """Build an API-facing frontier point from optimized weights.

    Annual return is geometric for display, volatility comes from the annual
    covariance matrix, and Sharpe uses the arithmetic optimizer return to stay
    consistent with the max-Sharpe objective.
    """
    normalized = _normalize_solver_weights(weights)
    annual_return_arith = _annual_arithmetic_return(normalized, mean_daily_returns)
    annual_vol = _annual_volatility(normalized, cov_annual)
    return FrontierPoint(
        annual_return=_annual_geometric_return(normalized, mean_daily_returns),
        annual_volatility=annual_vol,
        sharpe_ratio=_sharpe_ratio(annual_return_arith, annual_vol, rfr),
        weights={
            ticker: float(weight)
            for ticker, weight in zip(tickers, normalized, strict=True)
        },
    )


def find_min_variance_portfolio(
    returns_df: pd.DataFrame,
) -> tuple[npt.NDArray[np.float64], float, float]:
    """Find the long-only portfolio with the lowest variance.

    Solves:
        minimize    w.T @ Sigma_annual @ w
        subject to  sum(w) = 1
                    0 <= w_i <= 1

    Returns `(weights, annual_arithmetic_return, annual_volatility)`. The risk
    free rate is not an input because minimum variance is a pure risk
    minimization and does not depend on excess return.
    """
    _validate_returns_df(returns_df)
    n_assets = len(returns_df.columns)
    mean_daily = returns_df.mean().to_numpy(dtype=np.float64)
    cov_annual = returns_df.cov().to_numpy(dtype=np.float64) * _TRADING_DAYS

    def objective(weights: npt.NDArray[np.float64]) -> float:
        return float(weights.T @ cov_annual @ weights)

    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    bounds = [(0.0, 1.0)] * n_assets
    x0 = np.full(n_assets, 1.0 / n_assets, dtype=np.float64)

    result = minimize(objective, x0=x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        raise ValueError(f"minimum-variance optimization failed: {result.message}")

    weights = _normalize_solver_weights(np.asarray(result.x, dtype=np.float64))
    return (
        weights,
        _annual_arithmetic_return(weights, mean_daily),
        _annual_volatility(weights, cov_annual),
    )


def find_max_sharpe_portfolio(
    returns_df: pd.DataFrame,
    rfr: float,
) -> tuple[npt.NDArray[np.float64], float, float, float]:
    """Find the long-only portfolio with the highest Sharpe ratio.

    Solves:
        maximize    (252 * w.T @ mu_daily - R_f) / sqrt(w.T @ Sigma_annual @ w)
        subject to  sum(w) = 1
                    0 <= w_i <= 1

    Returns `(weights, annual_arithmetic_return, annual_volatility, sharpe)`.
    If volatility is effectively zero, the Sharpe objective returns 0.0 so the
    solver does not divide by floating-point noise.
    """
    _validate_returns_df(returns_df)
    n_assets = len(returns_df.columns)
    mean_daily = returns_df.mean().to_numpy(dtype=np.float64)
    cov_annual = returns_df.cov().to_numpy(dtype=np.float64) * _TRADING_DAYS

    def objective(weights: npt.NDArray[np.float64]) -> float:
        annual_vol = _annual_volatility(weights, cov_annual)
        annual_return = _annual_arithmetic_return(weights, mean_daily)
        return -_sharpe_ratio(annual_return, annual_vol, rfr)

    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    bounds = [(0.0, 1.0)] * n_assets
    x0 = np.full(n_assets, 1.0 / n_assets, dtype=np.float64)

    result = minimize(objective, x0=x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        raise ValueError(f"max-Sharpe optimization failed: {result.message}")

    weights = _normalize_solver_weights(np.asarray(result.x, dtype=np.float64))
    annual_return = _annual_arithmetic_return(weights, mean_daily)
    annual_vol = _annual_volatility(weights, cov_annual)
    return weights, annual_return, annual_vol, _sharpe_ratio(annual_return, annual_vol, rfr)


def generate_efficient_frontier(
    returns_df: pd.DataFrame,
    rfr: float,
    n_points: int = 30,
) -> list[FrontierPoint]:
    """Generate the long-only Markowitz efficient frontier.

    The lower target bound is the solved minimum-variance portfolio's
    arithmetic annual return, not the lowest individual asset return. The upper
    bound is the highest individual arithmetic annual return. For each target:

        minimize    w.T @ Sigma_annual @ w
        subject to  sum(w) = 1
                    252 * w.T @ mu_daily >= target
                    0 <= w_i <= 1

    SLSQP runs sequentially with the previous successful weights as the next
    initial guess. If one target is infeasible or fails to converge, it is
    skipped and later targets are still attempted, returning a best-effort
    partial frontier.
    """
    _validate_returns_df(returns_df)
    if n_points < 1:
        raise ValueError("n_points must be at least 1")

    tickers = list(returns_df.columns)
    n_assets = len(tickers)
    mean_daily = returns_df.mean().to_numpy(dtype=np.float64)
    cov_annual = returns_df.cov().to_numpy(dtype=np.float64) * _TRADING_DAYS

    min_weights, min_return, _ = find_min_variance_portfolio(returns_df)
    max_individual_return = float(np.max(mean_daily * _TRADING_DAYS))
    targets = np.linspace(min_return, max_individual_return, n_points)

    def objective(weights: npt.NDArray[np.float64]) -> float:
        return float(weights.T @ cov_annual @ weights)

    bounds = [(0.0, 1.0)] * n_assets
    x0 = min_weights
    points: list[FrontierPoint] = []

    for target in targets:
        constraints = [
            {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},
            {
                "type": "ineq",
                "fun": lambda w, target=target: _annual_arithmetic_return(w, mean_daily)
                - float(target),
            },
        ]
        result = minimize(
            objective,
            x0=x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )
        if not result.success:
            _logger.warning("frontier target %.6f skipped: %s", target, result.message)
            continue

        weights = _normalize_solver_weights(np.asarray(result.x, dtype=np.float64))
        points.append(_frontier_point(tickers, weights, mean_daily, cov_annual, rfr))
        x0 = weights

    if not points:
        raise ValueError("efficient frontier optimization produced no feasible points")
    return points


def _calculate_frontier_result(
    tickers: list[str],
    period: str,
    returns_df: pd.DataFrame,
    dropped_tickers: list[str],
    rfr: float,
) -> FrontierResult:
    """Assemble the full efficient frontier result from fetched returns.

    Surviving tickers are taken from `returns_df.columns`; the optimizer works
    only on data that passed the market-data quality pipeline. The result
    includes separate min-variance and max-Sharpe points for chart callouts.
    """
    if returns_df.empty:
        raise ValueError("No usable historical data for the requested tickers.")
    if len(returns_df.columns) < 2:
        raise ValueError("Efficient frontier requires at least two surviving tickers.")

    surviving_tickers = list(returns_df.columns)
    mean_daily = returns_df.mean().to_numpy(dtype=np.float64)
    cov_annual = returns_df.cov().to_numpy(dtype=np.float64) * _TRADING_DAYS

    min_weights, _, _ = find_min_variance_portfolio(returns_df)
    max_weights, _, _, _ = find_max_sharpe_portfolio(returns_df, rfr)
    frontier = generate_efficient_frontier(returns_df, rfr, n_points=100)

    return FrontierResult(
        tickers=surviving_tickers,
        period=period,
        risk_free_rate=rfr,
        frontier=frontier,
        min_variance=_frontier_point(
            surviving_tickers, min_weights, mean_daily, cov_annual, rfr
        ),
        max_sharpe=_frontier_point(surviving_tickers, max_weights, mean_daily, cov_annual, rfr),
        dropped_tickers=dropped_tickers,
        n_trading_days=len(returns_df),
    )


def _fetch_risk_free_rate_sync(market_service: MarketDataService) -> float:
    try:
        return market_service._fetch_rfr()
    except Exception as exc:
        _logger.warning("risk-free rate fetch failed, using 0.04 fallback: %s", exc)
        return 0.04


@celery_app.task(bind=True, soft_time_limit=55, time_limit=60)
def compute_frontier(self: Any, tickers: list[str], period: str) -> dict[str, Any]:
    """Celery task for efficient frontier computation.

    The worker uses sync yfinance and sync Redis only. It checks the same
    24-hour cache as the POST endpoint, fetches historical returns directly via
    `MarketDataService._fetch_and_process_returns()`, computes the Markowitz
    frontier, then stores the JSON result for future identical requests.
    """
    normalized_tickers = sorted(ticker.upper() for ticker in tickers)
    cache_key = build_frontier_cache_key(normalized_tickers, period)
    # rediss:// (Upstash TLS) requires explicit ssl_cert_reqs in redis-py's sync client.
    ssl_kwargs = {"ssl_cert_reqs": "CERT_NONE"} if settings.REDIS_URL.startswith("rediss://") else {}
    redis_client = redis.Redis.from_url(settings.REDIS_URL, **ssl_kwargs)
    try:
        cached = cast(bytes | str | None, redis_client.get(cache_key))
        if cached is not None:
            try:
                return deserialize_frontier_result(cached).model_dump(mode="json")
            except (ValueError, Exception) as exc:
                _logger.warning("frontier cache deserialization failed key=%s: %s", cache_key, exc)

        market_service = MarketDataService(cast(Any, redis_client))
        returns_df, dropped = market_service._fetch_and_process_returns(normalized_tickers, period)
        rfr = _fetch_risk_free_rate_sync(market_service)
        result = _calculate_frontier_result(
            tickers=normalized_tickers,
            period=period,
            returns_df=returns_df,
            dropped_tickers=dropped,
            rfr=rfr,
        )
        redis_client.setex(cache_key, _FRONTIER_CACHE_TTL, serialize_frontier_result(result))
        return result.model_dump(mode="json")
    except SoftTimeLimitExceeded as exc:
        raise TimeoutError("Efficient frontier computation timed out after 55 seconds.") from exc
    finally:
        cast(Any, redis_client).close()
