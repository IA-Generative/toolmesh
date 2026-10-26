import httpx
from fastapi import HTTPException, status

from app.config import Settings

ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"


async def exchange_token(settings: Settings, subject_token: str, audience: str) -> str:
    """Swap the caller's token for one scoped to `audience` (RFC 8693), keeping the user's identity.

    The request is built here rather than through python-keycloak, whose `exchange_token` always sends an empty
    `requested_subject` (and no `subject_token_type`): Keycloak rejects both for a standard token exchange.
    """
    url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"
    data = {
        "grant_type": TOKEN_EXCHANGE_GRANT,
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "subject_token": subject_token,
        "subject_token_type": ACCESS_TOKEN_TYPE,
        "requested_token_type": ACCESS_TOKEN_TYPE,
        "audience": audience,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, data=data)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Token exchange failed: Keycloak unreachable ({exc})"
        ) from exc
    if response.status_code != 200:
        try:
            reason = response.json().get("error_description") or response.json().get("error")
        except ValueError:
            reason = response.text
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Token exchange failed: {reason} ({response.status_code})")
    return response.json()["access_token"]
