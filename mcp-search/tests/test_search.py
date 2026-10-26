import httpx
import pytest
from mcp.client import Client

from app.config import Settings
from app.search import search
from app.server import mcp

SETTINGS = Settings(searxng_url="http://searx.test")

RESULTS = {
    "results": [
        {
            "title": "A",
            "url": "https://a.test",
            "content": "about a",
            "engine": "duckduckgo",
            "publishedDate": "2026-01-02",
        },
        {"title": "A again", "url": "https://a.test", "content": "dup"},
        {"title": "B", "url": "https://b.test", "content": "about b", "engine": "brave"},
        {"title": "no url"},
        {"title": "C", "url": "https://c.test"},
    ]
}


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_search_maps_dedupes_and_limits_results() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=RESULTS)

    results = await search(SETTINGS, "chat", max_results=2, time_range="week", client=client_for(handler))

    assert [r["url"] for r in results] == ["https://a.test", "https://b.test"]
    assert results[0] == {
        "title": "A",
        "url": "https://a.test",
        "snippet": "about a",
        "engine": "duckduckgo",
        "published": "2026-01-02",
    }
    assert seen == {"q": "chat", "format": "json", "language": "fr", "categories": "general", "time_range": "week"}


@pytest.mark.parametrize(
    ("status", "message"),
    [(403, "json"), (500, "500")],
    ids=["json-disabled", "server-error"],
)
async def test_search_explains_searxng_failures(status: int, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        await search(SETTINGS, "x", client=client_for(lambda _: httpx.Response(status)))


async def test_search_reports_an_unreachable_searxng() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(RuntimeError, match="unreachable"):
        await search(SETTINGS, "x", client=client_for(handler))


async def test_tools_are_exposed_over_mcp() -> None:
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    assert set(tools) == {"web_search", "fetch_page"}
    assert tools["web_search"].input_schema["required"] == ["query"]
    assert tools["fetch_page"].input_schema["required"] == ["url"]


async def test_endpoint_rejects_requests_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.server import create_app

    monkeypatch.setenv("MCP_SEARCH_OIDC_JWKS_URL", "http://unused.test/certs")
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp", json={})

    assert response.status_code == 401
