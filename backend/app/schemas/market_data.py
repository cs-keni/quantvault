from pydantic import BaseModel, Field


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
    tickers: list[str] = Field(min_length=1, max_length=50)


class ValidateTickersResponse(BaseModel):
    valid: list[str]
    invalid: list[str]
