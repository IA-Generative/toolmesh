import httpx

from app.config import Settings

BATCH = 64


class EmbeddingError(Exception):
    pass


async def embed(settings: Settings, texts: list[str], client: httpx.AsyncClient | None = None) -> list[list[float]]:
    """Dense vectors of `texts` from an OpenAI-compatible `/embeddings` API, in the order of `texts`."""
    if not (settings.embeddings_url and settings.embeddings_model):
        raise EmbeddingError("Embeddings are not configured")
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
