from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.market_data import (
    HistoricalDataResponse,
    TickerInfoResponse,
    TickerSearchResponse,
    TickerSearchResult,
    ValidateTickersRequest,
    ValidateTickersResponse,
)
from app.services.market_data_service import MarketDataService, get_market_data_service

router = APIRouter()

_MarketDataDep = Annotated[MarketDataService, Depends(get_market_data_service)]

_VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}


@router.get("/search", response_model=TickerSearchResponse)
async def search_tickers(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    service: _MarketDataDep,
) -> TickerSearchResponse:
    """Search for tickers by name or symbol."""
    results_raw = await service.search_tickers(q)
    return TickerSearchResponse(
        query=q,
        results=[TickerSearchResult(**r) for r in results_raw],
    )


@router.get("/{ticker}/history", response_model=HistoricalDataResponse)
async def get_ticker_history(
    ticker: str,
    service: _MarketDataDep,
    period: Annotated[str, Query()] = "1y",
) -> HistoricalDataResponse:
    """Return daily percentage returns for a single ticker over the requested period."""
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{period}'. Valid values: {sorted(_VALID_PERIODS)}",
        )

    upper = ticker.upper()
    try:
        df, dropped = await service.get_historical_returns([upper], period)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if df.empty or upper not in df.columns:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No usable historical data for '{ticker}'",
        )

    col = df[upper]
    dates = [str(idx.date()) for idx in col.index]
    return HistoricalDataResponse(
        ticker=upper,
        period=period,
        dates=dates,
        returns=col.tolist(),
    )


@router.get("/{ticker}/info", response_model=TickerInfoResponse)
async def get_ticker_info(
    ticker: str,
    service: _MarketDataDep,
) -> TickerInfoResponse:
    """Return company metadata for a ticker (name, sector, industry, market cap, etc.)."""
    try:
        info = await service.get_ticker_info(ticker.upper())
        return TickerInfoResponse(**info)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch info for '{ticker}': {exc}",
        ) from exc


@router.post("/validate-tickers", response_model=ValidateTickersResponse)
async def validate_tickers(
    payload: ValidateTickersRequest,
    service: _MarketDataDep,
) -> ValidateTickersResponse:
    """Batch-validate ticker symbols against Yahoo Finance."""
    valid, invalid = await service.validate_tickers(payload.tickers)
    return ValidateTickersResponse(valid=valid, invalid=invalid)
