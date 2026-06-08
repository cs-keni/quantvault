from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# asyncpg doesn't accept ssl/sslmode as URL query params via SQLAlchemy.
# Pass ssl=True via connect_args in production so the URL stays clean.
_connect_args = {"ssl": True} if settings.ENVIRONMENT == "production" else {}
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base shared by every SQLAlchemy ORM model."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
