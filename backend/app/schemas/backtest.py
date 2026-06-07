import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.backtest_result import BacktestStatus, RebalanceFrequency


class BacktestRequest(BaseModel):
    start_date: date
    end_date: date
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.QUARTERLY
    initial_investment: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)] = Decimal(
        "10000.00"
    )
    strategy_name: Annotated[str | None, Field(min_length=1, max_length=255)] = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "BacktestRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        if (self.end_date - self.start_date).days < 30:
            raise ValueError("Backtest date range must span at least 30 calendar days.")
        return self


class BacktestTearsheet(BaseModel):
    cagr: float
    sharpe: float
    sortino: float
    calmar: Annotated[
        float | None,
        Field(description="CAGR / abs(max_drawdown), or null when max_drawdown is zero."),
    ]
    beta: float
    alpha: Annotated[
        float,
        Field(
            description=(
                "Jensen's alpha: cagr - (static_rfr + beta * (benchmark_cagr - static_rfr)). "
                "Uses current ^TNX as a static risk-free-rate approximation."
            )
        ),
    ]
    win_rate: Annotated[
        float,
        Field(description="Fraction of trading days where portfolio return is positive."),
    ]
    max_drawdown: float
    rebalance_count: int
    benchmark_cagr: float
    final_value: float
    benchmark_final_value: float
    n_trading_days: int
    risk_free_rate: float


class EquityCurvePoint(BaseModel):
    date: str
    portfolio: float
    benchmark: float


class BacktestSubmitResponse(BaseModel):
    backtest_id: uuid.UUID
    task_id: str
    status: BacktestStatus


class BacktestStatusResponse(BaseModel):
    backtest_id: uuid.UUID
    portfolio_id: uuid.UUID
    strategy_name: str
    status: BacktestStatus
    start_date: date
    end_date: date
    rebalance_frequency: RebalanceFrequency
    initial_investment: Decimal
    tearsheet: BacktestTearsheet | None = None
    daily_returns: list[float] | None = None
    equity_curve: list[EquityCurvePoint] | None = None
    error: str | None = None


class BacktestSummary(BaseModel):
    backtest_id: uuid.UUID
    strategy_name: str
    status: BacktestStatus
    start_date: date
    end_date: date
    rebalance_frequency: RebalanceFrequency
    created_at: str
    cagr: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    max_drawdown: float | None = None
    benchmark_cagr: float | None = None
    error: str | None = None
