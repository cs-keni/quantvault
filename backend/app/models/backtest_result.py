import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.portfolio import Portfolio


class RebalanceFrequency(str, enum.Enum):
    """How often a backtest rebalances holdings back to their target weights."""

    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"
    NEVER = "NEVER"


class BacktestResult(Base):
    """A saved backtest run: its configuration plus the computed tearsheet/series.

    Results are stored as JSONB rather than normalized tables — they're
    write-once analytical blobs the service layer never queries *into* (only
    fetches whole), and their shape evolves with the tearsheet format.
    """

    __tablename__ = "backtest_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    rebalance_frequency: Mapped[RebalanceFrequency] = mapped_column(
        SQLEnum(RebalanceFrequency, name="rebalance_frequency", native_enum=True), nullable=False
    )
    initial_investment: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    tearsheet: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    daily_returns: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    equity_curve: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="backtest_results")
