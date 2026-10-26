import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    visible = await visible_tools(db, user)
    query = q.strip()
    index = get_index(settings) if query else None
    if index is not None:
        try:
            names = await index.search(query, user.roles, Filters(type, tuple(tag), source, version), limit)
        except Exception:
            logger.exception("Search index unavailable, falling back to the registry")
        else:
            by_name = {t.name: t for t in visible}  # the registry decides what the caller may see
            return SearchOut(
                tools=[by_name[n] for n in names if n in by_name], mode="hybrid" if index.dense else "keyword"
            )
    tools = filter_tools(visible, query, type, tuple(tag), source, version)[:limit]
    return SearchOut(tools=tools, mode="basic" if query else "filter")


@router.get("/me/tools/{name}")
async def get_my_tool(name: str, user: CurrentUser, db: DB) -> ToolOut:
    for tool in await visible_tools(db, user):
        if tool.name == name:
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


@router.post("/me/tools/{name}/call")
async def call_my_tool(
    name: str, payload: CallIn, user: CurrentUser, db: DB, settings: Annotated[Settings, Depends(get_settings)]
) -> CallOut:
    """Run a tool with the given arguments, as the caller (token exchange when its source asks for it)."""
    row = (await db.execute(select(Tool, Source).join(Source).where(Tool.name == name, Tool.enabled))).first()
    if row is None or not is_visible(row.Source, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool not found")
    try:
        return CallOut(**await execute(row.Source, row.Tool, payload.arguments, user.token, settings))
    except ExecutionError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
