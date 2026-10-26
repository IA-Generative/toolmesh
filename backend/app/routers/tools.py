from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import CurrentUser

router = APIRouter(prefix="/api", tags=["tools"])


class Tool(BaseModel):
    name: str
    description: str
    source: str
    type: Literal["mcp", "api", "skill"]
    tags: list[str] = []
    # Where the tool comes from: the MCP server / API it is exposed by, and for an API the route it maps to.
    source_url: str | None = None
    method: str | None = None
    path: str | None = None
    # JSON Schema of the arguments, used by the front to build the test form.
    input_schema: dict[str, Any] | None = None
    # Role required to see the tool; None means any authenticated caller.
    required_role: str | None = None


# Mock data until the registry (#2) exists.
MOCK_TOOLS = [
    Tool(
        name="web_search",
        description="Search the web and return the most relevant results with their snippets.",
        source="search-mcp",
        source_url="https://search.example.org/mcp",
        type="mcp",
        tags=["recherche", "web"],
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Terms to search for"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                "language": {"type": "string", "enum": ["fr", "en"], "default": "fr"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="fetch_page",
        description="Download a web page and return its readable text.",
        source="search-mcp",
        source_url="https://search.example.org/mcp",
        type="mcp",
        tags=["web", "texte"],
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri", "description": "Page to download"},
                "include_links": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="get_weather",
        description="Current weather conditions and short-term forecast for a city.",
        source="weather-api",
        source_url="https://weather.example.org/openapi.json",
        method="GET",
        path="/weather/{city}",
        type="api",
        tags=["météo", "données"],
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "units": {"type": "string", "enum": ["metric", "imperial"], "default": "metric"},
            },
            "required": ["city"],
        },
    ),
    Tool(
        name="get_forecast",
        description="Seven-day forecast for a city.",
        source="weather-api",
        source_url="https://weather.example.org/openapi.json",
        method="GET",
        path="/forecast/{city}",
        type="api",
        tags=["météo", "données"],
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "days": {"type": "integer", "minimum": 1, "maximum": 7, "default": 7},
            },
            "required": ["city"],
        },
    ),
    Tool(
        name="summarize",
        description="Summarize a long text into a few key points.",
        source="text-skills",
        type="skill",
        tags=["texte", "rédaction"],
        required_role="user",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to summarize", "maxLength": 5000},
                "max_sentences": {"type": "integer", "minimum": 1, "default": 3},
                "style": {"type": "string", "enum": ["neutral", "bullet_points"], "default": "neutral"},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="query_database",
        description="Run a read-only SQL query on the internal DB.",
        source="internal-db-mcp",
        source_url="https://db.internal.example.org/mcp",
        type="mcp",
        tags=["données", "sql"],
        required_role="admin",
        input_schema={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "Read-only SELECT statement"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
            },
            "required": ["sql"],
        },
    ),
    Tool(
        name="manage_sources",
        description="Register or remove indexed sources.",
        source="toolmesh-admin",
        source_url="https://admin.internal.example.org/openapi.json",
        method="POST",
        path="/sources",
        type="api",
        tags=["administration"],
        required_role="admin",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "remove"]},
                "url": {"type": "string", "format": "uri"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to attach to the source"},
            },
            "required": ["action", "url"],
        },
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
