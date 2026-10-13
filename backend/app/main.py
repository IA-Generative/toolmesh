from fastapi import FastAPI

from app.routers.health import router as health_router
from app.version import get_version

app = FastAPI(title="toolmesh backend", version=get_version())

app.include_router(health_router)
