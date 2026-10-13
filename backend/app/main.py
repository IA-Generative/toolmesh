from fastapi import FastAPI

from app.routers.downstream import router as downstream_router
from app.routers.health import router as health_router
from app.routers.mcp_datetime import router as mcp_datetime_router
from app.routers.tools import router as tools_router
from app.version import get_version

app = FastAPI(title="toolmesh backend", version=get_version())

app.include_router(health_router)
app.include_router(tools_router)
app.include_router(downstream_router)
app.include_router(mcp_datetime_router)
