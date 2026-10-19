from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.downstream import router as downstream_router
from app.routers.health import router as health_router
from app.routers.mcp_datetime import router as mcp_datetime_router
from app.routers.tools import router as tools_router
from app.version import get_version

app = FastAPI(title="toolmesh backend", version=get_version())

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
app.include_router(downstream_router)
app.include_router(mcp_datetime_router)
