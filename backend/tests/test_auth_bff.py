from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from keycloak.exceptions import KeycloakPostError

from app.auth.dependencies import get_jwks_client
from app.auth.keycloak import get_keycloak_openid
from app.auth.session import SessionStore, get_session_store
from app.config import Settings, get_settings
from app.main import app
from tests.test_tools import AUDIENCE, ISSUER, _FakeJwks, make_token

SETTINGS = Settings(
    keycloak_url="http://kc.test",
    oidc_audience=AUDIENCE,
    frontend_url="http://spa.test",
    backend_public_url="http://api.test",
)


class _FakeKeycloak:
    """Stands in for KeycloakOpenID: answers every grant with `response`, or fails with `error`, and logs the calls."""

    def __init__(self) -> None:
        self.response: dict = {}
        self.error = False
        self.calls: list[tuple[str, dict]] = []

    async def _answer(self, name: str, **kwargs: object) -> dict:
        self.calls.append((name, kwargs))
        if self.error:
            raise KeycloakPostError(response_code=400, response_body=b"{}")
        return self.response

    async def a_token(self, **kwargs: object) -> dict:
        return await self._answer("token", **kwargs)

    async def a_refresh_token(self, refresh_token: str) -> dict:
        return await self._answer("refresh", refresh_token=refresh_token)

    async def a_logout(self, refresh_token: str) -> dict:
        return await self._answer("logout", refresh_token=refresh_token)


@pytest.fixture
def keycloak() -> _FakeKeycloak:
    return _FakeKeycloak()


@pytest.fixture
async def store(keycloak: _FakeKeycloak) -> SessionStore:
    return SessionStore(fakeredis.FakeAsyncRedis(decode_responses=True), SETTINGS, keycloak)


@pytest.fixture
async def client(store: SessionStore, keycloak: _FakeKeycloak) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[get_jwks_client] = lambda: _FakeJwks()
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_keycloak_openid] = lambda: keycloak
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.test") as c:
        yield c
    app.dependency_overrides.clear()


def _token_response(roles: list[str]) -> dict:
    return {"access_token": make_token(roles), "refresh_token": "r1", "expires_in": 300, "id_token": "idt"}


def _grant(keycloak: _FakeKeycloak, response: dict | None = None, *, error: bool = False) -> None:
    """Sets how Keycloak answers from now on, and forgets the calls made so far."""
    keycloak.response = response or {}
    keycloak.error = error
    keycloak.calls.clear()


async def _login(client: AsyncClient, keycloak: _FakeKeycloak, roles: list[str], redirect: str = "/") -> str:
    """Run login + callback; returns the final Location."""
    login = await client.get("/api/auth/login", params={"redirect": redirect})
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    _grant(keycloak, _token_response(roles))
    callback = await client.get("/api/auth/callback", params={"code": "c", "state": state})
    return callback.headers["location"]


