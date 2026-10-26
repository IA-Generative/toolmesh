from typing import Any

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.discovery import DiscoveryError, check_url, is_exposed, matches, tools_from_spec
from app.schemas import SourceIn, ToolIn
from tests.test_sources import API_SOURCE, auth, create, make_token, user

SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "paths": {
        "/users": {
            "get": {"operationId": "listUsers", "summary": "List users", "tags": ["users"]},
            "post": {
                "summary": "Create a user",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/NewUser"}}},
                },
            },
        },
        "/users/{id}": {
            "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
            "get": {"parameters": [{"name": "verbose", "in": "query", "schema": {"type": "boolean"}}]},
            "delete": {"description": "Remove a user"},
        },
        "/internal/metrics": {"get": {}},
    },
    "components": {
        "schemas": {
            "NewUser": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        }
    },
}


def by_name(tools: list[ToolIn]) -> dict[str, ToolIn]:
    return {t.name: t for t in tools}


def test_patterns_use_wildcards_on_method_and_path() -> None:
    assert matches("GET /users*", "GET /users/{id}")
    assert matches("delete *", "DELETE /users/{id}")
    assert matches("GET /user?", "GET /users")
    assert not matches("GET /users", "GET /users/{id}")
    assert not matches("GET *", "POST /x")
    assert matches("GET /a.b", "GET /a.b") and not matches("GET /a.b", "GET /axb")  # `.` is literal


def test_exclusion_beats_inclusion_and_empty_include_means_all() -> None:
    assert is_exposed("GET /a", [], [])
    assert not is_exposed("DELETE /a", ["GET *"], [])
    assert not is_exposed("GET /internal/x", ["GET *"], ["*/internal/*"])


def test_each_operation_becomes_a_tool() -> None:
    tools = by_name(tools_from_spec(SPEC, [], []))

    assert set(tools) == {"listUsers", "post_users", "get_users_id", "delete_users_id", "get_internal_metrics"}
    assert (tools["listUsers"].method, tools["listUsers"].path, tools["listUsers"].tags) == ("GET", "/users", ["users"])
    assert tools["listUsers"].description == "List users"
    assert tools["delete_users_id"].description == "Remove a user"


def test_parameters_and_body_build_the_input_schema() -> None:
    tools = by_name(tools_from_spec(SPEC, [], []))

    assert tools["get_users_id"].input_schema == {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "verbose": {"type": "boolean"}},
        "required": ["id"],
    }
    assert tools["post_users"].input_schema == {
        "type": "object",
        "properties": {"body": SPEC["components"]["schemas"]["NewUser"]},
        "required": ["body"],
    }


def test_include_and_exclude_patterns_filter_operations() -> None:
    tools = tools_from_spec(SPEC, ["GET *"], ["*/internal/*"])

    assert {t.name for t in tools} == {"listUsers", "get_users_id"}


def test_circular_refs_do_not_loop() -> None:
    node = {"type": "object", "properties": {"child": {"$ref": "#/components/schemas/Node"}}}
    spec = {
        "paths": {
            "/n": {
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": node | {"$ref": "#/components/schemas/Node"}}}
                    }
                }
            }
        },
        "components": {"schemas": {"Node": node}},
    }

    assert len(tools_from_spec(spec, [], [])) == 1


def test_duplicate_operation_ids_are_made_unique() -> None:
    spec = {"paths": {"/a": {"get": {"operationId": "x"}}, "/b": {"get": {"operationId": "x"}}}}

    assert [t.name for t in tools_from_spec(spec, [], [])] == ["x", "x_2"]


@pytest.mark.parametrize(
    ("url", "allow_private"),
    [("http://127.0.0.1/spec", False), ("http://10.0.0.5/spec", False), ("http://169.254.169.254/latest", True)],
    ids=["loopback", "private", "link-local-even-if-private-allowed"],
)
async def test_internal_addresses_are_refused(url: str, allow_private: bool) -> None:
    settings = Settings(discovery_allow_private_hosts=allow_private)

    with pytest.raises(DiscoveryError):
        await check_url(url, settings)


