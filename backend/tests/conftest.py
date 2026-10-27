from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_jwks_client
from app.config import Settings, get_settings
from app.db.models import Base, Source, Tool
from app.db.session import get_db
from app.main import app
from tests.registry_data import seed_test_registry
from tests.test_tools import _FakeJwks


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """In-memory SQLite registry with the schema created from the models."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _registry_db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    """Every test talks to the in-memory registry, never to a real database."""

    async def _db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    """API client with a valid-token setup and the test registry loaded."""
    async with session_factory() as db:
        await seed_test_registry(db)

    app.dependency_overrides[get_settings] = lambda: Settings(keycloak_url="http://kc.test")
    app.dependency_overrides[get_jwks_client] = lambda: _FakeJwks()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def tool_id(session_factory: async_sessionmaker[AsyncSession]):
    """`await tool_id("web_search")`: the id of a tool, as the API addresses it (`source=` when the name is shared)."""

    async def find(name: str, source: str | None = None) -> str:
        query = select(Tool.id).join(Source).where(Tool.name == name)
        if source:
            query = query.where(Source.name == source)
        async with session_factory() as db:
            return (await db.scalars(query)).one()

    return find