async def test_login_redirects_to_keycloak_with_pkce(client: AsyncClient) -> None:
    response = await client.get("/api/auth/login")

    assert response.status_code == 307
    url = urlparse(response.headers["location"])
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/protocol/openid-connect/auth"
    assert query["client_id"] == ["toolmesh"]
    assert query["redirect_uri"] == ["http://api.test/api/auth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] and query["state"]


async def test_callback_sets_http_only_cookie_and_redirects_to_spa(
    client: AsyncClient, keycloak: _FakeKeycloak
) -> None:
    location = await _login(client, keycloak, ["user"], redirect="/tools")

    assert location == "http://spa.test/tools"
    set_cookie = client.cookies.jar
    assert any(c.name == "toolmesh_session" for c in set_cookie)


async def test_session_cookie_authenticates_without_bearer(client: AsyncClient, keycloak: _FakeKeycloak) -> None:
    await _login(client, keycloak, ["user"])

    me = await client.get("/api/auth/me")
    tools = await client.get("/api/me/tools")

    assert me.status_code == 200
    assert me.json() == {"sub": "u1", "username": "alice", "email": None, "roles": ["user"]}
    assert tools.status_code == 200


async def test_unsafe_redirect_falls_back_to_root(client: AsyncClient, keycloak: _FakeKeycloak) -> None:
    assert await _login(client, keycloak, ["user"], redirect="//evil.com") == "http://spa.test/"


async def test_callback_with_unknown_state_is_400(client: AsyncClient) -> None:
    response = await client.get("/api/auth/callback", params={"code": "c", "state": "nope"})

    assert response.status_code == 400


async def test_callback_with_keycloak_error_is_400(client: AsyncClient, keycloak: _FakeKeycloak) -> None:
    login = await client.get("/api/auth/login")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    _grant(keycloak, error=True)

    response = await client.get("/api/auth/callback", params={"code": "c", "state": state})

    assert response.status_code == 400


async def test_unknown_session_cookie_is_401(client: AsyncClient) -> None:
    client.cookies.set("toolmesh_session", "forged")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_expired_access_token_is_refreshed(
    client: AsyncClient, store: SessionStore, keycloak: _FakeKeycloak
) -> None:
    await _login(client, keycloak, ["user"])
    session_id = client.cookies["toolmesh_session"]
    session = await store.get_session(session_id)
    session.expires_at = 0
    await store._save(session_id, session)
    _grant(keycloak, {"access_token": make_token(["user", "admin"]), "refresh_token": "r2", "expires_in": 300})

    me = await client.get("/api/auth/me")

    assert me.json()["roles"] == ["user", "admin"]
    assert keycloak.calls == [("refresh", {"refresh_token": "r1"})]


async def test_failed_refresh_drops_the_session(
    client: AsyncClient, store: SessionStore, keycloak: _FakeKeycloak
) -> None:
    await _login(client, keycloak, ["user"])
    session_id = client.cookies["toolmesh_session"]
    session = await store.get_session(session_id)
    session.expires_at = 0
    await store._save(session_id, session)
    _grant(keycloak, error=True)

    assert (await client.get("/api/auth/me")).status_code == 401
    assert await store.get_session(session_id) is None


async def test_logout_ends_session_and_returns_end_session_url(
    client: AsyncClient, store: SessionStore, keycloak: _FakeKeycloak
) -> None:
    await _login(client, keycloak, ["user"])
    session_id = client.cookies["toolmesh_session"]
    _grant(keycloak)

    response = await client.post("/api/auth/logout")

    query = parse_qs(urlparse(response.json()["redirectUrl"]).query)
    assert query["id_token_hint"] == ["idt"]
    assert query["post_logout_redirect_uri"] == ["http://spa.test"]
    assert keycloak.calls == [("logout", {"refresh_token": "r1"})]
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


async def test_token_returns_keycloak_tokens(client: AsyncClient, keycloak: _FakeKeycloak) -> None:
    _grant(keycloak, _token_response(["user"]))

    response = await client.post("/api/auth/token", json={"username": "user", "password": "user"})

    assert response.status_code == 200
    assert response.json()["refresh_token"] == "r1"
    assert keycloak.calls == [("token", {"grant_type": "password", "username": "user", "password": "user"})]


async def test_token_with_bad_credentials_is_401(client: AsyncClient, keycloak: _FakeKeycloak) -> None:
    _grant(keycloak, error=True)

    response = await client.post("/api/auth/token", json={"username": "user", "password": "nope"})

    assert response.status_code == 401


async def test_refresh_returns_new_tokens(client: AsyncClient, keycloak: _FakeKeycloak) -> None:
    _grant(keycloak, _token_response(["user"]))

    response = await client.post("/api/auth/refresh", json={"refresh_token": "r0"})

    assert response.status_code == 200
    assert keycloak.calls == [("refresh", {"refresh_token": "r0"})]


def test_public_url_builds_the_issuer_and_internal_url_the_jwks() -> None:
    settings = Settings(keycloak_url="http://keycloak:8080", keycloak_public_url="https://sso.test", keycloak_realm="r")

    assert settings.oidc_issuer == "https://sso.test/realms/r"
    assert settings.auth_url == "https://sso.test/realms/r/protocol/openid-connect/auth"
    assert settings.jwks_url == "http://keycloak:8080/realms/r/protocol/openid-connect/certs"
