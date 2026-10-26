from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.migrate import run_migrations
from app.db.seed import seed_demo_data
from app.db.session import get_sessionmaker
from app.routers.auth import router as auth_router
from app.routers.downstream import router as downstream_router
from app.routers.health import router as health_router
from app.routers.mcp_datetime import router as mcp_datetime_router
from app.routers.sources import router as sources_router
from app.routers.tools import router as tools_router
from app.version import get_version


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.auto_migrate:
        await run_migrations(settings.database_url)
    if settings.seed_demo_data:
        async with get_sessionmaker()() as db:
            await seed_demo_data(db)
    yield


app = FastAPI(title="toolmesh backend", version=get_version(), lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(tools_router)
app.include_router(sources_router)
app.include_router(downstream_router)
app.include_router(mcp_datetime_router)
