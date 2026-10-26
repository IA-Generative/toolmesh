from typing import Literal

import httpx

from app.config import Settings

BATCH = 64


class EmbeddingError(Exception):
    pass


async def _request(settings: Settings, texts: list[str], client: httpx.AsyncClient | None = None) -> list[list[float]]:
    """POST the texts to the OpenAI-compatible `/embeddings` API; vectors in the order of `texts`."""
    headers = {"Authorization": f"Bearer {settings.embeddings_api_key}"} if settings.embeddings_api_key else {}
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30)
    vectors: list[list[float]] = []
    try:
        for start in range(0, len(texts), BATCH):
            body: dict = {"model": settings.embeddings_model, "input": texts[start : start + BATCH]}
            if settings.embeddings_dimensions:
                body["dimensions"] = settings.embeddings_dimensions
            try:
                response = await client.post(
                    f"{settings.embeddings_url.rstrip('/')}/embeddings", json=body, headers=headers
                )
            except httpx.HTTPError as exc:
                raise EmbeddingError(f"The embeddings API is unreachable: {exc}") from exc
            if response.status_code != 200:
                raise EmbeddingError(f"The embeddings API answered {response.status_code}")
            data = sorted(response.json().get("data", []), key=lambda d: d["index"])
            if len(data) != len(body["input"]):
                raise EmbeddingError("The embeddings API returned an unexpected number of vectors")
            vectors.extend(d["embedding"] for d in data)
    finally:
        if owns_client:
            await client.aclose()
    return vectors


async def embed(
    settings: Settings,
    texts: list[str],
    kind: Literal["query", "document"] = "document",
    client: httpx.AsyncClient | None = None,
) -> list[list[float]]:
    """Dense vectors of `texts`, in order. Models trained with instructions want a prefix that differs between what is
    searched (`query`) and what is searched in (`document`): `embeddings_query_prefix` and
    `embeddings_document_prefix`."""
    if not (settings.embeddings_url and settings.embeddings_model):
        raise EmbeddingError("Embeddings are not configured")
    prefix = settings.embeddings_query_prefix if kind == "query" else settings.embeddings_document_prefix
    return await _request(settings, [prefix + t for t in texts], client)
