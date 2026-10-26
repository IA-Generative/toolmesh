from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.config import Settings, get_settings
from app.db.models import Source, Tool
from app.db.session import get_db
from app.execution import ExecutionError, execute
from app.registry import is_visible, visible_tools
from app.schemas import ToolOut

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
