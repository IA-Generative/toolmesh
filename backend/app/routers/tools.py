from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.session import get_db
from app.registry import visible_tools
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
