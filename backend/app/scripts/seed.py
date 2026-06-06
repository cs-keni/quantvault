"""Seed the dev database with a demo user and a starter portfolio.

Run via `make seed` (wraps `python -m app.scripts.seed`). Idempotent — looks
the demo user up by email and exits early if it already exists, so re-running
after a fresh `make migrate` never raises a duplicate-key error.
"""

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.holding import AssetClass, Holding
from app.models.portfolio import Portfolio
from app.models.user import User

DEMO_EMAIL = "demo@quantvault.dev"
DEMO_PASSWORD = "quantvault-demo"
DEMO_FULL_NAME = "Demo User"

# A classic three-fund portfolio: US total market, US bonds, international —
# weights sum to 1.0 exactly, satisfying the invariant `portfolio_to_weights`
# callers rely on (see `portfolio_service.py`).
DEMO_HOLDINGS = [
    {
        "ticker": "VTI",
        "asset_name": "Vanguard Total Stock Market ETF",
        "asset_class": AssetClass.EQUITY,
        "target_weight": Decimal("0.60"),
    },
    {
        "ticker": "BND",
        "asset_name": "Vanguard Total Bond Market ETF",
        "asset_class": AssetClass.FIXED_INCOME,
        "target_weight": Decimal("0.30"),
    },
    {
        "ticker": "VXUS",
        "asset_name": "Vanguard Total International Stock ETF",
        "asset_class": AssetClass.EQUITY,
        "target_weight": Decimal("0.10"),
    },
]


async def _seed() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            print(f"Demo user already exists ({DEMO_EMAIL}) — nothing to do.")
            return

        user = User(
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=DEMO_FULL_NAME,
        )
        session.add(user)
        await session.flush()  # assigns user.id for the portfolio FK below

        portfolio = Portfolio(
            user_id=user.id,
            name="Demo Portfolio",
            description="A starter three-fund portfolio: US stocks, US bonds, and international stocks.",
            benchmark_ticker="SPY",
        )
        session.add(portfolio)
        await session.flush()  # assigns portfolio.id for the holdings' FK below

        for spec in DEMO_HOLDINGS:
            session.add(Holding(portfolio_id=portfolio.id, **spec))

        user.default_portfolio_id = portfolio.id

        await session.commit()
        print(
            f"Seeded demo user '{DEMO_EMAIL}' (password: '{DEMO_PASSWORD}') "
            f"with portfolio '{portfolio.name}' ({len(DEMO_HOLDINGS)} holdings, "
            f"set as default)."
        )


async def main() -> None:
    try:
        await _seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
