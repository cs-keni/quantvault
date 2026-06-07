import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.backtest_result import BacktestResult
    from app.models.portfolio import Portfolio
    from app.models.simulation_result import SimulationResult


class User(Base):
    """A registered account. Owns portfolios and authenticates via email + bcrypt password."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Points at one of this user's own portfolios. Nullable + use_alter because
    # `portfolios.id` doesn't exist yet when `users` is created — Alembic emits
    # this FK as a separate ALTER TABLE once both tables exist (locked decision:
    # User.default_portfolio_id FK, not Portfolio.is_default, to avoid a
    # multi-row "only one default per user" constraint).
    default_portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "portfolios.id",
            use_alter=True,
            name="fk_users_default_portfolio_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    portfolios: Mapped[list["Portfolio"]] = relationship(
        "Portfolio",
        back_populates="user",
        foreign_keys="[Portfolio.user_id]",
        cascade="all, delete-orphan",
    )
    simulation_results: Mapped[list["SimulationResult"]] = relationship(
        "SimulationResult", back_populates="user", cascade="all, delete-orphan"
    )
    backtest_results: Mapped[list["BacktestResult"]] = relationship(
        "BacktestResult", back_populates="user", cascade="all, delete-orphan"
    )
    # post_update=True: breaks the User <-> Portfolio insert cycle by issuing a
    # second UPDATE after both rows exist, instead of failing on either insert.
    default_portfolio: Mapped["Portfolio | None"] = relationship(
        "Portfolio",
        foreign_keys=[default_portfolio_id],
        post_update=True,
    )
