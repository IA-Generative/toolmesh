from functools import lru_cache

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

    @property
    def jwks_url(self) -> str:
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"

    @property
    def token_url(self) -> str:
        return self.oidc_token_url or f"{self.oidc_issuer}/protocol/openid-connect/token"


@lru_cache
def get_settings() -> Settings:
    return Settings()
