from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import CurrentUser
from app.auth.exchange import exchange_token
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/mock", tags=["mock"])


class DownstreamResult(BaseModel):
    exchanged_token_audience: str
    downstream_response: dict


@router.get("/downstream")
async def call_downstream(
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DownstreamResult:
    """Mock tool invocation: exchange the caller's token, then call the downstream service with it."""
    assert user.token is not None
    token = await exchange_token(settings, user.token, settings.downstream_audience)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.downstream_url}/whoami", headers={"Authorization": f"Bearer {token}"}
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Downstream unreachable: {exc}") from exc
    if response.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Downstream returned {response.status_code}: {response.text}")
    return DownstreamResult(exchanged_token_audience=settings.downstream_audience, downstream_response=response.json())
