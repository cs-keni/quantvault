import os
from collections.abc import AsyncGenerator

import pytest
from app.core.database import Base, get_db
from app.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Tests run against a dedicated database so they never touch dev/prod data.
# Override via TEST_DATABASE_URL in CI; defaults to the dev Postgres host with
# a "_test" suffixed database name.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://qv:qv@localhost:5432/quantvault_test",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Pin every async test to the same session-scoped loop as the DB fixtures.

    `engine` builds the schema once per run — its `loop_scope` is "session"
    (via `asyncio_default_fixture_loop_scope` below), and `db_session`/`client`
    reuse its pooled connections. `asyncio_mode = auto` marks test functions
    `loop_scope="function"` by default, which would run them on a *different*
    loop than the one that created those connections' internal locks/futures,
    raising "Future ... attached to a different loop" the moment a test issues
    a real query. Replacing the auto-applied marker with one pinned to
    "session" keeps tests and fixtures on the same loop.
    """
    session_asyncio = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        item.own_markers = [m for m in item.own_markers if m.name != "asyncio"]
        item.add_marker(session_asyncio)


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Session-scoped engine; creates all tables once and drops them on teardown."""
    test_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped session wrapped in a transaction that's rolled back after each test.

    This keeps tests isolated from each other without paying for a schema
    rebuild per test.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app with `get_db` overridden to `db_session`."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
