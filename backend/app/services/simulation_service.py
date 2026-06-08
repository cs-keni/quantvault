"""Monte Carlo portfolio simulation and Celery task orchestration.

All simulation math lives in this service. Routes create persistent
`SimulationResult` rows and dispatch Celery; workers fetch market data,
compute portfolio metrics, run the simulation, and write the result blob back
to PostgreSQL.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import redis
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.core.config import settings
from app.models.simulation_result import SimulationResult, SimulationStatus
from app.services.market_data_service import MarketDataService
from app.services.risk_service import calculate_portfolio_metrics

_logger = logging.getLogger(__name__)

_TRADING_DAYS = 252
_T_DF = 5
_SAMPLE_PATH_COUNT = 20


def run_monte_carlo(
    portfolio_metrics: dict[str, float],
    initial_investment: float,
    years: int,
    n_simulations: int,
    annual_contribution: float = 0.0,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run a fat-tailed Monte Carlo projection for a portfolio value.

    Inputs:
        `portfolio_metrics["annualized_return"]` is interpreted as arithmetic
        annual expected return `mu`; `portfolio_metrics["annualized_volatility"]`
        is annual volatility `sigma`.

    Formulas:
        daily_mu    = mu / 252
        daily_sigma = sigma / sqrt(252)
        r_t         = daily_mu + daily_sigma * standard_t(df=5)
        V_t         = V_(t-1) * (1 + r_t)

    The t-distribution is directly scaled by `daily_sigma` rather than
    variance-normalized. With df=5, realized volatility is about 1.29x the
    historical sigma, intentionally preserving fat tails and stress-like
    dispersion. Contributions are injected at each year boundary after that
    day's return, then compound forward in subsequent years.
    """
    if years < 1:
        raise ValueError("years must be at least 1")
    if n_simulations < 1:
        raise ValueError("n_simulations must be at least 1")
    if initial_investment <= 0:
        raise ValueError("initial_investment must be positive")
    if annual_contribution < 0:
        raise ValueError("annual_contribution must be non-negative")

    annual_return = float(portfolio_metrics["annualized_return"])
    annual_volatility = float(portfolio_metrics["annualized_volatility"])
    trading_days = years * _TRADING_DAYS
    daily_mu = annual_return / _TRADING_DAYS
    daily_sigma = annual_volatility / np.sqrt(_TRADING_DAYS)

    rng = np.random.default_rng(seed)
    t_draws = rng.standard_t(df=_T_DF, size=(trading_days, n_simulations))
    random_returns = cast(npt.NDArray[np.float64], daily_mu + daily_sigma * t_draws)

    portfolio_values = np.empty((trading_days, n_simulations), dtype=np.float64)
    current_values = np.full(n_simulations, initial_investment, dtype=np.float64)
    for day in range(trading_days):
        # Floor at zero: equity has limited liability; negative values compound backward.
        current_values = np.maximum(current_values * (1.0 + random_returns[day]), 0.0)
        if (day + 1) % _TRADING_DAYS == 0:
            current_values += annual_contribution
        portfolio_values[day] = current_values

    final_values = portfolio_values[-1]
    total_outlay = initial_investment + annual_contribution * years
    percentiles = [5, 10, 25, 50, 75, 90, 95]
    percentile_values = np.percentile(final_values, percentiles)

    sorted_final_indices = np.argsort(final_values)
    sample_positions = np.linspace(
        0, n_simulations - 1, _SAMPLE_PATH_COUNT, dtype=np.int64
    )
    sample_indices = sorted_final_indices[sample_positions]
    sample_paths = portfolio_values[:, sample_indices].T

    return {
        "percentile_outcomes": {
            percentile: float(value)
            for percentile, value in zip(percentiles, percentile_values, strict=True)
        },
        "sample_paths": sample_paths.tolist(),
        "mean_final_value": float(final_values.mean()),
        "probability_of_profit": float((final_values > total_outlay).mean()),
        "probability_of_doubling": float((final_values > total_outlay * 2.0).mean()),
        "final_value_distribution": final_values.tolist(),
        "initial_investment": float(initial_investment),
        "years": years,
        "n_simulations": n_simulations,
        "annual_contribution": float(annual_contribution),
    }


