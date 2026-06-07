# Each model module is imported here so it registers on Base.metadata —
# this is what alembic/env.py relies on for autogenerate to see the full schema.
from app.models.backtest_result import BacktestResult, BacktestStatus, RebalanceFrequency
from app.models.holding import AssetClass, Holding
from app.models.portfolio import Portfolio
from app.models.simulation_result import SimulationResult, SimulationStatus
from app.models.user import User

__all__ = [
    "AssetClass",
    "BacktestResult",
    "BacktestStatus",
    "Holding",
    "Portfolio",
    "RebalanceFrequency",
    "SimulationResult",
    "SimulationStatus",
    "User",
]
