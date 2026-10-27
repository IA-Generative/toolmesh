import logging
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import searchlog
from app.auth import CurrentUser
from app.config import Settings, get_settings
from app.db.models import Source, Tool
from app.db.session import get_db
from app.execution import ExecutionError, execute
from app.registry import filter_tools, is_visible, visible_tools
from app.schemas import SourceType, ToolOut
from app.toolsearch import Filters, get_index

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tools"])

DB = Annotated[AsyncSession, Depends(get_db)]


class MyToolsResponse(BaseModel):
    user: str | None
    roles: list[str]
    tools: list[ToolOut]


@router.get("/me/tools")
async def list_my_tools(user: CurrentUser, db: DB) -> MyToolsResponse:
    """Tools visible to the authenticated caller (filtered by realm role)."""
    tools = await visible_tools(db, user)
    return MyToolsResponse(user=user.username or user.sub, roles=user.roles, tools=tools)


class SearchOut(BaseModel):
    tools: list[ToolOut]
    # hybrid: keywords + embeddings; keyword: keywords only (no embeddings API); basic: plain match on the registry
    # (no search index); filter: no query, filters only.
    mode: Literal["hybrid", "keyword", "basic", "filter"]
    # Identifies this search, to say afterwards whether it worked (POST /api/search/{search_id}/feedback); None when
    # there was no query or the log is off.
    search_id: str | None = None


@router.get("/me/tools/search")
async def search_my_tools(
    user: CurrentUser,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
    q: str = "",
    type: SourceType | None = None,
    tag: Annotated[list[str], Query()] = [],  # noqa: B006  (FastAPI reads the default, it is never mutated)
    source: str | None = None,
    version: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchOut:
    """Search the tools visible to the caller (relevance order) and/or filter them by type, tags, source and version."""
    started = time.perf_counter()
    visible = await visible_tools(db, user)
    query = q.strip()
    flt = Filters(type, tuple(tag), source, version)
    result: SearchOut | None = None
    index = get_index(settings) if query else None
    if index is not None:
        try:
            ids = await index.search(query, user.roles, flt, limit)
        except Exception:
            logger.exception("Search index unavailable, falling back to the registry")
        else:
            by_id = {t.id: t for t in visible}  # the registry decides what the caller may see
            result = SearchOut(tools=[by_id[i] for i in ids if i in by_id], mode="hybrid" if index.dense else "keyword")
    if result is None:
        tools = filter_tools(visible, query, type, tuple(tag), source, version)[:limit]
        result = SearchOut(tools=tools, mode="basic" if query else "filter")
    if query and settings.search_log_enabled:
        try:
            result.search_id = await searchlog.record_search(
                db,
                user.sub,
                query,
                {k: v for k, v in {"type": type, "tags": list(tag), "source": source, "version": version}.items() if v},
                result.mode,
                [t.id for t in result.tools],
                round((time.perf_counter() - started) * 1000),
            )
        except Exception:
            logger.exception("Could not log the search")
            await db.rollback()
    return result


@router.get("/me/tools/{tool_id}")
async def get_my_tool(tool_id: str, user: CurrentUser, db: DB) -> ToolOut:
    for tool in await visible_tools(db, user):
        if tool.id == tool_id:
            return tool
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool not found")


class CallIn(BaseModel):
    arguments: dict[str, Any] = {}


class CallOut(BaseModel):
    ok: bool
    # HTTP status of an API call; None for an MCP tool.
    status: int | None
    content_type: str | None
    content: Any
    truncated: bool
    duration_ms: int


@router.post("/me/tools/{tool_id}/call")
async def call_my_tool(
    tool_id: str, payload: CallIn, user: CurrentUser, db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> CallOut:
    """Run a tool with the given arguments, as the caller (token exchange when its source asks for it)."""
    row = (await db.execute(select(Tool, Source).join(Source).where(Tool.id == tool_id, Tool.enabled))).first()
    if row is None or not is_visible(row.Source, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool not found")
    try:
        return CallOut(**await execute(row.Source, row.Tool, payload.arguments, user.token, settings))
    except ExecutionError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
