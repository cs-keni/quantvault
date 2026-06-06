from typing import Annotated

from pydantic import BaseModel, Field

# Per-item ticker validation: prevents comma/colon injection into Redis cache keys.
# Allows standard symbols (AAPL, BRK.B, ^TNX, BRK-B) and rejects any character
# that would corrupt qv:mds: cache key structure.
_TickerStr = Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")]


class HistoricalDataResponse(BaseModel):
    ticker: str
    period: str
    dates: list[str]
    returns: list[float]


class TickerInfoResponse(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None
    currency: str | None = None
    exchange: str | None = None


class QuoteResponse(BaseModel):
    ticker: str
    price: float
    change: float | None = None
    change_pct: float | None = None


class TickerSearchResult(BaseModel):
    ticker: str
    name: str | None = None
    exchange: str | None = None
    asset_type: str | None = None


class TickerSearchResponse(BaseModel):
    query: str
    results: list[TickerSearchResult]


class ValidateTickersRequest(BaseModel):
    tickers: list[_TickerStr] = Field(
        min_length=1,
        max_length=50,
        description="List of 1-50 ticker symbols to validate against Yahoo Finance.",
    )


class ValidateTickersResponse(BaseModel):
    valid: list[str]
    invalid: list[str]
