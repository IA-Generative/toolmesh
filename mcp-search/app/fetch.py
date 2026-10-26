import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from app.config import Settings

MAX_REDIRECTS = 3
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
SKIPPED_TAGS = {"script", "style", "noscript", "svg", "template"}
BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "li",
    "tr",
    "section",
    "article",
    "header",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}


async def check_url(url: str, settings: Settings) -> None:
    """Refuse URLs that would make the server call itself or its neighbours (SSRF)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"Invalid URL: {url}")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"Cannot resolve {parts.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        always_blocked = ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved
        if always_blocked or ((ip.is_loopback or ip.is_private) and not settings.allow_private_hosts):
            raise ValueError(f"Address not allowed: {parts.hostname}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "title":
            self._in_title = True
        if tag in SKIPPED_TAGS:
            self._skip += 1
        if tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in SKIPPED_TAGS and self._skip:
            self._skip -= 1
        if tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip:
            self._chunks.append(data)

    def text(self) -> str:
        text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self._chunks))
        return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def html_to_text(html: str) -> tuple[str, str]:
    """(title, readable text) of an HTML document: scripts and styles dropped, blocks separated by newlines."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.title.strip(), parser.text()


async def fetch_page(
    settings: Settings, url: str, max_chars: int = 8000, client: httpx.AsyncClient | None = None
) -> dict:
    """Download a page and return its title and text, truncated to `max_chars`."""
    max_chars = max(500, min(max_chars, 50_000))
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.timeout_seconds, follow_redirects=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            await check_url(url, settings)  # every hop is checked, so a redirect cannot reach an internal address
            async with client.stream("GET", url, headers={"User-Agent": "toolmesh-mcp-search"}) as response:
                if response.is_redirect and (location := response.headers.get("location")):
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise RuntimeError(f"The page answered {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in TEXT_TYPES:
                    raise RuntimeError(f"Not a text page ({content_type or 'unknown type'})")
                body = b""
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > settings.max_fetch_bytes:
                        break
                html = body.decode(response.encoding or "utf-8", errors="replace")
            break
        else:
            raise RuntimeError("Too many redirects")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Cannot fetch the page: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    if content_type == "text/plain":
        title, text = "", html.strip()
    else:
        title, text = html_to_text(html)
    return {"url": url, "title": title, "text": text[:max_chars], "truncated": len(text) > max_chars}
