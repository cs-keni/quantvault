import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.portfolio import Portfolio


class AssetClass(enum.StrEnum):
    """Broad category used to group holdings for diversification / allocation reporting."""

    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    REAL_ESTATE = "REAL_ESTATE"
    COMMODITY = "COMMODITY"
    CASH = "CASH"


class Holding(Base):
    """One position in a portfolio: a ticker plus its target allocation weight.

    `target_weight` is a fraction of 1.0 (0.6 == 60%); the service layer enforces
    that weights across a portfolio sum to 1.0 within a ±0.001 tolerance — that
    invariant spans multiple rows, so it can't be a single-column DB constraint.
    """

    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_class: Mapped[AssetClass] = mapped_column(
        SQLEnum(AssetClass, name="asset_class", native_enum=True), nullable=False
    )
    target_weight: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    current_shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")
