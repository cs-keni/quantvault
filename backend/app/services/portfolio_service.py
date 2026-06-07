"""Portfolio-level business logic: weight extraction, CRUD, and orchestration.

Pure financial math (VaR, Sharpe, etc.) lives in risk_service.py.
This module owns:
  - portfolio_to_weights()  — the single Decimal→float64 conversion point (decision #8)
  - Portfolio / Holding CRUD (DB operations)
  - calculate_beta_from_ticker() — orchestrates market_data + risk_service
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.holding import AssetClass, Holding
from app.models.portfolio import Portfolio
from app.services.risk_service import calculate_beta_from_returns

if TYPE_CHECKING:
    from app.services.market_data_service import MarketDataService

_logger = logging.getLogger(__name__)


def portfolio_to_weights(holdings: list[Holding]) -> tuple[list[str], npt.NDArray[np.float64]]:
    """Convert a portfolio's holdings into parallel ticker/weight arrays for numpy/scipy math.

    `Holding.target_weight` is stored as `Decimal` — exact and DB-safe — but
    every downstream calculation (`calculate_portfolio_metrics`, the efficient
    frontier solver, Monte Carlo, VaR/CVaR, ...) operates on `float64`
    `np.ndarray` weights via numpy/pandas/scipy. This is the single place that
    `Decimal` -> `float` conversion happens (locked architecture decision #8),
    so rounding behavior can't drift independently across call sites.

    Returns `(tickers, weights)` as index-aligned sequences: `weights[i]` is
    the target weight for `tickers[i]`. Callers that need the weights to sum to
    1.0 should validate at the point holdings are written (`add`/`update`
    endpoints), not here — re-checking on every read would mask the same bug
    that already passed validation, while flagging legitimately transient states.
    """
    tickers = [holding.ticker for holding in holdings]
    weights = np.array([float(holding.target_weight) for holding in holdings], dtype=np.float64)
    return tickers, weights


# ────────────────────────────────────────────────────────────────
# Portfolio CRUD
# ────────────────────────────────────────────────────────────────


async def create_portfolio(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    description: str | None,
    benchmark_ticker: str,
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        description=description,
        benchmark_ticker=benchmark_ticker.upper(),
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def list_portfolios(db: AsyncSession, user_id: uuid.UUID) -> list[Portfolio]:
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user_id)
        .options(selectinload(Portfolio.holdings))
        .order_by(Portfolio.created_at.desc())
    )
    return list(result.scalars().all())


async def get_portfolio(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Portfolio | None:
    result = await db.execute(
        select(Portfolio)
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        .options(selectinload(Portfolio.holdings))
    )
    return result.scalar_one_or_none()


async def update_portfolio(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
    benchmark_ticker: str | None = None,
) -> Portfolio | None:
    portfolio = await get_portfolio(db, portfolio_id, user_id)
    if portfolio is None:
        return None
    if name is not None:
        portfolio.name = name
    if description is not None:
        portfolio.description = description
    if benchmark_ticker is not None:
        portfolio.benchmark_ticker = benchmark_ticker.upper()
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def delete_portfolio(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    portfolio = await get_portfolio(db, portfolio_id, user_id)
    if portfolio is None:
        return False
    await db.delete(portfolio)
    await db.flush()
    return True


# ────────────────────────────────────────────────────────────────
# Holding management
# ────────────────────────────────────────────────────────────────


def _validate_weights(holdings: list[Holding]) -> None:
    """Raise ValueError if holdings weights don't sum to 1.0 ± 0.001."""
    if not holdings:
        return
    total = sum(float(h.target_weight) for h in holdings)
    if abs(total - 1.0) > 0.001:
        raise ValueError(
            f"Holdings weights sum to {total:.5f}, must be 1.000 ± 0.001. "
            "Adjust target weights before requesting metrics."
        )


async def add_holding(
    db: AsyncSession,
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
    ticker: str,
    asset_name: str,
    asset_class: AssetClass,
    target_weight: Decimal,
    current_shares: Decimal | None = None,
    notes: str | None = None,
) -> Holding:
    """Add a holding to a portfolio.  Weight sum is NOT enforced on add — the
    Portfolio Builder adds holdings one at a time and reaches 1.0 when done.
    Weight validation happens at metrics-computation time.
    """
    portfolio = await get_portfolio(db, portfolio_id, user_id)
    if portfolio is None:
        raise ValueError(f"Portfolio {portfolio_id} not found")

    holding = Holding(
        portfolio_id=portfolio_id,
        ticker=ticker.upper(),
        asset_name=asset_name,
        asset_class=asset_class,
        target_weight=target_weight,
        current_shares=current_shares,
        notes=notes,
    )
    db.add(holding)
    await db.flush()
    await db.refresh(holding)
    return holding


async def update_holding(
    db: AsyncSession,
    holding_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
    asset_name: str | None = None,
    asset_class: AssetClass | None = None,
    target_weight: Decimal | None = None,
    current_shares: Decimal | None = None,
    notes: str | None = None,
) -> Holding | None:
    result = await db.execute(
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .where(
            Holding.id == holding_id,
            Holding.portfolio_id == portfolio_id,
            Portfolio.user_id == user_id,
        )
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        return None

    if asset_name is not None:
        holding.asset_name = asset_name
    if asset_class is not None:
        holding.asset_class = asset_class
    if target_weight is not None:
        holding.target_weight = target_weight
    if current_shares is not None:
        holding.current_shares = current_shares
    if notes is not None:
        holding.notes = notes

    await db.flush()
    await db.refresh(holding)
    return holding


async def delete_holding(
    db: AsyncSession,
    holding_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .where(
            Holding.id == holding_id,
            Holding.portfolio_id == portfolio_id,
            Portfolio.user_id == user_id,
        )
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        return False
    await db.delete(holding)
    await db.flush()
    return True


# ────────────────────────────────────────────────────────────────
# Beta orchestration (fetches benchmark then delegates to risk_service)
# ────────────────────────────────────────────────────────────────


async def calculate_beta_from_ticker(
    portfolio_returns: pd.Series,
    benchmark_ticker: str,
    period: str,
    market_service: MarketDataService,
) -> float:
    """Fetch benchmark returns via MarketDataService and compute portfolio beta.

    Delegates the actual beta calculation to risk_service._compute_beta() via
    calculate_beta_from_returns() (which handles date-index alignment).
    """
    bench_df, dropped = await market_service.get_historical_returns(
        [benchmark_ticker.upper()], period
    )
    if bench_df.empty or benchmark_ticker.upper() in dropped:
        raise ValueError(f"No usable benchmark data for {benchmark_ticker}")
    bench_returns = bench_df[benchmark_ticker.upper()]
    return calculate_beta_from_returns(portfolio_returns, bench_returns)
