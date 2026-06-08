from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analysis, auth, backtest, market_data, portfolios, simulation
from app.core.config import settings


def create_app() -> FastAPI:
    """Application factory — builds the FastAPI app, middleware, and routers.

    Kept as a factory (rather than a module-level `app`) so tests can build
    isolated instances with overridden dependencies/settings.
    """
    app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_PREFIX}/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/celery", tags=["health"])
    async def health_celery() -> dict[str, object]:
        """Debug: check eager mode config and test apply() call."""
        from app.celery_app import celery_app as _ca
        from app.services.simulation_service import run_simulation

        eager = _ca.conf.task_always_eager
        propagate = _ca.conf.task_eager_propagates
        result: dict[str, object] = {
            "task_always_eager": eager,
            "task_eager_propagates": propagate,
        }
        try:
            # Minimal smoke test — bad params so task fails fast, but apply() itself must not raise
            task = run_simulation.apply(
                args=["00000000-0000-0000-0000-000000000000",
                      {"tickers": [], "weights": [], "period": "1y",
                       "initial_investment": 10000, "years": 1,
                       "n_simulations": 10, "annual_contribution": 0}]
            )
            result["apply_ok"] = True
            result["task_result_type"] = type(task).__name__
            if hasattr(task, "result"):
                r = task.result
                result["task_result"] = str(r)[:200] if not isinstance(r, dict) else r
        except Exception as exc:
            import traceback
            result["apply_ok"] = False
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc)[:500]
            result["traceback"] = traceback.format_exc()[-2000:]
        return result

    @app.get("/health/tiingo", tags=["health"])
    async def health_tiingo() -> dict[str, object]:
        """Test Tiingo API connectivity from this server. Returns status code and row count."""
        import asyncio
        from datetime import date, timedelta

        import requests as _req

        from app.core.config import settings as _s

        ticker = "SPY"
        end = date.today()
        start = end - timedelta(days=30)
        url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
        params = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "token": _s.TIINGO_API_KEY,
        }
        try:
            resp = await asyncio.to_thread(
                lambda: _req.get(url, params=params, timeout=15)
            )
            data = resp.json() if resp.ok else resp.text
            return {
                "status_code": resp.status_code,
                "ticker": ticker,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "rows": len(data) if isinstance(data, list) else None,
                "body_preview": str(data)[:300] if not isinstance(data, list) else None,
                "key_configured": bool(_s.TIINGO_API_KEY),
            }
        except Exception as exc:
            return {"error": str(exc), "key_configured": bool(_s.TIINGO_API_KEY)}

    app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
    app.include_router(
        market_data.router,
        prefix=f"{settings.API_V1_PREFIX}/market",
        tags=["market-data"],
    )
    app.include_router(
        portfolios.router,
        prefix=f"{settings.API_V1_PREFIX}/portfolios",
        tags=["portfolios"],
    )
    app.include_router(
        analysis.router,
        prefix=f"{settings.API_V1_PREFIX}/analysis",
        tags=["analysis"],
    )
    app.include_router(
        simulation.router,
        prefix=f"{settings.API_V1_PREFIX}/simulation",
        tags=["simulation"],
    )
    app.include_router(
        backtest.router,
        prefix=f"{settings.API_V1_PREFIX}/portfolios",
        tags=["backtest"],
    )
    # Remaining routers register here as each api/v1/* module lands:

    return app


app = create_app()
