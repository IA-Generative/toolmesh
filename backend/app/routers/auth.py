import base64
import hashlib
import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from jwt import PyJWKClient

from app.auth import CurrentUser, User
from app.auth.dependencies import decode_token, get_jwks_client
from app.auth.session import PendingAuth, SessionStore, get_session_store
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_RATE_LIMIT = 20
LOGIN_RATE_WINDOW_SECONDS = 60


def _is_safe_internal_path(path: str) -> bool:
    """Only "/foo/bar" may follow a login; "//evil.com" or "https://evil.com" would be an open redirect."""
    return path.startswith("/") and not path.startswith("//") and "\\" not in path


def _build_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


@router.get("/login", summary="Redirect the browser to Keycloak's login page")
async def login(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    redirect: str = "/",
) -> RedirectResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not await store.check_rate_limit(f"login:{client_ip}", LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW_SECONDS):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")

    verifier, challenge = _build_pkce_pair()
    state = secrets.token_urlsafe(32)
    next_path = redirect if _is_safe_internal_path(redirect) else "/"
    await store.save_pending(state, PendingAuth(code_verifier=verifier, next_path=next_path))
    query = urlencode(
        {
            "client_id": settings.bff_client_id,
            "response_type": "code",
            "redirect_uri": settings.callback_url,
            "scope": "openid profile email",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"{settings.auth_url}?{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/callback", summary="Exchange the Keycloak authorization code for a session")
async def callback(
    code: str,
    state: str,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    jwks_client: Annotated[PyJWKClient, Depends(get_jwks_client)],
) -> RedirectResponse:
    pending = await store.pop_pending(state)
    if pending is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired login attempt")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.bff_client_id,
                    "client_secret": settings.bff_client_secret,
                    "code": code,
                    "redirect_uri": settings.callback_url,
                    "code_verifier": pending.code_verifier,
                },
            )
        response.raise_for_status()
        token_response = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Login failed") from exc
    # Refuse to open a session for a token we would not accept as a bearer.
    decode_token(token_response["access_token"], settings, jwks_client)

    session_id = await store.create_session(token_response)
    redirect = RedirectResponse(
        f"{settings.frontend_url}{pending.next_path}", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
    redirect.set_cookie(
        settings.session_cookie_name,
        session_id,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
    )
    return redirect


@router.post("/logout", summary="End the BFF session and the Keycloak SSO session")
async def logout(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> dict[str, str]:
    """Returns the Keycloak end-session URL; the SPA navigates to it to finish the SSO logout."""
    id_token: str | None = None
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        session = await store.get_session(session_id)
        if session is not None:
            id_token = session.id_token
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        settings.logout_url,
                        data={
                            "client_id": settings.bff_client_id,
                            "client_secret": settings.bff_client_secret,
                            "refresh_token": session.refresh_token,
                        },
                    )
            except httpx.HTTPError:
                pass  # The local session is dropped regardless; Keycloak's copy expires on its own.
        await store.delete_session(session_id)
    response.delete_cookie(settings.session_cookie_name)
    query = {"client_id": settings.bff_client_id, "post_logout_redirect_uri": settings.frontend_url}
    if id_token:
        query["id_token_hint"] = id_token
    return {"redirectUrl": f"{settings.logout_url}?{urlencode(query)}"}


@router.get("/me", summary="The authenticated caller's profile")
async def me(user: CurrentUser) -> User:
    return user
