import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.simulation_result import SimulationStatus

_TickerStr = Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")]
_AnalysisPeriod = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


class SimulationRequest(BaseModel):
    tickers: Annotated[list[_TickerStr], Field(min_length=1, max_length=50)]
    weights: Annotated[list[float], Field(min_length=1, max_length=50)]
    period: _AnalysisPeriod = "1y"
    initial_investment: Annotated[float, Field(gt=0)] = 10_000.0
    years: Annotated[int, Field(ge=1, le=30)] = 10
    n_simulations: Annotated[int, Field(ge=1, le=1000)] = 500
    annual_contribution: Annotated[float, Field(ge=0)] = 0.0
    seed: int | None = None
    portfolio_id: uuid.UUID | None = None

    @field_validator("tickers", mode="after")
    @classmethod
    def normalize_and_dedup_tickers(cls, tickers: list[str]) -> list[str]:
        normalized = [ticker.upper() for ticker in tickers]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate tickers are not allowed.")
        return normalized

    @model_validator(mode="after")
    def validate_weights(self) -> "SimulationRequest":
        if len(self.weights) != len(self.tickers):
            raise ValueError("weights length must match tickers length.")
        if any(weight < 0 for weight in self.weights):
            raise ValueError("weights must be non-negative.")
        total = sum(self.weights)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"weights must sum to 1.0 +/- 0.001 (got {total:.6f}).")
        return self


class SimulationResponse(BaseModel):
    percentile_outcomes: dict[int, float]
    sample_paths: list[list[float]]
    mean_final_value: float
    probability_of_profit: float
    probability_of_doubling: float
    final_value_distribution: list[float]
    initial_investment: float
    years: int
    n_simulations: int
    annual_contribution: float


class SimulationSubmitResponse(BaseModel):
    simulation_id: uuid.UUID
    task_id: str
    status: SimulationStatus


class SimulationStatusResponse(BaseModel):
    simulation_id: uuid.UUID
    status: SimulationStatus
    result: SimulationResponse | None = None
    error: str | None = None
