import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.backtest_result import BacktestResult
    from app.models.holding import Holding
    from app.models.simulation_result import SimulationResult
    from app.models.user import User


class Portfolio(Base):
    """A named collection of holdings owned by a user, analyzed against a benchmark ticker."""

    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    benchmark_ticker: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SPY", server_default="SPY"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="portfolios", foreign_keys=[user_id])
    holdings: Mapped[list["Holding"]] = relationship(
        "Holding", back_populates="portfolio", cascade="all, delete-orphan"
    )
    backtest_results: Mapped[list["BacktestResult"]] = relationship(
        "BacktestResult", back_populates="portfolio", cascade="all, delete-orphan"
    )
    simulation_results: Mapped[list["SimulationResult"]] = relationship(
        "SimulationResult", back_populates="portfolio", cascade="all, delete-orphan"
    )
