"""Bearer-token check in front of the MCP endpoint (signature, issuer, audience, expiry via Keycloak JWKS)."""

import jwt
from jwt import PyJWKClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_DATETIME_", extra="ignore")

    # Disable only for local experiments without Keycloak.
    auth_enabled: bool = True
    oidc_issuer: str = "http://localhost:8080/realms/toolmesh"
    oidc_jwks_url: str | None = None
    oidc_audience: str = "mcp-datetime"

    @property
    def jwks_url(self) -> str:
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, settings: AuthSettings, jwks_client: PyJWKClient | None = None) -> None:
        self.app = app
        self.settings = settings
        self.jwks_client = jwks_client or PyJWKClient(settings.jwks_url)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        auth = headers.get(b"authorization", b"").decode()
        if not auth.lower().startswith("bearer "):
            await self._reject("Missing bearer token", scope, receive, send)
            return
        token = auth[7:]
        try:
            key = self.jwks_client.get_signing_key_from_jwt(token)
            jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            await self._reject(f"Invalid token: {exc}", scope, receive, send)
            return
        await self.app(scope, receive, send)

    async def _reject(self, detail: str, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"detail": detail}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        await response(scope, receive, send)
