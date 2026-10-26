from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source
from app.registry import build_source
from app.schemas import SourceIn

SEED_USER = "seed"

DEMO_SOURCES = [
    SourceIn(
        name="search-mcp",
        type="mcp",
        url="https://search.example.org/mcp",
        tools=[
            {
                "name": "web_search",
                "description": "Search the web and return the most relevant results with their snippets.",
                "tags": ["recherche", "web"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Terms to search for"},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                        "language": {"type": "string", "enum": ["fr", "en"], "default": "fr"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "fetch_page",
                "description": "Download a web page and return its readable text.",
                "tags": ["web", "texte"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "format": "uri", "description": "Page to download"},
                        "include_links": {"type": "boolean", "default": False},
                    },
                    "required": ["url"],
                },
            },
        ],
    ),
    SourceIn(
        name="weather-api",
        type="api",
        url="https://weather.example.org",
        openapi_url="https://weather.example.org/openapi.json",
        tools=[
            {
                "name": "get_weather",
                "description": "Current weather conditions and short-term forecast for a city.",
                "tags": ["météo", "données"],
                "method": "GET",
                "path": "/weather/{city}",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                        "units": {"type": "string", "enum": ["metric", "imperial"], "default": "metric"},
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "get_forecast",
                "description": "Seven-day forecast for a city.",
                "tags": ["météo", "données"],
                "method": "GET",
                "path": "/forecast/{city}",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "days": {"type": "integer", "minimum": 1, "maximum": 7, "default": 7},
                    },
                    "required": ["city"],
                },
            },
        ],
    ),
    SourceIn(
        name="summarize",
        type="skill",
        description="Summarize a long text into a few key points.",
        tags=["texte", "rédaction"],
        required_role="user",
        tools=[
            {
                "name": "summarize",
                "description": "Summarize a long text into a few key points.",
                "tags": ["texte", "rédaction"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to summarize", "maxLength": 5000},
                        "max_sentences": {"type": "integer", "minimum": 1, "default": 3},
                        "style": {"type": "string", "enum": ["neutral", "bullet_points"], "default": "neutral"},
                    },
                    "required": ["text"],
                },
            }
        ],
    ),
    SourceIn(
        name="internal-db-mcp",
        type="mcp",
        url="https://db.internal.example.org/mcp",
        required_role="admin",
        tools=[
            {
                "name": "query_database",
                "description": "Run a read-only SQL query on the internal DB.",
                "tags": ["données", "sql"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "Read-only SELECT statement"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
                    },
                    "required": ["sql"],
                },
            }
        ],
    ),
    SourceIn(
        name="toolmesh-admin",
        type="api",
        url="https://admin.internal.example.org",
        openapi_url="https://admin.internal.example.org/openapi.json",
        required_role="admin",
        tools=[
            {
                "name": "manage_sources",
                "description": "Register or remove indexed sources.",
                "tags": ["administration"],
                "method": "POST",
                "path": "/sources",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "remove"]},
                        "url": {"type": "string", "format": "uri"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to attach"},
                    },
                    "required": ["action", "url"],
                },
            }
        ],
    ),
]


async def seed_demo_data(db: AsyncSession) -> bool:
    """Insert the demo sources if the registry is empty; returns whether it did."""
    if await db.scalar(select(func.count()).select_from(Source)):
        return False
    db.add_all(build_source(payload, created_by=SEED_USER) for payload in DEMO_SOURCES)
    await db.commit()
    return True
