from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.config import Settings, get_settings
from app.db.models import Source
from app.db.session import get_db
from app.searchlog import learned_aliases
from app.toolsearch import get_index
from app.toolsearch.embeddings import EmbeddingError

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ReindexOut(BaseModel):
    sources: int
    tools: int


@router.post("/reindex", dependencies=[require_role("admin")])
async def reindex(
    db: Annotated[AsyncSession, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]
) -> ReindexOut:
    """Rebuild the search index from the registry (after a change of embedding model, or to repair it)."""
    index = get_index(settings)
    if index is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No search index is configured (TOOLMESH_QDRANT_URL)")
    sources = list((await db.scalars(select(Source))).all())
    try:
        tools = await index.reindex(sources, await learned_aliases(db))
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return ReindexOut(sources=len(sources), tools=tools)
