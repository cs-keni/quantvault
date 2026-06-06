from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    # Routers are registered here as each api/v1/* module lands (Phase 1+):
    # from app.api.v1 import auth, portfolios, analysis, simulation, backtest, market_data
    # app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])

    return app


app = create_app()
