"""Call a registered tool on behalf of a user: `tools/call` on an MCP server, an HTTP request for an API."""

import asyncio
import json
import re
import time
from typing import Any
from urllib.parse import quote

import httpx
import httpx2
from fastapi import status
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from app.auth.exchange import exchange_token
from app.config import Settings
from app.db.models import Source, Tool
from app.discovery import DiscoveryError, check_url

BODY_METHODS = {"POST", "PUT", "PATCH"}
PATH_PARAM = re.compile(r"\{([^{}]+)\}")


class ExecutionError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(message)
        self.status_code = status_code


async def _auth_headers(source: Source, user_token: str | None, settings: Settings) -> dict[str, str]:
    if source.auth_mode != "token_exchange":
        return {}
    if not user_token or not source.audience:
        raise ExecutionError("Token exchange needs a user token and an audience", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return {"Authorization": f"Bearer {await exchange_token(settings, user_token, source.audience)}"}


async def _check(url: str, settings: Settings) -> None:
    try:
        await check_url(url, settings)
    except DiscoveryError as exc:
        raise ExecutionError(str(exc), exc.status_code) from exc


def build_request(tool: Tool, base_url: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """URL, query and JSON body of an API call: `{name}` in the path are filled from the arguments, `body` is the
    JSON body and every other argument is a query parameter."""
    path = tool.path or ""
    used: set[str] = set()

    def fill(match: re.Match) -> str:
        name = match.group(1)
        if arguments.get(name) is None:
            raise ExecutionError(f"Missing path parameter: {name}", status.HTTP_422_UNPROCESSABLE_CONTENT)
        used.add(name)
        return quote(str(arguments[name]), safe="")

    url = base_url.rstrip("/") + PATH_PARAM.sub(fill, path)
    query = {k: v for k, v in arguments.items() if k not in used and k != "body" and v is not None}
    body = arguments.get("body") if (tool.method or "GET").upper() in BODY_METHODS else None
    return {"url": url, "params": query, "json": body}


async def _call_api(
    source: Source,
    tool: Tool,
    arguments: dict[str, Any],
    headers: dict[str, str],
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    request = build_request(tool, source.url or "", arguments)
    await _check(request["url"], settings)
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.execution_timeout_seconds, follow_redirects=False)
    try:
        # Redirects are not followed: the target would escape the address check above.
        async with client.stream(
            (tool.method or "GET").upper(),
            request["url"],
            params=request["params"],
            json=request["json"],
            headers=headers,
        ) as response:
            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                if len(body) > settings.execution_max_response_bytes:
                    break
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            truncated = len(body) > settings.execution_max_response_bytes
            body = body[: settings.execution_max_response_bytes]
            status_code = response.status_code
    except httpx.HTTPError as exc:
        raise ExecutionError(f"The API is unreachable: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    text = body.decode("utf-8", errors="replace")
    content: Any = text
    if "json" in content_type and not truncated:
        try:
            content = json.loads(text)
        except ValueError:
            pass
    return {
        "ok": status_code < 400,
        "status": status_code,
        "content_type": content_type,
        "content": content,
        "truncated": truncated,
    }


async def _call_mcp(
    source: Source, tool: Tool, arguments: dict[str, Any], headers: dict[str, str], settings: Settings
) -> dict[str, Any]:
    await _check(source.url or "", settings)
    try:
        async with asyncio.timeout(settings.execution_timeout_seconds):
            http_client = httpx2.AsyncClient(headers=headers, follow_redirects=False)
            async with http_client, Client(streamable_http_client(source.url, http_client=http_client)) as mcp:
                result = await mcp.call_tool(tool.name, arguments)
    except TimeoutError as exc:
        raise ExecutionError("The MCP server did not answer in time") from exc
    except Exception as exc:
        raise ExecutionError(f"The MCP call failed: {exc}") from exc
    text = "".join(getattr(part, "text", "") for part in result.content)
    content: Any = result.structured_content
    if content is None:
        try:
            content = json.loads(text)
        except ValueError:
            content = text
    return {"ok": not result.is_error, "status": None, "content_type": None, "content": content, "truncated": False}


async def execute(
    source: Source, tool: Tool, arguments: dict[str, Any], user_token: str | None, settings: Settings
) -> dict[str, Any]:
    """Run `tool` with `arguments`; the result has `ok`, `content` and, for an API, the HTTP `status`."""
    if source.type == "skill":
        raise ExecutionError(
            "Skills cannot be run yet: no model provider is configured", status.HTTP_501_NOT_IMPLEMENTED
        )
    started = time.perf_counter()
    headers = await _auth_headers(source, user_token, settings)
    if source.type == "api":
        result = await _call_api(source, tool, arguments, headers, settings)
    else:
        result = await _call_mcp(source, tool, arguments, headers, settings)
    return result | {"duration_ms": round((time.perf_counter() - started) * 1000)}
