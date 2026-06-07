import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import CurrentUser
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingOut,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioListItem,
    PortfolioOut,
    PortfolioUpdate,
)
from app.services import portfolio_service

router = APIRouter()
_logger = logging.getLogger(__name__)

_DBDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[PortfolioListItem])
async def list_portfolios(current_user: CurrentUser, db: _DBDep) -> list[PortfolioListItem]:
    """List all portfolios owned by the authenticated user."""
    portfolios = await portfolio_service.list_portfolios(db, current_user.id)
    return [
        PortfolioListItem(
            id=p.id,
            name=p.name,
            benchmark_ticker=p.benchmark_ticker,
            holding_count=len(p.holdings),
        )
        for p in portfolios
    ]


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioCreate,
    current_user: CurrentUser,
    db: _DBDep,
) -> PortfolioOut:
    """Create a new portfolio for the authenticated user."""
    portfolio = await portfolio_service.create_portfolio(
        db,
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        benchmark_ticker=payload.benchmark_ticker,
    )
    await db.commit()
    # Reload after commit: commit expires all SQLAlchemy attributes; reload with
    # selectinload so the `holdings` relationship is accessible to Pydantic.
    reloaded = await portfolio_service.get_portfolio(db, portfolio.id, current_user.id)
    assert reloaded is not None
    return PortfolioOut.model_validate(reloaded)


@router.get("/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
) -> PortfolioOut:
    """Get a portfolio (with holdings) by ID."""
    portfolio = await portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return PortfolioOut.model_validate(portfolio)


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
async def update_portfolio(
    portfolio_id: uuid.UUID,
    payload: PortfolioUpdate,
    current_user: CurrentUser,
    db: _DBDep,
) -> PortfolioOut:
    """Update portfolio metadata (name, description, benchmark)."""
    portfolio = await portfolio_service.update_portfolio(
        db,
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        benchmark_ticker=payload.benchmark_ticker,
    )
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    await db.commit()
    portfolio = await portfolio_service.get_portfolio(db, portfolio_id, current_user.id)
    return PortfolioOut.model_validate(portfolio)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
) -> None:
    """Delete a portfolio and all its holdings."""
    deleted = await portfolio_service.delete_portfolio(db, portfolio_id, current_user.id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    await db.commit()


# ────────────────────────────────────────────────────────────────
# Holdings management
# ────────────────────────────────────────────────────────────────


@router.post(
    "/{portfolio_id}/holdings",
    response_model=HoldingOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_holding(
    portfolio_id: uuid.UUID,
    payload: HoldingCreate,
    current_user: CurrentUser,
    db: _DBDep,
) -> HoldingOut:
    """Add a holding to a portfolio.

    Weight sum is NOT enforced on add — the Portfolio Builder adds holdings
    one at a time. Validation happens when computing metrics.
    """
    try:
        holding = await portfolio_service.add_holding(
            db,
            portfolio_id=portfolio_id,
            user_id=current_user.id,
            ticker=payload.ticker,
            asset_name=payload.asset_name,
            asset_class=payload.asset_class,
            target_weight=payload.target_weight,
            current_shares=payload.current_shares,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(holding)
    return HoldingOut.model_validate(holding)


@router.patch("/{portfolio_id}/holdings/{holding_id}", response_model=HoldingOut)
async def update_holding(
    portfolio_id: uuid.UUID,
    holding_id: uuid.UUID,
    payload: HoldingUpdate,
    current_user: CurrentUser,
    db: _DBDep,
) -> HoldingOut:
    """Update a holding's weight, asset class, shares, or notes."""
    holding = await portfolio_service.update_holding(
        db,
        holding_id=holding_id,
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        asset_name=payload.asset_name,
        asset_class=payload.asset_class,
        target_weight=payload.target_weight,
        current_shares=payload.current_shares,
        notes=payload.notes,
    )
    if holding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Holding not found")
    await db.commit()
    await db.refresh(holding)
    return HoldingOut.model_validate(holding)


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    portfolio_id: uuid.UUID,
    holding_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
) -> None:
    """Remove a holding from a portfolio."""
    deleted = await portfolio_service.delete_holding(
        db,
        holding_id=holding_id,
        portfolio_id=portfolio_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Holding not found")
    await db.commit()
