from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.config import Settings
from app.db.models import Source, Tool
from app.execution import ExecutionError, _call_api, build_request, execute
from tests.test_tools import auth, make_token

PUBLIC = "http://93.184.216.34"  # a public address: literals need no DNS lookup
SETTINGS = Settings()


def api_tool(path: str = "/orders/{id}", method: str = "GET") -> Tool:
    return Tool(name="t", method=method, path=path)


def api_source(url: str = PUBLIC, **kwargs: Any) -> Source:
    return Source(name="s", type="api", url=url, **({"auth_mode": "none"} | kwargs))


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_path_parameters_query_and_body_are_split() -> None:
    request = build_request(
        api_tool("/orders/{id}/items", "POST"), "http://x.test/", {"id": "a/b 1", "status": "open", "body": {"n": 1}}
    )

    assert request == {"url": "http://x.test/orders/a%2Fb%201/items", "params": {"status": "open"}, "json": {"n": 1}}


def test_body_is_only_sent_with_a_body_method() -> None:
    assert build_request(api_tool("/o", "GET"), "http://x.test", {"body": {"n": 1}})["json"] is None
    assert build_request(api_tool("/o", "DELETE"), "http://x.test", {})["json"] is None


def test_a_missing_path_parameter_is_reported() -> None:
    with pytest.raises(ExecutionError, match="id") as exc:
        build_request(api_tool(), "http://x.test", {"other": 1})

    assert exc.value.status_code == 422


async def test_api_call_returns_the_json_answer() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(method=request.method, url=str(request.url), auth=request.headers.get("authorization"))
        return httpx.Response(200, json={"id": 7})

    result = await _call_api(
        api_source(),
        api_tool(),
        {"id": 7, "verbose": True},
        {"Authorization": "Bearer x"},
        SETTINGS,
        client_for(handler),
    )

    assert result == {
        "ok": True,
        "status": 200,
        "content_type": "application/json",
        "content": {"id": 7},
        "truncated": False,
    }
    assert seen == {"method": "GET", "url": f"{PUBLIC}/orders/7?verbose=true", "auth": "Bearer x"}


async def test_api_errors_are_results_not_failures() -> None:
    result = await _call_api(
        api_source(), api_tool(), {"id": 1}, {}, SETTINGS, client_for(lambda _: httpx.Response(404, text="nope"))
    )

    assert (result["ok"], result["status"], result["content"]) == (False, 404, "nope")


async def test_long_answers_are_truncated() -> None:
    settings = Settings(execution_max_response_bytes=10)

    result = await _call_api(
        api_source(), api_tool(), {"id": 1}, {}, settings, client_for(lambda _: httpx.Response(200, text="x" * 50))
    )

    assert (len(result["content"]), result["truncated"]) == (10, True)


async def test_an_unreachable_api_is_a_bad_gateway() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(ExecutionError, match="unreachable") as exc:
        await _call_api(api_source(), api_tool(), {"id": 1}, {}, SETTINGS, client_for(handler))

    assert exc.value.status_code == 502


async def test_internal_addresses_are_not_called() -> None:
    with pytest.raises(ExecutionError) as exc:
        await _call_api(
            api_source("http://127.0.0.1:8000"), api_tool(), {"id": 1}, {}, SETTINGS, client_for(lambda _: None)
        )

    assert exc.value.status_code == 422


async def test_token_exchange_asks_for_the_audience_of_the_source(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_exchange(settings: Settings, subject_token: str, audience: str) -> str:
        calls.append((subject_token, audience))
        return "exchanged"

    async def fake_call(source, tool, arguments, headers, settings, client=None):
        return {"ok": True, "status": 200, "content_type": None, "content": headers, "truncated": False}

    monkeypatch.setattr("app.execution.exchange_token", fake_exchange)
    monkeypatch.setattr("app.execution._call_api", fake_call)
    source = api_source(auth_mode="token_exchange", audience="orders")

    result = await execute(source, api_tool(), {"id": 1}, "user-token", SETTINGS)

    assert calls == [("user-token", "orders")]
    assert result["content"] == {"Authorization": "Bearer exchanged"}


async def test_skills_cannot_be_run_yet() -> None:
    with pytest.raises(ExecutionError) as exc:
        await execute(Source(name="s", type="skill"), Tool(name="s"), {}, None, SETTINGS)

    assert exc.value.status_code == 501


# --- Route ---------------------------------------------------------------------------------------------------------


async def test_call_route_runs_the_tool(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tool_id) -> None:
    seen: dict[str, Any] = {}

    async def fake_execute(
        source: Source, tool: Tool, arguments: dict, user_token: str | None, settings: Settings
    ) -> dict:
        seen.update(source=source.name, tool=tool.name, arguments=arguments, token=user_token)
        return {"ok": True, "status": None, "content_type": None, "content": "hi", "truncated": False, "duration_ms": 3}

    monkeypatch.setattr("app.routers.tools.execute", fake_execute)
    token = make_token(["user"])

    response = await client.post(
        f"/api/me/tools/{await tool_id('web_search')}/call", json={"arguments": {"query": "x"}}, headers=auth(token)
    )

    assert response.status_code == 200
    assert response.json()["content"] == "hi"
    assert seen == {"source": "search-mcp", "tool": "web_search", "arguments": {"query": "x"}, "token": token}


async def test_call_route_reports_execution_errors(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tool_id
) -> None:
    async def failing(*_: Any) -> dict:
        raise ExecutionError("boom", 502)

    monkeypatch.setattr("app.routers.tools.execute", failing)

    response = await client.post(
        f"/api/me/tools/{await tool_id('web_search')}/call", json={}, headers=auth(make_token(["user"]))
    )

    assert (response.status_code, response.json()["detail"]) == (502, "boom")


async def test_call_route_hides_unknown_and_restricted_tools(client: AsyncClient, tool_id) -> None:
    user = auth(make_token(["user"]))

    assert (await client.post("/api/me/tools/nope/call", json={}, headers=user)).status_code == 404
    assert (
        await client.post(f"/api/me/tools/{await tool_id('query_database')}/call", json={}, headers=user)
    ).status_code == 404  # admin only
    assert (await client.post(f"/api/me/tools/{await tool_id('web_search')}/call", json={})).status_code == 401


async def test_a_skill_call_is_not_implemented(client: AsyncClient, tool_id) -> None:
    response = await client.post(
        f"/api/me/tools/{await tool_id('summarize')}/call",
        json={"arguments": {"text": "x"}},
        headers=auth(make_token(["user"])),
    )

    assert response.status_code == 501