async def _write_result_to_db(
    simulation_id: uuid.UUID,
    status: SimulationStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    task_id: str | None = None,
) -> None:
    # NullPool: single-use connection — no pool overhead for one-off Celery writes.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            simulation = await session.get(SimulationResult, simulation_id)
            if simulation is None:
                _logger.warning("simulation result %s not found for task write", simulation_id)
                return
            simulation.status = status
            simulation.results = result
            simulation.error = error
            if task_id is not None:
                simulation.task_id = task_id
            await session.commit()
    finally:
        await engine.dispose()


def _write_result_to_db_sync(
    simulation_id: uuid.UUID,
    status: SimulationStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    task_id: str | None = None,
) -> None:
    # Only called from real Celery workers (no running event loop).
    # In eager mode (USE_CELERY=false), the endpoint handles DB writes directly.
    asyncio.run(_write_result_to_db(simulation_id, status, result, error, task_id))


@celery_app.task(bind=True, soft_time_limit=55, time_limit=60)
def run_simulation(self: Any, simulation_id: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Celery task for a persisted Monte Carlo simulation.

    In eager mode (USE_CELERY=false): returns a result dict for the endpoint to
    persist — avoids asyncio-in-asyncio conflicts when the task runs synchronously
    inside FastAPI's event loop.

    In real worker mode: writes SUCCESS/FAILURE directly to the simulation_results
    row using a fresh async engine.
    """
    simulation_uuid = uuid.UUID(simulation_id)
    task_id = cast(str | None, getattr(self.request, "id", None))
    # rediss:// (Upstash TLS) requires explicit ssl_cert_reqs in redis-py's sync client.
    # "CERT_NONE" is the accepted string constant (ssl.CERT_NONE = 0).
    _ssl = {"ssl_cert_reqs": "CERT_NONE"} if settings.REDIS_URL.startswith("rediss://") else {}
    redis_client = redis.Redis.from_url(settings.REDIS_URL, **_ssl)
    eager = celery_app.conf.task_always_eager
    try:
        tickers = [str(ticker).upper() for ticker in params["tickers"]]
        weights = np.asarray(params["weights"], dtype=np.float64)
        period = str(params["period"])

        market_service = MarketDataService(cast(Any, redis_client))
        returns_df, dropped = market_service._fetch_and_process_returns(tickers, period)
        if dropped:
            raise ValueError(
                f"Simulation rejected because market data dropped tickers: {', '.join(dropped)}"
            )
        if returns_df.empty:
            raise ValueError("No usable historical data for the requested tickers.")

        metrics = calculate_portfolio_metrics(returns_df, weights)
        result = run_monte_carlo(
            portfolio_metrics={
                # Use arithmetic annual return (mean_daily * 252) per the spec — NOT
                # geometric annual return, which would overstate daily drift by ~4%.
                "annualized_return": metrics["mean_daily_return"] * 252,
                "annualized_volatility": metrics["annual_volatility"],
            },
            initial_investment=float(params["initial_investment"]),
            years=int(params["years"]),
            n_simulations=int(params["n_simulations"]),
            annual_contribution=float(params.get("annual_contribution", 0.0)),
            seed=cast(int | None, params.get("seed")),
        )
        if eager:
            return {"ok": True, "result": result, "task_id": task_id}
        _write_result_to_db_sync(
            simulation_uuid,
            SimulationStatus.SUCCESS,
            result=result,
            error=None,
            task_id=task_id,
        )
        return None
    except SoftTimeLimitExceeded:
        if not eager:
            try:
                _write_result_to_db_sync(
                    simulation_uuid,
                    SimulationStatus.FAILURE,
                    result=None,
                    error="timeout",
                    task_id=task_id,
                )
            except Exception:
                _logger.exception(
                    "failed to write timeout failure for simulation_id=%s", simulation_id
                )
        return {"ok": False, "error": "timeout", "task_id": task_id} if eager else None
    except Exception as exc:
        _logger.exception("simulation task failed simulation_id=%s", simulation_id)
        if not eager:
            try:
                _write_result_to_db_sync(
                    simulation_uuid,
                    SimulationStatus.FAILURE,
                    result=None,
                    error=str(exc)[:2000],
                    task_id=task_id,
                )
            except Exception:
                _logger.exception(
                    "failed to write failure for simulation_id=%s", simulation_id
                )
        return {"ok": False, "error": str(exc)[:2000], "task_id": task_id} if eager else None
    finally:
        cast(Any, redis_client).close()
