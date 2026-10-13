import httpx
from fastapi import HTTPException, status

from app.config import Settings

TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


async def exchange_token(settings: Settings, subject_token: str, audience: str) -> str:
    """Swap the caller's token for one scoped to `audience` (RFC 8693), keeping the user's identity."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.token_url,
            data={
                "grant_type": TOKEN_EXCHANGE_GRANT,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "subject_token": subject_token,
                "subject_token_type": ACCESS_TOKEN_TYPE,
                "requested_token_type": ACCESS_TOKEN_TYPE,
                "audience": audience,
            },
        )
    if response.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Token exchange failed: {response.text}")
    return response.json()["access_token"]
