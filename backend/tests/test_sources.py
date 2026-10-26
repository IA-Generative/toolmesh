from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.migrate import alembic_config
from app.db.models import Base
from tests.registry_data import seed_test_registry
from tests.test_tools import auth, make_token

API_SOURCE: dict[str, Any] = {
    "name": "orders-api",
    "type": "api",
    "url": "https://orders.example.org",
    "openapi_url": "https://orders.example.org/openapi.json",
    "auth_mode": "token_exchange",
    "audience": "orders",
    "endpoint_include": ["GET *"],
    "tools": [
        {
            "name": "list_orders",
            "description": "List the orders",
            "tags": ["commandes"],
            "method": "GET",
            "path": "/orders",
            "input_schema": {"type": "object", "properties": {"status": {"type": "string"}}},
        }
    ],
}


def user(sub: str = "u1", roles: tuple[str, ...] = ("user",)) -> dict[str, str]:
    return auth(make_token(list(roles), sub=sub))


async def create(client: AsyncClient, body: dict[str, Any], **kwargs: Any):
    return await client.post("/api/sources", json=body, headers=kwargs.get("headers", user()))


async def test_create_api_source_exposes_its_tools(client: AsyncClient) -> None:
    response = await create(client, API_SOURCE)

    assert response.status_code == 201
    body = response.json()
    assert body["created_by"] == "u1"
    assert [t["name"] for t in body["tools"]] == ["list_orders"]

    detail = await client.get("/api/me/tools/list_orders", headers=user())
    assert detail.status_code == 200
    assert detail.json() | {"input_schema": None} == {
        "name": "list_orders",
        "description": "List the orders",
        "source": "orders-api",
        "source_version": None,
        "type": "api",
        "tags": ["commandes"],
        "source_url": "https://orders.example.org/openapi.json",
        "method": "GET",
        "path": "/orders",
        "input_schema": None,
        "auth_mode": "token_exchange",
        "audience": "orders",
        "required_role": None,
    }


async def test_skill_becomes_a_single_tool_and_needs_a_description(client: AsyncClient) -> None:
    missing = await create(client, {"name": "rewrite", "type": "skill"})
    assert missing.status_code == 422

    created = await create(
        client, {"name": "rewrite", "type": "skill", "description": "Rewrite a text", "tags": ["texte"]}
    )
    assert created.status_code == 201
    tool = (await client.get("/api/me/tools/rewrite", headers=user())).json()
    assert (tool["type"], tool["description"], tool["tags"], tool["source_url"]) == (
        "skill",
        "Rewrite a text",
        ["texte"],
        None,
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "mcp", "url": None},
        {"openapi_url": None},
        {"audience": None},
        {"name": "has space"},
        {"type": "unknown"},
    ],
    ids=["mcp-without-url", "api-without-openapi", "token-exchange-without-audience", "bad-name", "bad-type"],
)
async def test_invalid_sources_are_rejected(client: AsyncClient, patch: dict[str, Any]) -> None:
    assert (await create(client, API_SOURCE | patch)).status_code == 422


async def test_duplicate_names_are_rejected(client: AsyncClient) -> None:
    assert (await create(client, API_SOURCE)).status_code == 201

    assert (await create(client, API_SOURCE)).status_code == 409
    clash = API_SOURCE | {"name": "other-api"}  # same tool name `list_orders`
    assert (await create(client, clash)).status_code == 409
    assert (await create(client, {"name": "web_search", "type": "skill", "description": "x"})).status_code == 409


async def test_public_source_drops_the_audience(client: AsyncClient) -> None:
    body = (await create(client, API_SOURCE | {"auth_mode": "none"})).json()

    assert (body["auth_mode"], body["audience"]) == ("none", None)


async def test_role_restricted_sources_are_hidden(client: AsyncClient) -> None:
    created = await create(client, API_SOURCE | {"required_role": "admin"}, headers=user("a", ("admin",)))
    source_id = created.json()["id"]

    assert (await client.get(f"/api/sources/{source_id}", headers=user())).status_code == 404
    assert (await client.get("/api/me/tools/list_orders", headers=user())).status_code == 404
    assert (await client.get(f"/api/sources/{source_id}", headers=user("a", ("admin",)))).status_code == 200
    assert source_id not in {s["id"] for s in (await client.get("/api/sources", headers=user())).json()}


async def test_only_creator_or_admin_can_delete(client: AsyncClient) -> None:
    source_id = (await create(client, API_SOURCE)).json()["id"]

    assert (await client.delete(f"/api/sources/{source_id}", headers=user("someone-else"))).status_code == 403
    assert (await client.delete(f"/api/sources/{source_id}", headers=user("u1"))).status_code == 204
    assert (await client.get("/api/me/tools/list_orders", headers=user())).status_code == 404

    again = (await create(client, API_SOURCE)).json()["id"]
    assert (await client.delete(f"/api/sources/{again}", headers=user("boss", ("admin",)))).status_code == 204
    assert (await client.delete(f"/api/sources/{again}", headers=user())).status_code == 404


async def test_sources_require_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/sources", json=API_SOURCE)).status_code == 401
    assert (await client.get("/api/sources")).status_code == 401
    assert (await client.get("/api/me/tools/web_search")).status_code == 401


async def test_unknown_tool_is_404(client: AsyncClient) -> None:
    assert (await client.get("/api/me/tools/nope", headers=user())).status_code == 404


async def test_seeding_only_fills_an_empty_registry(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as db:
        assert await seed_test_registry(db) is True
        assert await seed_test_registry(db) is False


def test_migrations_match_the_models(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}"
    command.upgrade(alembic_config(url), "head")

    engine = create_engine(f"sqlite:///{tmp_path / 'registry.db'}")
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
