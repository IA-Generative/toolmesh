from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import fakeredis
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_jwks_client
from app.auth.session import SessionStore, get_session_store
from app.config import Settings, get_settings
from app.main import app
from tests.test_tools import AUDIENCE, ISSUER, _FakeJwks, make_token

SETTINGS = Settings(
    oidc_issuer=ISSUER,
    oidc_audience=AUDIENCE,
    frontend_url="http://spa.test",
    backend_public_url="http://api.test",
)


_REAL_CLIENT = httpx.AsyncClient  # captured before any monkeypatch so mocks never stack


@pytest.fixture
async def store() -> SessionStore:
    return SessionStore(fakeredis.FakeAsyncRedis(decode_responses=True), SETTINGS)


@pytest.fixture
async def client(store: SessionStore) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[get_jwks_client] = lambda: _FakeJwks()
    app.dependency_overrides[get_session_store] = lambda: store
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.test") as c:
        yield c
    app.dependency_overrides.clear()


def _token_response(roles: list[str]) -> dict:
    return {"access_token": make_token(roles), "refresh_token": "r1", "expires_in": 300, "id_token": "idt"}


def _mock_keycloak(monkeypatch: pytest.MonkeyPatch, response: dict | None = None, status_code: int = 200) -> list:
    """Route the backend's outgoing calls to Keycloak to a canned answer; returns the requests seen."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status_code, json=response or {})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    return seen


async def _login(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, roles: list[str], redirect: str = "/") -> str:
    """Run login + callback; returns the final Location."""
    login = await client.get("/api/auth/login", params={"redirect": redirect})
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    _mock_keycloak(monkeypatch, _token_response(roles))
    callback = await client.get("/api/auth/callback", params={"code": "c", "state": state})
    return callback.headers["location"]


async def test_login_redirects_to_keycloak_with_pkce(client: AsyncClient) -> None:
    response = await client.get("/api/auth/login")

    assert response.status_code == 307
    url = urlparse(response.headers["location"])
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/protocol/openid-connect/auth"
    assert query["client_id"] == ["toolmesh-bff"]
    assert query["redirect_uri"] == ["http://api.test/api/auth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] and query["state"]


async def test_callback_sets_http_only_cookie_and_redirects_to_spa(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    location = await _login(client, monkeypatch, ["user"], redirect="/tools")

    assert location == "http://spa.test/tools"
    set_cookie = client.cookies.jar
    assert any(c.name == "toolmesh_session" for c in set_cookie)


async def test_session_cookie_authenticates_without_bearer(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _login(client, monkeypatch, ["user"])

    me = await client.get("/api/auth/me")
    tools = await client.get("/api/me/tools")

    assert me.status_code == 200
    assert me.json() == {"sub": "u1", "username": "alice", "email": None, "roles": ["user"]}
    assert tools.status_code == 200


async def test_unsafe_redirect_falls_back_to_root(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert await _login(client, monkeypatch, ["user"], redirect="//evil.com") == "http://spa.test/"


async def test_callback_with_unknown_state_is_400(client: AsyncClient) -> None:
    response = await client.get("/api/auth/callback", params={"code": "c", "state": "nope"})

    assert response.status_code == 400


async def test_callback_with_keycloak_error_is_400(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    login = await client.get("/api/auth/login")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    _mock_keycloak(monkeypatch, {"error": "invalid_grant"}, status_code=400)

    response = await client.get("/api/auth/callback", params={"code": "c", "state": state})

    assert response.status_code == 400


async def test_unknown_session_cookie_is_401(client: AsyncClient) -> None:
    client.cookies.set("toolmesh_session", "forged")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_expired_access_token_is_refreshed(
    client: AsyncClient, store: SessionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _login(client, monkeypatch, ["user"])
    session_id = client.cookies["toolmesh_session"]
    session = await store.get_session(session_id)
    session.expires_at = 0
    await store._save(session_id, session)
    seen = _mock_keycloak(
        monkeypatch, {"access_token": make_token(["user", "admin"]), "refresh_token": "r2", "expires_in": 300}
    )

    me = await client.get("/api/auth/me")

    assert me.json()["roles"] == ["user", "admin"]
    assert parse_qs(seen[0].content.decode())["grant_type"] == ["refresh_token"]


async def test_failed_refresh_drops_the_session(
    client: AsyncClient, store: SessionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _login(client, monkeypatch, ["user"])
    session_id = client.cookies["toolmesh_session"]
    session = await store.get_session(session_id)
    session.expires_at = 0
    await store._save(session_id, session)
    _mock_keycloak(monkeypatch, status_code=400)

    assert (await client.get("/api/auth/me")).status_code == 401
    assert await store.get_session(session_id) is None


async def test_logout_ends_session_and_returns_end_session_url(
    client: AsyncClient, store: SessionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _login(client, monkeypatch, ["user"])
    session_id = client.cookies["toolmesh_session"]
    seen = _mock_keycloak(monkeypatch)

    response = await client.post("/api/auth/logout")

    query = parse_qs(urlparse(response.json()["redirectUrl"]).query)
    assert query["id_token_hint"] == ["idt"]
    assert query["post_logout_redirect_uri"] == ["http://spa.test"]
    assert parse_qs(seen[0].content.decode())["refresh_token"] == ["r1"]
    assert await store.get_session(session_id) is None
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_bearer_still_works_and_wins_over_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {make_token(['admin'])}"})

    assert response.status_code == 200
    assert response.json()["roles"] == ["admin"]


async def test_cors_allows_only_the_spa_origin_with_credentials(client: AsyncClient) -> None:
    ok = await client.options(
        "/api/auth/me", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )

    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert ok.headers["access-control-allow-credentials"] == "true"
    bad = await client.options(
        "/api/auth/me", headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in bad.headers


async def test_token_returns_keycloak_tokens(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _mock_keycloak(monkeypatch, _token_response(["user"]))

    response = await client.post("/api/auth/token", json={"username": "user", "password": "user"})

    assert response.status_code == 200
    assert response.json()["refresh_token"] == "r1"
    assert parse_qs(seen[0].content.decode())["grant_type"] == ["password"]


async def test_token_with_bad_credentials_is_401(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_keycloak(monkeypatch, {"error": "invalid_grant"}, status_code=401)

    response = await client.post("/api/auth/token", json={"username": "user", "password": "nope"})

    assert response.status_code == 401


async def test_refresh_returns_new_tokens(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _mock_keycloak(monkeypatch, _token_response(["user"]))

    response = await client.post("/api/auth/refresh", json={"refresh_token": "r0"})

    assert response.status_code == 200
    assert parse_qs(seen[0].content.decode())["refresh_token"] == ["r0"]
