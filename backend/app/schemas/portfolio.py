import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.holding import AssetClass

_TickerStr = Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")]
_AnalysisPeriod = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]

# ────────────────────────────────────────────────────────────────
# Portfolio CRUD schemas
# ────────────────────────────────────────────────────────────────


class PortfolioCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    benchmark_ticker: Annotated[str, Field(min_length=1, max_length=16)] = "SPY"


class PortfolioUpdate(BaseModel):
    name: Annotated[str | None, Field(min_length=1, max_length=255)] = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    benchmark_ticker: Annotated[str | None, Field(min_length=1, max_length=16)] = None


class HoldingOut(BaseModel):
    id: uuid.UUID
    ticker: str
    asset_name: str
    asset_class: AssetClass
    target_weight: Decimal
    current_shares: Decimal | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class PortfolioOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    benchmark_ticker: str
    holdings: list[HoldingOut] = []

    model_config = {"from_attributes": True}


class PortfolioListItem(BaseModel):
    id: uuid.UUID
    name: str
    benchmark_ticker: str
    holding_count: int = 0

    model_config = {"from_attributes": True}


# ────────────────────────────────────────────────────────────────
# Holding management schemas
# ────────────────────────────────────────────────────────────────


class HoldingCreate(BaseModel):
    ticker: Annotated[str, Field(min_length=1, max_length=16)]
    asset_name: Annotated[str, Field(min_length=1, max_length=255)]
    asset_class: AssetClass
    target_weight: Annotated[Decimal, Field(gt=0, le=1)]
    current_shares: Annotated[Decimal | None, Field(gt=0)] = None
    notes: Annotated[str | None, Field(max_length=2000)] = None


class HoldingUpdate(BaseModel):
    asset_name: Annotated[str | None, Field(min_length=1, max_length=255)] = None
    asset_class: AssetClass | None = None
    target_weight: Annotated[Decimal | None, Field(gt=0, le=1)] = None
    current_shares: Annotated[Decimal | None, Field(gt=0)] = None
    notes: Annotated[str | None, Field(max_length=2000)] = None


# ────────────────────────────────────────────────────────────────
# Analysis / metrics schemas
# ────────────────────────────────────────────────────────────────


class AdHocHolding(BaseModel):
    """A single holding for ad-hoc metrics without a saved portfolio."""

    ticker: Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")]
    weight: Annotated[float, Field(gt=0, le=1)]


class MetricsRequest(BaseModel):
    """Input for POST /api/v1/analysis/metrics (ad-hoc portfolio, no DB save)."""

    holdings: Annotated[list[AdHocHolding], Field(min_length=1, max_length=50)]
    period: str = "1y"
    confidence: Annotated[float, Field(gt=0, lt=1)] = 0.95
    benchmark_ticker: Annotated[
        str,
        Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.^=\-]{1,20}$"),
    ] = "SPY"

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "MetricsRequest":
        total = sum(h.weight for h in self.holdings)
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Holdings weights must sum to 1.0 (got {total:.6f}). "
                "Adjust weights before submitting."
            )
        return self


class CorrelationMatrix(BaseModel):
    tickers: list[str]
    matrix: list[list[float]]


class PortfolioMetricsResponse(BaseModel):
    # Basic return / risk
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    # VaR / CVaR (signed fractions; negative = loss)
    var: float
    cvar: float
    confidence: float
    # Drawdown
    max_drawdown: float
    peak_date: str | int
    trough_date: str | int
    # Sortino
    sortino_ratio: float
    # Beta
    beta: float | None = None
    beta_benchmark: str | None = None
    # Diversification
    correlation: CorrelationMatrix
    # Metadata
    risk_free_rate: float
    period: str
    n_trading_days: int
    dropped_tickers: list[str]


# ────────────────────────────────────────────────────────────────
# Efficient frontier schemas
# ────────────────────────────────────────────────────────────────


class FrontierRequest(BaseModel):
    """Input for POST /api/v1/analysis/frontier."""

    tickers: Annotated[list[_TickerStr], Field(min_length=2, max_length=30)]
    period: _AnalysisPeriod = "1y"

    @field_validator("tickers", mode="after")
    @classmethod
    def normalize_and_dedup_tickers(cls, tickers: list[str]) -> list[str]:
        normalized = [ticker.upper() for ticker in tickers]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate tickers are not allowed.")
        return normalized


class FrontierPoint(BaseModel):
    annual_return: Annotated[
        float,
        Field(description="Geometrically compounded annual return: (1 + mean_daily)^252 - 1"),
    ]
    annual_volatility: float
    sharpe_ratio: Annotated[
        float,
        Field(
            description=(
                "Sharpe ratio using arithmetic annual return in the numerator "
                "(252 * mean_daily - rfr) / sigma. Slightly differs from computing "
                "(annual_return - rfr) / annual_volatility using the geometric annual_return field."
            )
        ),
    ]
    weights: dict[str, float]


class FrontierResult(BaseModel):
    tickers: list[str]
    period: str
    risk_free_rate: float
    frontier: list[FrontierPoint]
    min_variance: FrontierPoint
    max_sharpe: FrontierPoint
    dropped_tickers: list[str] = []
    n_trading_days: int


class FrontierTaskStatus(BaseModel):
    task_id: str
    status: str
    result: FrontierResult | None = None
    error: str | None = None


class FrontierSubmitResponse(BaseModel):
    task_id: str | None = None
    status: str
    result: FrontierResult | None = None
    error: str | None = None
