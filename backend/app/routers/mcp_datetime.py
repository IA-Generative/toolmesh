from typing import Annotated, Literal

import httpx2
from fastapi import APIRouter, Depends, HTTPException, status
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel

from app.auth import CurrentUser
from app.auth.exchange import exchange_token
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/mock", tags=["mock"])


class McpDatetimeResult(BaseModel):
    exchanged_token_audience: str
    tool: str
    result: str


@router.get("/mcp-datetime")
async def call_mcp_datetime(
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    date: str = "2026-10-13",
    kind: Literal["week", "month", "quarter", "year"] = "quarter",
) -> McpDatetimeResult:
    """Mock tool invocation: exchange the caller's token, then call `period_bounds` on the MCP server with it."""
    assert user.token is not None
    token = await exchange_token(settings, user.token, settings.mcp_datetime_audience)
    http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"})
    try:
        async with (
            http_client,
            Client(streamable_http_client(settings.mcp_datetime_url, http_client=http_client)) as mcp,
        ):
            result = await mcp.call_tool("period_bounds", {"date_iso": date, "kind": kind})
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"MCP call failed: {exc}") from exc
    text = "".join(getattr(part, "text", "") for part in result.content)
    return McpDatetimeResult(exchanged_token_audience=settings.mcp_datetime_audience, tool="period_bounds", result=text)
