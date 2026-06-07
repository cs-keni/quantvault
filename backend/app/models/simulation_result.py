import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.portfolio import Portfolio
    from app.models.user import User


class SimulationStatus(enum.StrEnum):
    """Lifecycle state for an asynchronous Monte Carlo simulation."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SimulationResult(Base):
    """A persisted Monte Carlo run: inputs, task state, and output blob.

    Inputs are stored alongside the result for auditability and reproduction.
    Results are JSONB because the simulation output is a write-once analytical
    blob consumed whole by the API/UI rather than queried relationally.
    """

    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[SimulationStatus] = mapped_column(
        SQLEnum(SimulationStatus, name="simulation_status", native_enum=True),
        nullable=False,
    )
    tickers: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    weights: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    initial_investment: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    years: Mapped[int] = mapped_column(Integer, nullable=False)
    n_simulations: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_contribution: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="simulation_results")
    portfolio: Mapped["Portfolio | None"] = relationship(
        "Portfolio", back_populates="simulation_results"
    )
