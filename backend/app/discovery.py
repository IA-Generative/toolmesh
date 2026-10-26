"""Find the tools a source exposes: `tools/list` for an MCP server, the OpenAPI spec for an API."""

import asyncio
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx
import httpx2
import yaml
from fastapi import status
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from app.auth.exchange import exchange_token
from app.config import Settings
from app.schemas import SourceIn, ToolIn

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
MAX_OPERATIONS = 500
MAX_REF_DEPTH = 8


class DiscoveryError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(message)
        self.status_code = status_code


# --- Address guard -------------------------------------------------------------------------------------------------


async def check_url(url: str, settings: Settings) -> None:
    """Refuse URLs that would make the backend call itself or its neighbours (SSRF)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise DiscoveryError(f"Invalid URL: {url}", status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DiscoveryError(f"Cannot resolve {parts.hostname}", status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        always_blocked = ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved
        local = ip.is_loopback or ip.is_private
        if always_blocked or (local and not settings.discovery_allow_private_hosts):
            raise DiscoveryError(f"Address not allowed: {parts.hostname}", status.HTTP_422_UNPROCESSABLE_CONTENT)


async def _auth_headers(source: SourceIn, subject_token: str | None, settings: Settings) -> dict[str, str]:
    if source.auth_mode != "token_exchange":
        return {}
    if not subject_token or not source.audience:
        raise DiscoveryError("Token exchange needs a user token and an audience", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return {"Authorization": f"Bearer {await exchange_token(settings, subject_token, source.audience)}"}


# --- Glob filter on "METHOD /path" ---------------------------------------------------------------------------------


def matches(pattern: str, operation: str) -> bool:
    """`*` matches any characters (`/` included), `?` one character; case-insensitive."""
    regex = re.escape(pattern.upper()).replace(r"\*", ".*").replace(r"\?", ".")
    return re.fullmatch(regex, operation.upper()) is not None


def is_exposed(operation: str, include: list[str], exclude: list[str]) -> bool:
    included = not include or any(matches(p, operation) for p in include)
    return included and not any(matches(p, operation) for p in exclude)


# --- OpenAPI -------------------------------------------------------------------------------------------------------


def _resolve(node: Any, spec: dict, depth: int = 0) -> Any:
    """Inline local `$ref`s; deeper or circular references are left as an empty schema."""
    if isinstance(node, list):
        return [_resolve(n, spec, depth) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        ref = node["$ref"]
        if depth >= MAX_REF_DEPTH or not isinstance(ref, str) or not ref.startswith("#/"):
            return {}
        target: Any = spec
        for part in ref[2:].split("/"):
            target = target.get(part.replace("~1", "/").replace("~0", "~")) if isinstance(target, dict) else None
        return _resolve(target, spec, depth + 1) if target is not None else {}
    return {k: _resolve(v, spec, depth) for k, v in node.items()}


def _slug(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_.:-]", "_", text)).strip("_")[:100]


def _input_schema(operation: dict, path_item: dict, spec: dict) -> dict:
    parameters = {}
    for raw in [*path_item.get("parameters", []), *operation.get("parameters", [])]:
        p = _resolve(raw, spec)
        if p.get("in") in ("path", "query") and p.get("name"):
            parameters[(p["in"], p["name"])] = p  # an operation parameter overrides the path-level one
    properties: dict[str, Any] = {}
    required: list[str] = []
    for (location, name), p in parameters.items():
        schema = dict(p.get("schema") or {})
        if p.get("description"):
            schema.setdefault("description", p["description"])
        properties[name] = schema
        if p.get("required") or location == "path":
            required.append(name)
    body = _resolve(operation.get("requestBody") or {}, spec)
    json_body = (body.get("content") or {}).get("application/json", {}).get("schema")
    if json_body:
        properties["body"] = json_body
        if body.get("required"):
            required.append("body")
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def spec_version(spec: dict) -> str | None:
    version = (spec.get("info") or {}).get("version")
    return str(version)[:100] if version not in (None, "") else None


def tools_from_spec(spec: dict, include: list[str], exclude: list[str]) -> list[ToolIn]:
    """One tool per operation of the OpenAPI document that passes the include/exclude patterns."""
    tools: list[ToolIn] = []
    used: set[str] = set()
    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict) or not is_exposed(f"{method.upper()} {path}", include, exclude):
                continue
            base = _slug(operation.get("operationId") or f"{method}_{path}") or method
            name, n = base, 2
            while name in used:
                name, n = f"{base[:95]}_{n}", n + 1
            used.add(name)
            tools.append(
                ToolIn(
                    name=name,
                    description=(operation.get("summary") or operation.get("description") or "").strip(),
                    tags=[str(t) for t in operation.get("tags", [])],
                    method=method.upper(),
                    path=path,
                    input_schema=_input_schema(operation, path_item, spec),
                )
            )
            if len(tools) >= MAX_OPERATIONS:
                return tools
    return tools


async def fetch_spec(url: str, headers: dict[str, str], settings: Settings) -> dict:
    await check_url(url, settings)
    try:
        # Redirects are not followed: the target would escape the address check above.
        async with (
            httpx.AsyncClient(timeout=settings.discovery_timeout_seconds, follow_redirects=False) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            if response.status_code != 200:
                raise DiscoveryError(f"The OpenAPI document returned {response.status_code}")
            body = b""
            async for chunk in response.aiter_bytes():
                body += chunk
                if len(body) > settings.discovery_max_spec_bytes:
                    raise DiscoveryError("The OpenAPI document is too large")
    except httpx.HTTPError as exc:
        raise DiscoveryError(f"Cannot fetch the OpenAPI document: {exc}") from exc
    try:
        spec = json.loads(body)
    except ValueError:
        try:
            spec = yaml.safe_load(body)
        except yaml.YAMLError as exc:
            raise DiscoveryError("The OpenAPI document is neither JSON nor YAML") from exc
    if not isinstance(spec, dict) or "paths" not in spec:
        raise DiscoveryError("Not an OpenAPI document (no `paths`)")
    return spec


async def discover_api(source: SourceIn, subject_token: str | None, settings: Settings):
    headers = await _auth_headers(source, subject_token, settings)
    spec = await fetch_spec(source.openapi_url or "", headers, settings)
    return tools_from_spec(spec, source.endpoint_include, source.endpoint_exclude), spec_version(spec)


# --- MCP -----------------------------------------------------------------------------------------------------------


async def discover_mcp(source: SourceIn, subject_token: str | None, settings: Settings):
    await check_url(source.url or "", settings)
    headers = await _auth_headers(source, subject_token, settings)
    tools: list[ToolIn] = []
    version: str | None = None
    try:
        async with asyncio.timeout(settings.discovery_timeout_seconds):
            http_client = httpx2.AsyncClient(headers=headers, follow_redirects=False)
            async with http_client, Client(streamable_http_client(source.url, http_client=http_client)) as mcp:
                server_version = getattr(getattr(mcp, "server_info", None), "version", None)
                version = str(server_version)[:100] if server_version else None
                cursor = None
                while True:
                    page = await mcp.list_tools(cursor=cursor)
                    for t in page.tools:
                        if name := _slug(t.name):
                            tools.append(
                                ToolIn(name=name, description=t.description or "", input_schema=t.input_schema)
                            )
                    cursor = page.next_cursor
                    if not cursor or len(tools) >= MAX_OPERATIONS:
                        break
    except TimeoutError as exc:
        raise DiscoveryError("The MCP server did not answer in time") from exc
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(f"Cannot list the tools of the MCP server: {exc}") from exc
    return tools, version


async def discover(source: SourceIn, subject_token: str | None, settings: Settings):
    if source.type == "mcp":
        tools, version = await discover_mcp(source, subject_token, settings)
    elif source.type == "api":
        tools, version = await discover_api(source, subject_token, settings)
    else:
        raise DiscoveryError("A skill has nothing to discover", status.HTTP_422_UNPROCESSABLE_CONTENT)
    if not tools:
        raise DiscoveryError("No tool found", status.HTTP_422_UNPROCESSABLE_CONTENT)
    return tools, version
