"""Backtest endpoints for saved portfolios."""

import asyncio
import logging
import uuid
from typing import Annotated

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import CurrentUser
from app.models.backtest_result import BacktestResult, BacktestStatus
from app.schemas.backtest import (
    BacktestRequest,
    BacktestStatusResponse,
    BacktestSubmitResponse,
    BacktestSummary,
    BacktestTearsheet,
    EquityCurvePoint,
)
from celery.result import EagerResult

from app.celery_app import celery_app
from app.services import portfolio_service
from app.services.backtest_service import run_backtest
from app.services.market_data_service import MarketDataService, get_market_data_service

router = APIRouter()
_logger = logging.getLogger(__name__)

_DBDep = Annotated[AsyncSession, Depends(get_db)]
_MarketDep = Annotated[MarketDataService, Depends(get_market_data_service)]


def _business_day_gap(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return int(np.busday_count(start.date().isoformat(), end.date().isoformat()))


def _assert_data_availability(
    returns_df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    label: str,
) -> None:
    if returns_df.empty:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No usable historical data for {label}.",
        )
    first_date = pd.Timestamp(returns_df.index[0])
    last_date = pd.Timestamp(returns_df.index[-1])
    late_start_gap = _business_day_gap(start_date, first_date)
    early_end_gap = _business_day_gap(last_date, end_date)
    if late_start_gap > 5:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} data starts more than 5 trading days after start_date.",
        )
    if early_end_gap > 5:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} data ends more than 5 trading days before end_date.",
        )


async def _preflight_market_data(
    market_service: MarketDataService,
    tickers: list[str],
    benchmark_ticker: str,
    payload: BacktestRequest,
) -> None:
    returns_df, dropped = await asyncio.wait_for(
        asyncio.to_thread(
            market_service._fetch_and_process_returns_by_date,
            tickers,
            payload.start_date,
            payload.end_date,
        ),
        timeout=30.0,
    )
    if dropped:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Backtest rejected because market data dropped: {', '.join(dropped)}",
        )
    benchmark_df, benchmark_dropped = await asyncio.wait_for(
        asyncio.to_thread(
            market_service._fetch_and_process_returns_by_date,
            [benchmark_ticker],
            payload.start_date,
            payload.end_date,
        ),
        timeout=30.0,
    )
    if benchmark_dropped:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No usable benchmark data for {benchmark_ticker}.",
        )
    start_ts = pd.Timestamp(payload.start_date)
    end_ts = pd.Timestamp(payload.end_date)
    _assert_data_availability(returns_df, start_ts, end_ts, "portfolio")
    _assert_data_availability(benchmark_df, start_ts, end_ts, "benchmark")


def _status_response(backtest: BacktestResult) -> BacktestStatusResponse:
    return BacktestStatusResponse(
        backtest_id=backtest.id,
        portfolio_id=backtest.portfolio_id,
        strategy_name=backtest.strategy_name,
        status=backtest.status,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        rebalance_frequency=backtest.rebalance_frequency,
        initial_investment=backtest.initial_investment,
        tearsheet=(
            BacktestTearsheet.model_validate(backtest.tearsheet)
            if backtest.tearsheet is not None
            else None
        ),
        daily_returns=backtest.daily_returns,
        equity_curve=(
            [EquityCurvePoint.model_validate(point) for point in backtest.equity_curve]
            if backtest.equity_curve is not None
            else None
        ),
        error=backtest.error,
    )


def _summary(backtest: BacktestResult) -> BacktestSummary:
    tearsheet = backtest.tearsheet or {}
    return BacktestSummary(
        backtest_id=backtest.id,
        strategy_name=backtest.strategy_name,
        status=backtest.status,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        rebalance_frequency=backtest.rebalance_frequency,
        created_at=backtest.created_at.isoformat(),
        cagr=tearsheet.get("cagr"),
        sharpe=tearsheet.get("sharpe"),
        sortino=tearsheet.get("sortino"),
        calmar=tearsheet.get("calmar"),
        max_drawdown=tearsheet.get("max_drawdown"),
        benchmark_cagr=tearsheet.get("benchmark_cagr"),
        error=backtest.error,
    )


