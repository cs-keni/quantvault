"""Monte Carlo simulation endpoints."""

import logging
import uuid
from decimal import Decimal
from typing import Annotated

from celery.result import EagerResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import CurrentUser
from app.models.simulation_result import SimulationResult, SimulationStatus
from app.schemas.simulation import (
    SimulationRequest,
    SimulationResponse,
    SimulationStatusResponse,
    SimulationSubmitResponse,
)
from app.services import portfolio_service
from app.services.simulation_service import run_simulation

router = APIRouter()
_logger = logging.getLogger(__name__)

_DBDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/monte-carlo", response_model=SimulationSubmitResponse)
async def submit_monte_carlo_simulation(
    payload: SimulationRequest,
    current_user: CurrentUser,
    db: _DBDep,
) -> SimulationSubmitResponse:
    """Create a pending Monte Carlo simulation and dispatch the worker task."""
    if payload.portfolio_id is not None:
        portfolio = await portfolio_service.get_portfolio(
            db, payload.portfolio_id, current_user.id
        )
        if portfolio is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    simulation = SimulationResult(
        user_id=current_user.id,
        portfolio_id=payload.portfolio_id,
        status=SimulationStatus.PENDING,
        tickers=payload.tickers,
        weights=payload.weights,
        period=payload.period,
        initial_investment=Decimal(str(payload.initial_investment)),
        years=payload.years,
        n_simulations=payload.n_simulations,
        annual_contribution=Decimal(str(payload.annual_contribution)),
        seed=payload.seed,
    )
    db.add(simulation)
    await db.commit()
    await db.refresh(simulation)

    params = payload.model_dump(mode="json", exclude={"portfolio_id"})
    try:
        task = run_simulation.delay(str(simulation.id), params)
    except Exception as exc:
        _logger.exception("failed to dispatch simulation task simulation_id=%s", simulation.id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dispatch simulation task.",
        ) from exc

    simulation.task_id = task.id

    # In eager mode (USE_CELERY=false) the task runs synchronously and returns a
    # result dict — we write the outcome here since the task can't do async DB
    # writes from inside the event loop.
    if isinstance(task, EagerResult) and isinstance(task.result, dict):
        resp = task.result
        if resp.get("ok"):
            simulation.status = SimulationStatus.SUCCESS
            simulation.results = resp.get("result")
        else:
            simulation.status = SimulationStatus.FAILURE
            simulation.error = str(resp.get("error", "Task failed"))[:2000]

    await db.commit()

    return SimulationSubmitResponse(
        simulation_id=simulation.id,
        task_id=task.id,
        status=simulation.status,
    )


@router.get("/{simulation_id}", response_model=SimulationStatusResponse)
async def get_simulation_status(
    simulation_id: uuid.UUID,
    current_user: CurrentUser,
    db: _DBDep,
) -> SimulationStatusResponse:
    """Get a persisted simulation by id, scoped to the authenticated user."""
    result = await db.execute(
        select(SimulationResult).where(
            SimulationResult.id == simulation_id,
            SimulationResult.user_id == current_user.id,
        )
    )
    simulation = result.scalar_one_or_none()
    if simulation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    response_result = (
        SimulationResponse.model_validate(simulation.results)
        if simulation.results is not None
        else None
    )
    return SimulationStatusResponse(
        simulation_id=simulation.id,
        status=simulation.status,
        result=response_result,
        error=simulation.error,
    )
