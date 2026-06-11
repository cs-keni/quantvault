"""Analysis endpoints: ad-hoc and saved-portfolio risk/return metrics."""

import logging
import uuid
from typing import Annotated

import numpy as np
import numpy.typing as npt
import pandas as pd
import redis.asyncio
from celery.result import EagerResult
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.core.database import get_db
from app.core.redis import get_redis
from app.dependencies import CurrentUser
from app.schemas.portfolio import (
    CorrelationMatrix,
    FrontierRequest,
    FrontierResult,
    FrontierSubmitResponse,
    FrontierTaskStatus,
    MetricsRequest,
    PortfolioMetricsResponse,
)
from app.services import portfolio_service, risk_service
from app.services.market_data_service import MarketDataService, get_market_data_service
from app.services.optimization_service import (
    build_frontier_cache_key,
    compute_frontier,
    deserialize_frontier_result,
)

router = APIRouter()
_logger = logging.getLogger(__name__)

_DBDep = Annotated[AsyncSession, Depends(get_db)]
_MarketDep = Annotated[MarketDataService, Depends(get_market_data_service)]
_RedisDep = Annotated[redis.asyncio.Redis, Depends(get_redis)]

_VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}


async def _get_cached_frontier(
    redis_client: redis.asyncio.Redis,
    tickers: list[str],
    period: str,
) -> FrontierResult | None:
    cache_key = build_frontier_cache_key(tickers, period)
    try:
        cached = await redis_client.get(cache_key)
    except redis.RedisError as exc:
        _logger.warning("frontier cache read failed key=%s: %s", cache_key, exc)
        return None

    if cached is None:
        return None
    try:
        return deserialize_frontier_result(cached)
    except ValueError as exc:
        _logger.warning("frontier cache deserialization failed key=%s: %s", cache_key, exc)
        return None


async def _compute_metrics(
    tickers: list[str],
    weights: npt.NDArray[np.float64],
    period: str,
    confidence: float,
    benchmark_ticker: str,
    market_service: MarketDataService,
) -> PortfolioMetricsResponse:
    """Shared computation used by both the ad-hoc and saved-portfolio endpoints."""
    # Fetch returns — yfinance failures raise ValueError; surface as 503 not 500
    try:
        returns_df, dropped = await market_service.get_historical_returns(tickers, period)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data unavailable: {exc}",
        ) from exc
    if returns_df.empty:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No usable historical data for the requested tickers.",
        )

    # Re-align weights to surviving tickers (some may have been dropped)
    surviving = [t for t in tickers if t not in dropped]
    ticker_to_weight = dict(zip(tickers, weights, strict=False))
    surv_weights_raw = np.array([ticker_to_weight[t] for t in surviving], dtype=np.float64)
    # Re-normalize weights to sum to 1.0 after dropping tickers
    weight_sum = surv_weights_raw.sum()
    if weight_sum == 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="All requested tickers were dropped by the data-quality pipeline.",
        )
    surv_weights = surv_weights_raw / weight_sum
    surv_df = returns_df[surviving]

    # Risk-free rate
    rfr = await market_service.get_risk_free_rate()

    # Basic metrics
    basic = risk_service.calculate_portfolio_metrics(surv_df, surv_weights, rfr)
    port_returns: pd.Series = surv_df @ surv_weights

    # VaR / CVaR
    var_result = risk_service.calculate_var_cvar(port_returns, confidence)

    # Max drawdown
    dd_result = risk_service.calculate_max_drawdown(port_returns)

    # Sortino
    sortino = risk_service.calculate_sortino(port_returns, basic["annual_return"], rfr)

    # Beta (best-effort — don't 500 if benchmark fetch fails)
    beta: float | None = None
    try:
        beta = await portfolio_service.calculate_beta_from_ticker(
            port_returns, benchmark_ticker, period, market_service
        )
    except Exception as exc:
        _logger.warning("beta calculation failed for %s: %s", benchmark_ticker, exc)

    # Correlation matrix
    corr_data = risk_service.calculate_correlation_matrix(surv_df)

    return PortfolioMetricsResponse(
        annual_return=basic["annual_return"],
        annual_volatility=basic["annual_volatility"],
        sharpe_ratio=basic["sharpe_ratio"],
        var=var_result["var"],
        cvar=var_result["cvar"],
        confidence=confidence,
        max_drawdown=dd_result["max_drawdown"],
        peak_date=dd_result["peak_date"],
        trough_date=dd_result["trough_date"],
        sortino_ratio=sortino,
        daily_returns=basic["daily_returns"],
        beta=beta,
        beta_benchmark=benchmark_ticker if beta is not None else None,
        correlation=CorrelationMatrix(**corr_data),
        risk_free_rate=rfr,
        period=period,
        n_trading_days=basic["n_trading_days"],
        dropped_tickers=dropped,
    )


