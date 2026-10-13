from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.auth.models import User
from app.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True)


def get_jwks_client(settings: Annotated[Settings, Depends(get_settings)]) -> PyJWKClient:
    return _jwks_client(settings.jwks_url)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    jwks_client: Annotated[PyJWKClient, Depends(get_jwks_client)],
) -> User:
    """Validate the bearer token (signature, issuer, audience, expiry) and return the caller."""
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized(f"Invalid token: {exc}") from exc

    return User(
        sub=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
        roles=claims.get("realm_access", {}).get("roles", []),
        token=credentials.credentials,
    )


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: str):
    async def checker(user: CurrentUser) -> User:
        if role not in user.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{role}' required")
        return user

    return Depends(checker)