async def test_private_addresses_pass_when_allowed_and_bad_schemes_never() -> None:
    await check_url("http://127.0.0.1:8000/x", Settings(discovery_allow_private_hosts=True))
    with pytest.raises(DiscoveryError):
        await check_url("file:///etc/passwd", Settings(discovery_allow_private_hosts=True))


# --- Routes --------------------------------------------------------------------------------------------------------


@pytest.fixture
def found(monkeypatch: pytest.MonkeyPatch) -> list[ToolIn]:
    """What the (faked) discovery returns; tests mutate the list to change it."""
    tools = [ToolIn(name="list_things", description="List", method="GET", path="/things")]

    async def fake(source: SourceIn, *_: Any) -> list[ToolIn]:
        if not tools:
            raise DiscoveryError("No tool found", 422)
        return list(tools)

    monkeypatch.setattr("app.routers.sources.discover", fake)
    return tools


def declared_none(**patch: Any) -> dict[str, Any]:
    return API_SOURCE | {"tools": []} | patch


async def test_discover_previews_without_saving(client: AsyncClient, found: list[ToolIn]) -> None:
    response = await client.post("/api/sources/discover", json=declared_none(), headers=user())

    assert response.status_code == 200
    assert [t["name"] for t in response.json()["tools"]] == ["list_things"]
    assert "orders-api" not in {s["name"] for s in (await client.get("/api/sources", headers=user())).json()}


async def test_create_without_tools_discovers_them(client: AsyncClient, found: list[ToolIn]) -> None:
    response = await create(client, declared_none())

    assert response.status_code == 201
    assert [t["name"] for t in response.json()["tools"]] == ["list_things"]
    assert (await client.get("/api/me/tools/list_things", headers=user())).status_code == 200


async def test_discovery_failures_are_reported(client: AsyncClient, found: list[ToolIn]) -> None:
    found.clear()

    response = await create(client, declared_none())

    assert (response.status_code, response.json()["detail"]) == (422, "No tool found")
    assert "orders-api" not in {s["name"] for s in (await client.get("/api/sources", headers=user())).json()}


async def test_discovered_name_clashes_are_prefixed_by_the_source(client: AsyncClient, found: list[ToolIn]) -> None:
    found[:] = [ToolIn(name="web_search"), ToolIn(name="fresh")]  # `web_search` belongs to the test search-mcp

    response = await create(client, declared_none())

    assert sorted(t["name"] for t in response.json()["tools"]) == ["fresh", "orders-api.web_search"]


async def test_refresh_adds_removes_and_updates_tools(client: AsyncClient, found: list[ToolIn]) -> None:
    source_id = (await create(client, declared_none())).json()["id"]
    found[:] = [ToolIn(name="list_things", description="Updated"), ToolIn(name="new_thing")]

    response = await client.post(f"/api/sources/{source_id}/refresh", headers=user())

    tools = {t["name"]: t for t in response.json()["tools"]}
    assert set(tools) == {"list_things", "new_thing"}
    assert tools["list_things"]["description"] == "Updated"


async def test_refresh_keeps_a_disabled_tool_disabled(
    client: AsyncClient, found: list[ToolIn], session_factory
) -> None:
    from sqlalchemy import update

    from app.db.models import Tool

    source_id = (await create(client, declared_none())).json()["id"]
    async with session_factory() as db:
        await db.execute(update(Tool).where(Tool.name == "list_things").values(enabled=False))
        await db.commit()

    response = await client.post(f"/api/sources/{source_id}/refresh", headers=user())

    assert response.json()["tools"][0]["enabled"] is False


async def test_refresh_rules(client: AsyncClient, found: list[ToolIn]) -> None:
    source_id = (await create(client, declared_none())).json()["id"]
    skill_id = (await create(client, {"name": "rewrite", "type": "skill", "description": "x"})).json()["id"]

    assert (await client.post(f"/api/sources/{source_id}/refresh", headers=user("other"))).status_code == 403
    assert (await client.post(f"/api/sources/{skill_id}/refresh", headers=user())).status_code == 422
    assert (await client.post("/api/sources/nope/refresh", headers=user())).status_code == 404
    assert (
        await client.post(f"/api/sources/{source_id}/refresh", headers=auth(make_token(["admin"], sub="boss")))
    ).status_code == 200


async def test_discover_requires_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/sources/discover", json=declared_none())).status_code == 401
