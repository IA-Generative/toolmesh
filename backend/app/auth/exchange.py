from fastapi import HTTPException, status
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError

ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


async def exchange_token(keycloak_openid: KeycloakOpenID, subject_token: str, audience: str) -> str:
    """Swap the caller's token for one scoped to `audience` (RFC 8693), keeping the user's identity."""
    try:
        response = await keycloak_openid.a_exchange_token(
            subject_token, audience=audience, requested_token_type=ACCESS_TOKEN_TYPE
        )
    except KeycloakError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Token exchange failed: {exc}") from exc
    return response["access_token"]
