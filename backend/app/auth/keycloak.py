from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from keycloak import KeycloakOpenID

from app.config import Settings, get_settings


@lru_cache
def _keycloak_openid(server_url: str, realm: str, client_id: str, client_secret: str) -> KeycloakOpenID:
    return KeycloakOpenID(server_url=server_url, realm_name=realm, client_id=client_id, client_secret_key=client_secret)


def get_keycloak_openid(settings: Annotated[Settings, Depends(get_settings)]) -> KeycloakOpenID:
    """Client for the backend-to-Keycloak calls (token, refresh, logout, token exchange)."""
    return _keycloak_openid(
        settings.keycloak_url, settings.keycloak_realm, settings.keycloak_client_id, settings.keycloak_client_secret
    )
