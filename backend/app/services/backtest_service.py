"""Backtesting engine and Celery task orchestration.

All backtest math lives here. API routes validate ownership and create PENDING
rows; workers fetch market data, run the pure backtest engine, and persist the
result blobs back to PostgreSQL.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pandas as pd
import redis
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.core.config import settings
from app.models.backtest_result import BacktestResult, BacktestStatus, RebalanceFrequency
from app.services.market_data_service import MarketDataService
from app.services.risk_service import (
    calculate_beta_from_returns,
    calculate_max_drawdown,
    calculate_sortino,
)

_logger = logging.getLogger(__name__)

_TRADING_DAYS = 252
_VOL_FLOOR = 1e-8


def _period_key(ts: pd.Timestamp, frequency: RebalanceFrequency) -> tuple[int, int] | int:
    if frequency == RebalanceFrequency.MONTHLY:
        return (int(ts.year), int(ts.month))
    if frequency == RebalanceFrequency.QUARTERLY:
        return (int(ts.year), (int(ts.month) - 1) // 3)
    if frequency == RebalanceFrequency.ANNUALLY:
        return int(ts.year)
    return 0


def _cagr(final_value: float, initial_investment: float, n_trading_days: int) -> float:
    """True terminal CAGR from start/end values.

    Formula:
        CAGR = (final_value / initial_investment) ** (252 / n_trading_days) - 1

    This intentionally does not use `calculate_portfolio_metrics()`, whose
    geometric return from mean daily returns is not the same as terminal CAGR.
    """
    if final_value <= 0.0:
        return -1.0
    return float((final_value / initial_investment) ** (_TRADING_DAYS / n_trading_days) - 1.0)


def _sharpe_ratio(daily_returns: pd.Series, cagr: float, rfr: float) -> float:
    """Sharpe ratio from terminal CAGR and annualized realized volatility.

    Formula:
        sigma_annual = std(daily_returns, ddof=1) * sqrt(252)
        sharpe = (CAGR - rfr) / sigma_annual
    """
    annual_vol = float(daily_returns.std(ddof=1) * np.sqrt(_TRADING_DAYS))
    if annual_vol <= _VOL_FLOOR:
        return 0.0
    return (cagr - rfr) / annual_vol


def _equity_from_rebalanced_returns(
    returns_df: pd.DataFrame,
    weights: npt.NDArray[np.float64],
    initial_investment: float,
    rebalance_frequency: RebalanceFrequency,
) -> tuple[npt.NDArray[np.float64], int]:
    """Simulate dollar buckets with rebalancing at calendar period boundaries.

    Each asset bucket earns its own daily return. On the first trading day of a
    new month/quarter/year, the day's return is applied first, then buckets are
    reset to target weights. The total equity is unchanged by the rebalance,
    but this timing makes rebalance counts verifiable and avoids look-ahead.
    """
    asset_values = weights * initial_investment
    equity_values: list[float] = []
    previous_key = _period_key(pd.Timestamp(returns_df.index[0]), rebalance_frequency)
    rebalance_count = 0

    for ts, row in returns_df.iterrows():
        asset_values *= 1.0 + row.to_numpy(dtype=np.float64)
        current_key = _period_key(pd.Timestamp(ts), rebalance_frequency)
        if current_key != previous_key:
            total_value = float(asset_values.sum())
            asset_values = weights * total_value
            rebalance_count += 1
            previous_key = current_key
        equity_values.append(float(asset_values.sum()))

    return np.asarray(equity_values, dtype=np.float64), rebalance_count


def run_backtest_engine(
    returns_df: pd.DataFrame,
    benchmark_returns: pd.Series,
    weights: npt.NDArray[np.float64],
    initial_investment: float,
    rebalance_frequency: RebalanceFrequency,
    rfr: float = 0.04,
) -> dict[str, Any]:
    """Run a portfolio backtest against a benchmark return series.

    Formulas:
        NEVER equity_t = initial * sum_i(w_i * prod_s<=t(1 + r_i,s))
        Rebalanced equity uses per-asset dollar buckets, reset to target weights
        after the first trading day's return in each new calendar period.
        Benchmark equity_t = initial * prod_s<=t(1 + r_benchmark,s)
        CAGR = (final / initial) ** (252 / n_trading_days) - 1
        Jensen alpha = CAGR_p - (rfr + beta * (CAGR_b - rfr))

    The risk-free rate is a static current ^TNX approximation. That is
    acceptable for this demo but historically imperfect for long date ranges.
    """
    if returns_df.empty:
        raise ValueError("returns_df must not be empty")
    if benchmark_returns.empty:
        raise ValueError("benchmark_returns must not be empty")
    if len(returns_df.columns) != len(weights):
        raise ValueError("weights length must match returns_df columns")

    aligned = pd.concat([returns_df, benchmark_returns.rename("benchmark")], axis=1).dropna()
    if aligned.empty:
        raise ValueError("portfolio and benchmark returns have no overlapping dates")
    portfolio_returns_df = aligned[list(returns_df.columns)]
    benchmark_series = aligned["benchmark"]
    n_days = len(aligned)

    if rebalance_frequency == RebalanceFrequency.NEVER:
        cumulative_asset_returns = (1.0 + portfolio_returns_df).cumprod()
        portfolio_equity = (
            initial_investment * cumulative_asset_returns.to_numpy(dtype=np.float64) @ weights
        )
        rebalance_count = 0
    else:
        portfolio_equity, rebalance_count = _equity_from_rebalanced_returns(
            portfolio_returns_df, weights, initial_investment, rebalance_frequency
        )

    benchmark_equity = (
        initial_investment * (1.0 + benchmark_series).cumprod().to_numpy(dtype=np.float64)
    )
    if not np.all(np.isfinite(portfolio_equity)):
        raise ValueError(
            "Portfolio equity contains non-finite values — check for extreme daily returns "
            "or a total-wipeout position."
        )
    previous_portfolio = np.concatenate(
        [np.array([initial_investment], dtype=np.float64), portfolio_equity[:-1]]
    )
    portfolio_daily_returns = pd.Series(
        portfolio_equity / previous_portfolio - 1.0,
        index=aligned.index,
        dtype=np.float64,
    )

    cagr = _cagr(float(portfolio_equity[-1]), initial_investment, n_days)
    benchmark_cagr = _cagr(float(benchmark_equity[-1]), initial_investment, n_days)
    drawdown = calculate_max_drawdown(portfolio_daily_returns)
    max_drawdown = float(drawdown["max_drawdown"])
    beta = calculate_beta_from_returns(portfolio_daily_returns, benchmark_series)
    alpha = cagr - (rfr + beta * (benchmark_cagr - rfr))
    calmar = (cagr / abs(max_drawdown)) if max_drawdown != 0.0 else None

    tearsheet = {
        "cagr": cagr,
        "sharpe": _sharpe_ratio(portfolio_daily_returns, cagr, rfr),
        "sortino": calculate_sortino(portfolio_daily_returns, cagr, rfr),
        "calmar": calmar,
        "beta": beta,
        "alpha": alpha,
        "win_rate": float((portfolio_daily_returns > 0.0).mean()),
        "max_drawdown": max_drawdown,
        "rebalance_count": rebalance_count,
        "benchmark_cagr": benchmark_cagr,
        "final_value": float(portfolio_equity[-1]),
        "benchmark_final_value": float(benchmark_equity[-1]),
        "n_trading_days": n_days,
        "risk_free_rate": rfr,
    }
    equity_curve = [
        {
            "date": str(pd.Timestamp(ts).date()),
            "portfolio": float(portfolio_value),
            "benchmark": float(benchmark_value),
        }
        for ts, portfolio_value, benchmark_value in zip(
            aligned.index, portfolio_equity, benchmark_equity, strict=True
        )
    ]
    return {
        "tearsheet": tearsheet,
        "daily_returns": portfolio_daily_returns.astype(float).tolist(),
        "equity_curve": equity_curve,
    }


async def _write_result_to_db(
    backtest_id: uuid.UUID,
    status: BacktestStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    task_id: str | None = None,
) -> None:
    # NullPool: single-use connection — no pool overhead for one-off Celery writes.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            backtest = await session.get(BacktestResult, backtest_id)
            if backtest is None:
                _logger.warning("backtest result %s not found for task write", backtest_id)
                return
            if backtest.status != BacktestStatus.PENDING:
                # Guard against duplicate task execution or SoftTimeLimitExceeded
                # firing after a successful commit — don't overwrite a settled result.
                _logger.warning(
                    "backtest %s already settled as %s — skipping write",
                    backtest_id,
                    backtest.status,
                )
                return
            backtest.status = status
            if result is not None:
                backtest.tearsheet = cast(dict[str, Any], result["tearsheet"])
                backtest.daily_returns = cast(list[float], result["daily_returns"])
                backtest.equity_curve = cast(list[dict[str, Any]], result["equity_curve"])
            backtest.error = error
            if task_id is not None:
                backtest.task_id = task_id
            await session.commit()
    finally:
        await engine.dispose()


def _write_result_to_db_sync(
    backtest_id: uuid.UUID,
    status: BacktestStatus,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    task_id: str | None = None,
) -> None:
    # asyncio.run() is safe only with Celery's default prefork pool.
    # Do not switch to --pool=gevent or --pool=eventlet without replacing this.
    asyncio.run(_write_result_to_db(backtest_id, status, result, error, task_id))


def _fetch_risk_free_rate_sync(market_service: MarketDataService) -> float:
    try:
        return market_service._fetch_rfr()
    except Exception as exc:
        _logger.warning("risk-free rate fetch failed, using 0.04 fallback: %s", exc)
        return 0.04


@celery_app.task(bind=True, soft_time_limit=55, time_limit=60)
def run_backtest(self: Any, backtest_id: str, params: dict[str, Any]) -> None:
    """Celery task for a persisted backtest run."""
    backtest_uuid = uuid.UUID(backtest_id)
    task_id = cast(str | None, getattr(self.request, "id", None))
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    try:
        tickers = [str(ticker).upper() for ticker in params["tickers"]]
        weights = np.asarray(params["weights"], dtype=np.float64)
        benchmark_ticker = str(params["benchmark_ticker"]).upper()
        start_date = date.fromisoformat(str(params["start_date"]))
        end_date = date.fromisoformat(str(params["end_date"]))
        rebalance_frequency = RebalanceFrequency(str(params["rebalance_frequency"]))
        initial_investment = float(params["initial_investment"])

        market_service = MarketDataService(cast(Any, redis_client))
        returns_df, dropped = market_service._fetch_and_process_returns_by_date(
            tickers, start_date, end_date
        )
        if dropped:
            raise ValueError(f"Backtest rejected because market data dropped: {', '.join(dropped)}")
        benchmark_df, benchmark_dropped = market_service._fetch_and_process_returns_by_date(
            [benchmark_ticker], start_date, end_date
        )
        if benchmark_dropped or benchmark_df.empty:
            raise ValueError(f"No usable benchmark data for {benchmark_ticker}.")
        if returns_df.empty:
            raise ValueError("No usable historical data for the requested tickers.")

        result = run_backtest_engine(
            returns_df=returns_df,
            benchmark_returns=benchmark_df[benchmark_ticker],
            weights=weights,
            initial_investment=initial_investment,
            rebalance_frequency=rebalance_frequency,
            rfr=_fetch_risk_free_rate_sync(market_service),
        )
        _write_result_to_db_sync(
            backtest_uuid,
            BacktestStatus.SUCCESS,
            result=result,
            error=None,
            task_id=task_id,
        )
    except SoftTimeLimitExceeded:
        try:
            _write_result_to_db_sync(
                backtest_uuid,
                BacktestStatus.FAILURE,
                result=None,
                error="timeout",
                task_id=task_id,
            )
        except Exception:
            _logger.exception("failed to write timeout failure for backtest_id=%s", backtest_id)
    except Exception as exc:
        _logger.exception("backtest task failed backtest_id=%s", backtest_id)
        try:
            _write_result_to_db_sync(
                backtest_uuid,
                BacktestStatus.FAILURE,
                result=None,
                error=str(exc)[:2000],
                task_id=task_id,
            )
        except Exception:
            _logger.exception("failed to write failure for backtest_id=%s", backtest_id)
    finally:
        cast(Any, redis_client).close()
