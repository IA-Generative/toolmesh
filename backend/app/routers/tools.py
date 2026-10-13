from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import CurrentUser

router = APIRouter(prefix="/api", tags=["tools"])


class Tool(BaseModel):
    name: str
    description: str
    source: str
    type: Literal["mcp", "api", "skill"]
    # Role required to see the tool; None means any authenticated caller.
    required_role: str | None = None


# Mock data until the registry (#2) exists.
MOCK_TOOLS = [
    Tool(name="web_search", description="Search the web", source="search-mcp", type="mcp"),
    Tool(name="get_weather", description="Current weather for a city", source="weather-api", type="api"),
    Tool(name="summarize", description="Summarize a text", source="text-skills", type="skill", required_role="user"),
    Tool(
        name="query_database",
        description="Run a read-only SQL query on the internal DB",
        source="internal-db-mcp",
        type="mcp",
        required_role="admin",
    ),
    Tool(
        name="manage_sources",
        description="Register or remove indexed sources",
        source="toolmesh-admin",
        type="api",
        required_role="admin",
    ),
]


class MyToolsResponse(BaseModel):
    user: str | None
    roles: list[str]
    tools: list[Tool]


@router.get("/me/tools")
async def list_my_tools(user: CurrentUser) -> MyToolsResponse:
    """Tools visible to the authenticated caller (mock data, filtered by realm role)."""
    visible = [t for t in MOCK_TOOLS if t.required_role is None or t.required_role in user.roles]
    return MyToolsResponse(user=user.username or user.sub, roles=user.roles, tools=visible)
