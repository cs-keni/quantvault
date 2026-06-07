from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analysis, auth, market_data, portfolios, simulation
from app.core.config import settings


def create_app() -> FastAPI:
    """Application factory — builds the FastAPI app, middleware, and routers.

    Kept as a factory (rather than a module-level `app`) so tests can build
    isolated instances with overridden dependencies/settings.
    """
    app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_PREFIX}/openapi.json")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
    # Remaining routers register here as each api/v1/* module lands:
    # from app.api.v1 import backtest

    return app


app = create_app()
