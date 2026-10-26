"""MCP server exposing web search (through SearXNG) and page reading."""

from mcp.server.mcpserver import MCPServer

from app.auth import AuthSettings, BearerAuthMiddleware
from app.config import Settings
from app.fetch import fetch_page as _fetch_page
from app.search import Category, TimeRange
from app.search import search as _search

mcp = MCPServer(
    "search",
    instructions="Search the web, then read the pages worth reading. Results come from a SearXNG meta-search engine.",
)


@mcp.tool()
async def web_search(
    query: str,
    max_results: int = 5,
    language: str = "fr",
    time_range: TimeRange | None = None,
    category: Category = "general",
) -> list[dict]:
    """Search the web. Returns title, url, snippet and source engine for each result.

    `language` is a code such as fr or en; `time_range` restricts to the last day, week, month or year.
    """
    return await _search(Settings(), query, max(1, min(max_results, 20)), language, time_range, category)


@mcp.tool()
async def fetch_page(url: str, max_chars: int = 8000) -> dict:
    """Download a web page and return its title and readable text (truncated to `max_chars`, 500 to 50000)."""
    return await _fetch_page(Settings(), url, max_chars)


def create_app():
    """ASGI app serving MCP over streamable HTTP at /mcp, protected by a Keycloak bearer token."""
    app = mcp.streamable_http_app(host="0.0.0.0")
    settings = AuthSettings()
    if settings.auth_enabled:
        app.add_middleware(BearerAuthMiddleware, settings=settings)
    return app
