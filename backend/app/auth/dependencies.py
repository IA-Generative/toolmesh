from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.auth.models import User
from app.auth.session import SessionStore, get_session_store
from app.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True)


def get_jwks_client(settings: Annotated[Settings, Depends(get_settings)]) -> PyJWKClient:
    return _jwks_client(settings.jwks_url)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def decode_token(token: str, settings: Settings, jwks_client: PyJWKClient) -> User:
    """Validate an access token (signature, issuer, audience, expiry) and return its owner."""
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.audience,
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
        token=token,
    )


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    jwks_client: Annotated[PyJWKClient, Depends(get_jwks_client)],
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> User:
    """The caller: a bearer token (CLI, agents) or the BFF session cookie (browser)."""
    if credentials is not None:
        return decode_token(credentials.credentials, settings, jwks_client)
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        session = await store.get_session(session_id)
        if session is not None:
            return decode_token(session.access_token, settings, jwks_client)
    raise _unauthorized("Not authenticated")


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: str):
    async def checker(user: CurrentUser) -> User:
        if role not in user.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Role '{role}' required")
        return user

    return Depends(checker)
