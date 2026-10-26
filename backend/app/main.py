import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.db.migrate import run_migrations
from app.db.models import Source
from app.db.session import get_sessionmaker
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.sources import router as sources_router
from app.routers.tools import router as tools_router
from app.toolsearch import get_index
from app.version import get_version

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.auto_migrate:
        await run_migrations(settings.database_url)
    if (index := get_index(settings)) is not None:
        try:
            if await index.ensure_collection():  # a new collection starts empty: fill it from the registry
                async with get_sessionmaker()() as db:
                    await index.reindex(list((await db.scalars(select(Source))).all()))
        except Exception:
            logger.exception("The search index is not ready; POST /api/admin/reindex retries")
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
app.include_router(admin_router)
app.include_router(tools_router)
app.include_router(sources_router)