@router.post("/{portfolio_id}/backtests", response_model=BacktestSubmitResponse, status_code=202)
async def submit_backtest(
    portfolio_id: uuid.UUID,
    payload: BacktestRequest,
    current_user: CurrentUser,
    db: _DBDep,
    market_service: _MarketDep,
) -> BacktestSubmitResponse:
    """Create a pending backtest for a saved portfolio and dispatch Celery."""
    portfolio = await portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if not portfolio.holdings:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Portfolio has no holdings.")

    try:
        portfolio_service._validate_weights(portfolio.holdings)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    tickers, weights = portfolio_service.portfolio_to_weights(portfolio.holdings)
    benchmark_ticker = portfolio.benchmark_ticker.upper()
    # In eager mode the task runs synchronously in this request — skip the preflight
    # (which also calls Tiingo) to avoid double-fetching and an extra failure point.
    if not celery_app.conf.task_always_eager:
        await _preflight_market_data(market_service, tickers, benchmark_ticker, payload)

    strategy_name = (
        payload.strategy_name
        or f"{payload.rebalance_frequency.value} {payload.start_date}-{payload.end_date}"
    )
    # Pre-generate task_id so it can be committed in the same transaction as the
    # BacktestResult row, eliminating the two-commit race where a failed second
    # commit would orphan a dispatched task with task_id=NULL.
    task_id = str(uuid.uuid4())
    backtest = BacktestResult(
        user_id=current_user.id,
        portfolio_id=portfolio.id,
        strategy_name=strategy_name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        rebalance_frequency=payload.rebalance_frequency,
        status=BacktestStatus.PENDING,
        initial_investment=payload.initial_investment,
        tickers=tickers,
        weights=[float(weight) for weight in weights],
        task_id=task_id,
    )
    db.add(backtest)
    await db.commit()

    params = {
        "tickers": tickers,
        "weights": [float(weight) for weight in weights],
        "benchmark_ticker": benchmark_ticker,
        "start_date": payload.start_date.isoformat(),
        "end_date": payload.end_date.isoformat(),
        "rebalance_frequency": payload.rebalance_frequency.value,
        "initial_investment": float(payload.initial_investment),
    }
    try:
        if celery_app.conf.task_always_eager:
            # apply() skips the Kombu producer pool (no broker connection needed)
            task = run_backtest.apply(args=[str(backtest.id), params], task_id=task_id)
        else:
            task = run_backtest.apply_async(args=[str(backtest.id), params], task_id=task_id)
    except Exception as exc:
        _logger.exception("failed to dispatch backtest task backtest_id=%s", backtest.id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dispatch backtest task.",
        ) from exc

    # In eager mode (USE_CELERY=false) the task runs synchronously and returns a
    # result dict — write the outcome here since the task can't do async DB writes.
    if isinstance(task, EagerResult) and isinstance(task.result, dict):
        resp = task.result
        if resp.get("ok"):
            backtest.status = BacktestStatus.SUCCESS
            result_data = resp["result"]
            backtest.tearsheet = result_data["tearsheet"]
            backtest.daily_returns = result_data["daily_returns"]
            backtest.equity_curve = result_data["equity_curve"]
        else:
            backtest.status = BacktestStatus.FAILURE
            backtest.error = str(resp.get("error", "Task failed"))[:2000]
        await db.commit()

    return BacktestSubmitResponse(
        backtest_id=backtest.id,
        task_id=task_id,
        status=backtest.status,
    )


@router.get("/{portfolio_id}/backtests/{backtest_id}", response_model=BacktestStatusResponse)
async def get_backtest(
    portfolio_id: uuid.UUID,
    backtest_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
) -> BacktestStatusResponse:
    result = await db.execute(
        select(BacktestResult).where(
            BacktestResult.id == backtest_id,
            BacktestResult.portfolio_id == portfolio_id,
            BacktestResult.user_id == current_user.id,
        )
    )
    backtest = result.scalar_one_or_none()
    if backtest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return _status_response(backtest)


@router.get("/{portfolio_id}/backtests", response_model=list[BacktestSummary])
async def list_backtests(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
) -> list[BacktestSummary]:
    result = await db.execute(
        select(BacktestResult)
        .where(
            BacktestResult.portfolio_id == portfolio_id,
            BacktestResult.user_id == current_user.id,
        )
        .order_by(BacktestResult.created_at.desc())
    )
    return [_summary(backtest) for backtest in result.scalars().all()]
