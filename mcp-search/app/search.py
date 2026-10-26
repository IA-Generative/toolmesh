from typing import Literal

import httpx

from app.config import Settings

TimeRange = Literal["day", "week", "month", "year"]
Category = Literal["general", "news", "science", "it", "images"]


async def search(
    settings: Settings,
    query: str,
    max_results: int = 5,
    language: str = "fr",
    time_range: TimeRange | None = None,
    category: Category = "general",
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Query SearXNG and return the first `max_results` distinct results."""
    params = {"q": query, "format": "json", "language": language, "categories": category}
    if time_range:
        params["time_range"] = time_range
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.timeout_seconds)
    try:
        response = await client.get(f"{settings.searxng_url}/search", params=params)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"SearXNG is unreachable: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    if response.status_code == 403:
        raise RuntimeError("SearXNG refused the request: enable the `json` format in `search.formats` of its settings")
    if response.status_code != 200:
        raise RuntimeError(f"SearXNG answered {response.status_code}")

    results, seen = [], set()
    for item in response.json().get("results", []):
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        results.append(
            {
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("content", ""),
                "engine": item.get("engine", ""),
                "published": item.get("publishedDate"),
            }
        )
        if len(results) >= max_results:
            break
    return results
