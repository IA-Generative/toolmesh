from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.config import Settings, get_settings
from app.db.models import Source
from app.db.session import get_db
from app.discovery import DiscoveryError, discover
from app.registry import build_source, is_visible, name_conflicts, sync_tools
from app.schemas import SourceIn, SourceOut, ToolIn
from app.toolsearch import forget_source, sync_source_with_feedback

router = APIRouter(prefix="/api/sources", tags=["sources"])

DB = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class DiscoveredTools(BaseModel):
    tools: list[ToolIn]
    version: str | None = None


async def _discover(payload: SourceIn, user: CurrentUser, settings: Settings) -> tuple[list[ToolIn], str | None]:
    try:
        return await discover(payload, user.token, settings)
    except DiscoveryError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


async def _get_visible(db: AsyncSession, source_id: str, user: CurrentUser) -> Source:
    source = await db.get(Source, source_id)
    if source is None or not is_visible(source, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return source


@router.post("/discover")
async def discover_tools(payload: SourceIn, user: CurrentUser, settings: AppSettings) -> DiscoveredTools:
    """Preview the tools of an MCP server or API without registering anything."""
    tools, version = await _discover(payload, user, settings)
    return DiscoveredTools(tools=tools, version=version)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceIn, user: CurrentUser, db: DB, settings: AppSettings) -> SourceOut:
    """Register an MCP server, an API or a skill; without declared tools, those of a server or API are discovered."""
    if taken := await name_conflicts(db, payload):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already exists: {', '.join(taken)}")
    if payload.type != "skill" and not payload.tools:
        tools, version = await _discover(payload, user, settings)
        payload = payload.model_copy(update={"tools": tools, "version": payload.version or version})
    source = build_source(payload, created_by=user.sub)
    db.add(source)
    try:
        await db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent creation
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Name already taken") from exc
    await sync_source_with_feedback(settings, db, source)
    return SourceOut.model_validate(source)


@router.get("")
async def list_sources(user: CurrentUser, db: DB) -> list[SourceOut]:
    sources = (await db.scalars(select(Source).order_by(Source.name))).all()
    return [SourceOut.model_validate(s) for s in sources if is_visible(s, user)]


@router.get("/{source_id}")
async def get_source(source_id: str, user: CurrentUser, db: DB) -> SourceOut:
    return SourceOut.model_validate(await _get_visible(db, source_id, user))


@router.post("/{source_id}/refresh")
async def refresh_source(source_id: str, user: CurrentUser, db: DB, settings: AppSettings) -> SourceOut:
    """Discover the tools again: new ones are added, vanished ones removed, the others updated."""
    source = await _get_visible(db, source_id, user)
    if source.created_by != user.sub and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an admin can refresh a source")
    if source.type == "skill":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A skill has nothing to discover")
    stored = SourceIn.model_validate(SourceOut.model_validate(source).model_dump(exclude={"tools"}))
    tools, version = await _discover(stored, user, settings)
    sync_tools(source, tools)
    source.version = version or source.version
    await db.commit()
    await sync_source_with_feedback(settings, db, source)
    return SourceOut.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: str, user: CurrentUser, db: DB, settings: AppSettings) -> Response:
    """Delete a source and its tools; reserved to its creator and to admins."""
    source = await _get_visible(db, source_id, user)
    if source.created_by != user.sub and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an admin can delete a source")
    await db.delete(source)
    await db.commit()
    await forget_source(settings, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
