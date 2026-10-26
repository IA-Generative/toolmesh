from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models import Source
from app.db.session import get_db
from app.registry import build_source, is_visible, name_conflicts
from app.schemas import SourceIn, SourceOut

router = APIRouter(prefix="/api/sources", tags=["sources"])

DB = Annotated[AsyncSession, Depends(get_db)]


async def _get_visible(db: AsyncSession, source_id: str, user: CurrentUser) -> Source:
    source = await db.get(Source, source_id)
    if source is None or not is_visible(source, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return source


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceIn, user: CurrentUser, db: DB) -> SourceOut:
    """Register an MCP server, an API or a skill together with the tools it exposes."""
    if taken := await name_conflicts(db, payload):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already exists: {', '.join(taken)}")
    source = build_source(payload, created_by=user.sub)
    db.add(source)
    try:
        await db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent creation
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Name already taken") from exc
    return SourceOut.model_validate(source)


@router.get("")
async def list_sources(user: CurrentUser, db: DB) -> list[SourceOut]:
    sources = (await db.scalars(select(Source).order_by(Source.name))).all()
    return [SourceOut.model_validate(s) for s in sources if is_visible(s, user)]


@router.get("/{source_id}")
async def get_source(source_id: str, user: CurrentUser, db: DB) -> SourceOut:
    return SourceOut.model_validate(await _get_visible(db, source_id, user))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: str, user: CurrentUser, db: DB) -> Response:
    """Delete a source and its tools; reserved to its creator and to admins."""
    source = await _get_visible(db, source_id, user)
    if source.created_by != user.sub and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an admin can delete a source")
    await db.delete(source)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
