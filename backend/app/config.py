from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TOOLMESH_", env_file=".env", extra="ignore")

    # OIDC provider (Keycloak). The issuer must match the `iss` claim exactly.
    oidc_issuer: str = "http://localhost:8080/realms/toolmesh"
    # Optional: fetch JWKS from another URL than <issuer>/protocol/openid-connect/certs
    # (useful when the backend reaches Keycloak through a different hostname, e.g. in docker).
    oidc_jwks_url: str | None = None
    oidc_token_url: str | None = None
    oidc_audience: str = "toolmesh"

    # Confidential client used for token exchange (RFC 8693) towards downstream services.
    oidc_client_id: str = "toolmesh"
    oidc_client_secret: str = "toolmesh-secret"
    downstream_url: str = "http://localhost:8020"
    downstream_audience: str = "downstream-service"
    mcp_datetime_url: str = "http://localhost:8030/mcp"
    mcp_datetime_audience: str = "mcp-datetime"

    # BFF (browser login): confidential client running the authorization code flow with PKCE.
    # The browser only ever holds an opaque session cookie; tokens stay in Redis.
    bff_client_id: str = "toolmesh-bff"
    bff_client_secret: str = "toolmesh-bff-secret"
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
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"

    @property
    def token_url(self) -> str:
        return self.oidc_token_url or f"{self.oidc_issuer}/protocol/openid-connect/token"


@lru_cache
def get_settings() -> Settings:
    return Settings()
