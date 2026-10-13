from fastapi import APIRouter
from pydantic import BaseModel

from app.version import get_version

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/api/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=get_version())
