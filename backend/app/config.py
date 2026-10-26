from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TOOLMESH_", env_file=".env", extra="ignore")

    # Keycloak. `keycloak_url` is how the backend reaches it (e.g. the Docker service name); the browser-facing
    # `keycloak_public_url` defaults to it. The issuer, built from the public URL, must match the tokens' `iss` claim.
    keycloak_url: str = "http://localhost:8080"
    keycloak_public_url: str | None = None
    keycloak_realm: str = "toolmesh"
    # One confidential client for the browser login (code + PKCE), the password/refresh grants and token exchange.
    keycloak_client_id: str = "toolmesh"
    keycloak_client_secret: str = "toolmesh-secret"
    # Audience to enforce on incoming tokens; unset means `aud` is not checked.
    oidc_audience: str | None = None

    # Registry of sources and tools.
    database_url: str = "postgresql+asyncpg://toolmesh:toolmesh@localhost:5432/toolmesh"
    # Apply the Alembic migrations when the app starts.
    auto_migrate: bool = True

    # Discovery: the backend fetches OpenAPI specs and lists MCP tools at addresses given by users.
    # Loopback/private addresses are refused unless this is set (link-local ones, e.g. cloud metadata, never pass).
    discovery_allow_private_hosts: bool = False
    discovery_timeout_seconds: float = 15
    discovery_max_spec_bytes: int = 5_000_000

    # Execution: calls to the registered services made on behalf of a user (same address rules as the discovery).
    execution_timeout_seconds: float = 30
    execution_max_response_bytes: int = 1_000_000

    # Search of tools (hybrid: sparse keywords + dense embeddings, fused by Qdrant). Without `qdrant_url` the search
    # falls back to a plain keyword match on the registry. Without `embeddings_url` only the keywords are indexed.
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "toolmesh-tools"
    # OpenAI-compatible embeddings API: POST `<embeddings_url>/embeddings`.
    embeddings_url: str | None = None
    embeddings_api_key: str | None = None
    embeddings_model: str | None = None
    # Size of the vectors; probed with a first call when unset.
    embeddings_dimensions: int | None = None

    # BFF (browser login): the authorization code flow with PKCE.
    # The browser only ever holds an opaque session cookie; tokens stay in Redis.
    redis_url: str = "redis://localhost:6379/0"
    # Origin of the SPA: target of the post-login redirect and the only CORS origin allowed.
    frontend_url: str = "http://localhost:3000"
    # Origin the browser uses to reach this backend; builds the redirect_uri registered in Keycloak.
    backend_public_url: str = "http://localhost:8010"
    session_cookie_name: str = "toolmesh_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_ttl_seconds: int = 28800

    @property
    def public_url(self) -> str:
        return self.keycloak_public_url or self.keycloak_url

    @property
    def oidc_issuer(self) -> str:
        return f"{self.public_url}/realms/{self.keycloak_realm}"

    @property
    def callback_url(self) -> str:
        return f"{self.backend_public_url}/api/auth/callback"

    @property
    def auth_url(self) -> str:
        return f"{self.oidc_issuer}/protocol/openid-connect/auth"

    @property
    def logout_url(self) -> str:
        return f"{self.oidc_issuer}/protocol/openid-connect/logout"

    @property
    def jwks_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