@router.post("/metrics", response_model=PortfolioMetricsResponse)
async def compute_metrics_adhoc(
    payload: MetricsRequest,
    current_user: CurrentUser,
    market_service: _MarketDep,
) -> PortfolioMetricsResponse:
    """Compute full risk/return metrics for an ad-hoc portfolio (no DB save required).

    This is the endpoint the Portfolio Builder UI calls for live metric preview
    while the user is still adjusting allocations.
    """
    if payload.period not in _VALID_PERIODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{payload.period}'. Valid: {sorted(_VALID_PERIODS)}",
        )
    tickers = [h.ticker.upper() for h in payload.holdings]
    weights = np.array([h.weight for h in payload.holdings], dtype=np.float64)

    return await _compute_metrics(
        tickers=tickers,
        weights=weights,
        period=payload.period,
        confidence=payload.confidence,
        benchmark_ticker=payload.benchmark_ticker.upper(),
        market_service=market_service,
    )


@router.get("/portfolios/{portfolio_id}/metrics", response_model=PortfolioMetricsResponse)
async def compute_metrics_for_portfolio(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
    market_service: _MarketDep,
    period: str = "1y",
    confidence: Annotated[float, Query(gt=0, lt=1)] = 0.95,
) -> PortfolioMetricsResponse:
    """Compute full risk/return metrics for a saved portfolio."""
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{period}'. Valid: {sorted(_VALID_PERIODS)}",
        )
    portfolio = await portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    if not portfolio.holdings:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Portfolio has no holdings.",
        )

    tickers, weights = portfolio_service.portfolio_to_weights(portfolio.holdings)

    try:
        portfolio_service._validate_weights(portfolio.holdings)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return await _compute_metrics(
        tickers=tickers,
        weights=weights,
        period=period,
        confidence=confidence,
        benchmark_ticker=portfolio.benchmark_ticker,
        market_service=market_service,
    )


@router.post("/frontier", response_model=FrontierSubmitResponse)
async def submit_frontier(
    payload: FrontierRequest,
    current_user: CurrentUser,
    redis_client: _RedisDep,
) -> FrontierSubmitResponse:
    """Submit an efficient-frontier computation or return a cached result."""
    cached = await _get_cached_frontier(redis_client, payload.tickers, payload.period)
    if cached is not None:
        return FrontierSubmitResponse(status="SUCCESS", result=cached)

    task_id = str(uuid.uuid4())
    try:
        if celery_app.conf.task_always_eager:
            # apply() skips Kombu producer acquisition, which would otherwise
            # try to connect to the Redis broker even in eager mode.
            task = compute_frontier.apply(args=[payload.tickers, payload.period], task_id=task_id)
        else:
            task = compute_frontier.apply_async(args=[payload.tickers, payload.period], task_id=task_id)
    except Exception as exc:
        _logger.exception("failed to dispatch frontier task task_id=%s", task_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dispatch frontier task.",
        ) from exc

    if isinstance(task, EagerResult):
        if task.successful():
            return FrontierSubmitResponse(
                status="SUCCESS",
                result=FrontierResult.model_validate(task.result),
            )
        error_detail = str(task.result) if task.result else "Frontier analysis failed."
        _logger.error("eager frontier task failed task_id=%s: %s", task_id, error_detail)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Frontier analysis failed: {error_detail}",
        )

    return FrontierSubmitResponse(task_id=task_id, status="PENDING")


@router.get("/frontier/{task_id}", response_model=FrontierTaskStatus)
async def get_frontier_status(
    task_id: str,
    current_user: CurrentUser,
) -> FrontierTaskStatus:
    """Poll efficient-frontier task state without blocking on task completion."""
    result = celery_app.AsyncResult(task_id)
    state = str(result.state)

    if state == "SUCCESS":
        return FrontierTaskStatus(
            task_id=task_id,
            status=state,
            result=FrontierResult.model_validate(result.info),
        )
    if state == "FAILURE":
        return FrontierTaskStatus(task_id=task_id, status=state, error=str(result.info))

    return FrontierTaskStatus(task_id=task_id, status=state)
