import time
from collections.abc import AsyncIterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import decode_token, get_jwks_client
from app.config import Settings, get_settings
from app.main import app

ISSUER = "http://kc.test/realms/toolmesh"
AUDIENCE = "toolmesh"

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _SigningKey:
    key = _key.public_key()


class _FakeJwks:
    def get_signing_key_from_jwt(self, token: str) -> _SigningKey:
        return _SigningKey()


def make_token(roles: list[str], *, key: Any = _key, **overrides: Any) -> str:
    claims = {
        "sub": "u1",
        "preferred_username": "alice",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": roles},
    } | overrides
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(keycloak_url="http://kc.test")
    app.dependency_overrides[get_jwks_client] = lambda: _FakeJwks()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_missing_token_is_401(client: AsyncClient) -> None:
    assert (await client.get("/api/me/tools")).status_code == 401


async def test_user_sees_only_non_admin_tools(client: AsyncClient) -> None:
    response = await client.get("/api/me/tools", headers=auth(make_token(["user"])))

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == "alice"
    assert {t["name"] for t in body["tools"]} == {
        "web_search",
        "fetch_page",
        "get_weather",
        "get_forecast",
        "summarize",
    }


async def test_admin_sees_all_tools(client: AsyncClient) -> None:
    response = await client.get("/api/me/tools", headers=auth(make_token(["user", "admin"])))

    names = {t["name"] for t in response.json()["tools"]}
    assert {"query_database", "manage_sources"} <= names


@pytest.mark.parametrize(
    "token",
    [
        make_token(["user"], exp=int(time.time()) - 10),
        make_token(["user"], iss="http://evil/realms/x"),
        make_token(["user"], key=_other_key),
        "not-a-jwt",
    ],
    ids=["expired", "wrong-issuer", "bad-signature", "garbage"],
)
async def test_invalid_token_is_401(client: AsyncClient, token: str) -> None:
    assert (await client.get("/api/me/tools", headers=auth(token))).status_code == 401


async def test_audience_is_ignored_unless_configured(client: AsyncClient) -> None:
    for aud in ("other", None):
        claims = {"aud": aud} if aud else {}
        token = jwt.encode(
            {"sub": "u1", "iss": ISSUER, "exp": int(time.time()) + 300, "realm_access": {"roles": ["user"]}} | claims,
            _key,
            algorithm="RS256",
        )
        assert (await client.get("/api/me/tools", headers=auth(token))).status_code == 200


async def test_configured_audience_is_enforced() -> None:
    settings = Settings(keycloak_url="http://kc.test", oidc_audience=AUDIENCE)

    assert decode_token(make_token(["user"]), settings, _FakeJwks()).sub == "u1"
    with pytest.raises(HTTPException):
        decode_token(make_token(["user"], aud="other"), settings, _FakeJwks())


async def test_downstream_call_uses_exchanged_token(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, str] = {}

    async def fake_exchange(settings: Settings, subject_token: str, audience: str) -> str:
        calls["subject"], calls["audience"] = subject_token, audience
        return "exchanged-token"

    class _FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {"service": "downstream", "username": "alice"}

    class _FakeHttpClient:
        def __init__(self, **_: Any) -> None: ...
        async def __aenter__(self) -> "_FakeHttpClient":
            return self

        async def __aexit__(self, *_: Any) -> None: ...
        async def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
            calls["authorization"] = headers["Authorization"]
            return _FakeResponse()

    monkeypatch.setattr("app.routers.downstream.exchange_token", fake_exchange)
    monkeypatch.setattr("app.routers.downstream.httpx.AsyncClient", _FakeHttpClient)
    token = make_token(["user"])

    response = await client.get("/api/mock/downstream", headers=auth(token))

    assert response.status_code == 200
    assert calls == {"subject": token, "audience": "downstream-service", "authorization": "Bearer exchanged-token"}
    assert response.json()["downstream_response"]["username"] == "alice"


async def test_downstream_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/mock/downstream")).status_code == 401


async def test_mcp_datetime_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/mock/mcp-datetime")).status_code == 401


async def test_tools_expose_tags(client: AsyncClient) -> None:
    response = await client.get("/api/me/tools", headers=auth(make_token(["user"])))

    tools = {t["name"]: t for t in response.json()["tools"]}
    assert tools["web_search"]["tags"] == ["recherche", "web"]


async def test_api_tool_exposes_its_route(client: AsyncClient) -> None:
    response = await client.get("/api/me/tools", headers=auth(make_token(["user"])))

    tools = {t["name"]: t for t in response.json()["tools"]}
    assert (tools["get_weather"]["method"], tools["get_weather"]["path"]) == ("GET", "/weather/{city}")
    assert tools["web_search"]["method"] is None


async def test_tools_expose_input_schema(client: AsyncClient) -> None:
    response = await client.get("/api/me/tools", headers=auth(make_token(["user"])))

    schema = {t["name"]: t for t in response.json()["tools"]}["web_search"]["input_schema"]
    assert schema["required"] == ["query"]
