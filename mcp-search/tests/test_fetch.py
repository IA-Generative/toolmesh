import httpx
import pytest

from app.config import Settings
from app.fetch import check_url, fetch_page, html_to_text

PUBLIC = "http://93.184.216.34"  # a public address: literals need no DNS lookup
SETTINGS = Settings()

HTML = """<html><head><title> Hello </title><style>p {color: red}</style></head>
<body><script>alert(1)</script><h1>Title</h1><p>First   paragraph.</p><p>Second &amp; last.</p>
<noscript>enable js</noscript></body></html>"""


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def page(body: str = HTML, content_type: str = "text/html; charset=utf-8", status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": content_type})


def test_html_is_reduced_to_readable_text() -> None:
    title, text = html_to_text(HTML)

    assert title == "Hello"
    assert text == "Title\n\nFirst paragraph.\n\nSecond & last."


async def test_fetch_returns_title_and_text() -> None:
    result = await fetch_page(SETTINGS, f"{PUBLIC}/x", client=client_for(lambda _: page()))

    assert result == {
        "url": f"{PUBLIC}/x",
        "title": "Hello",
        "text": "Title\n\nFirst paragraph.\n\nSecond & last.",
        "truncated": False,
    }


async def test_fetch_truncates_long_pages() -> None:
    result = await fetch_page(
        SETTINGS, PUBLIC, max_chars=500, client=client_for(lambda _: page("<p>" + "a" * 900 + "</p>"))
    )

    assert (len(result["text"]), result["truncated"]) == (500, True)


async def test_plain_text_is_returned_as_is() -> None:
    result = await fetch_page(SETTINGS, PUBLIC, client=client_for(lambda _: page(" raw <b> ", "text/plain")))

    assert result["text"] == "raw <b>"


@pytest.mark.parametrize(
    ("response", "message"),
    [(page(status=404), "404"), (page("%PDF", "application/pdf"), "Not a text page")],
    ids=["not-found", "binary"],
)
async def test_fetch_rejects_unusable_responses(response: httpx.Response, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        await fetch_page(SETTINGS, PUBLIC, client=client_for(lambda _: response))


async def test_redirects_are_followed_and_checked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/end"})
        return page("<p>arrived</p>")

    result = await fetch_page(SETTINGS, f"{PUBLIC}/start", client=client_for(handler))
    assert (result["url"], result["text"]) == (f"{PUBLIC}/end", "arrived")

    def to_internal(_: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    with pytest.raises(ValueError, match="not allowed"):
        await fetch_page(SETTINGS, PUBLIC, client=client_for(to_internal))

    with pytest.raises(RuntimeError, match="Too many redirects"):
        await fetch_page(
            SETTINGS, PUBLIC, client=client_for(lambda _: httpx.Response(302, headers={"location": "/again"}))
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://x/",
    ],
    ids=["loopback", "private", "metadata", "ipv6-loopback", "file", "ftp"],
)
async def test_internal_and_non_http_urls_are_refused(url: str) -> None:
    with pytest.raises(ValueError):
        await check_url(url, SETTINGS)


async def test_private_hosts_pass_only_when_allowed_and_metadata_never() -> None:
    allowed = Settings(allow_private_hosts=True)

    await check_url("http://127.0.0.1:8080/", allowed)
    with pytest.raises(ValueError):
        await check_url("http://169.254.169.254/", allowed)
