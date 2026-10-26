"""The Qdrant collection holding one point per tool: a keyword vector, an optional dense vector and the payload
used for filtering. Search fuses both rankings with reciprocal rank fusion."""

import logging
from dataclasses import dataclass
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from app.config import Settings
from app.db.models import Source, Tool
from app.toolsearch.embeddings import EmbeddingError, embed
from app.toolsearch.sparse import encode_document, encode_query

logger = logging.getLogger(__name__)

DENSE = "dense"
SPARSE = "sparse"
PREFETCH = 50


def document_text(source: Source, tool: Tool) -> str:
    """What a tool is searched by."""
    route = f"{tool.method} {tool.path}" if tool.method and tool.path else ""
    parts = [tool.name, tool.description, " ".join(tool.tags or []), source.name, source.description or "", route]
    return "\n".join(p for p in parts if p)


@dataclass
class Filters:
    type: str | None = None
    tags: tuple[str, ...] = ()
    source: str | None = None
    version: str | None = None


def build_filter(roles: list[str], filters: Filters) -> models.Filter:
    """Enabled tools whose source the caller may see, narrowed by the requested filters."""
    must: list = [
        models.FieldCondition(key="enabled", match=models.MatchValue(value=True)),
        models.Filter(
            should=[
                models.IsNullCondition(is_null=models.PayloadField(key="required_role")),
                models.FieldCondition(key="required_role", match=models.MatchAny(any=roles or [""])),
            ]
        ),
    ]
    if filters.type:
        must.append(models.FieldCondition(key="type", match=models.MatchValue(value=filters.type)))
    if filters.source:
        must.append(models.FieldCondition(key="source", match=models.MatchValue(value=filters.source)))
    if filters.version:
        must.append(models.FieldCondition(key="version", match=models.MatchValue(value=filters.version)))
    must.extend(models.FieldCondition(key="tags", match=models.MatchValue(value=t)) for t in filters.tags)
    return models.Filter(must=must)


class ToolIndex:
    def __init__(self, settings: Settings, client: AsyncQdrantClient | None = None) -> None:
        self.settings = settings
        self.collection = settings.qdrant_collection
        self.client = client or AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self.dense = bool(settings.embeddings_url and settings.embeddings_model)
        self._dense_size = settings.embeddings_dimensions

    async def ensure_collection(self, recreate: bool = False) -> bool:
        """Create the collection if it does not exist (or always, with `recreate`); returns whether it did."""
        exists = await self.client.collection_exists(self.collection)
        if exists and not recreate:
            return False
        if exists:
            await self.client.delete_collection(self.collection)
        vectors = {}
        if self.dense:
            if not self._dense_size:
                self._dense_size = len((await embed(self.settings, ["dimension probe"]))[0])
            vectors[DENSE] = models.VectorParams(size=self._dense_size, distance=models.Distance.COSINE)
        await self.client.create_collection(
            self.collection,
            vectors_config=vectors,
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        return True

    async def _points(self, source: Source, tools: list[Tool]) -> list[models.PointStruct]:
        texts = [document_text(source, t) for t in tools]
        dense = await embed(self.settings, texts) if self.dense and texts else [None] * len(tools)
        points = []
        for tool, text, vector in zip(tools, texts, dense, strict=True):
            indices, values = encode_document(text)
            vectors: dict = {SPARSE: models.SparseVector(indices=indices, values=values)}
            if vector is not None:
                vectors[DENSE] = vector
            points.append(
                models.PointStruct(
                    id=str(UUID(tool.id)),
                    vector=vectors,
                    payload={
                        "name": tool.name,
                        "source": source.name,
                        "source_id": source.id,
                        "type": source.type,
                        "version": source.version,
                        "tags": tool.tags or [],
                        "required_role": source.required_role,
                        "enabled": tool.enabled,
                    },
                )
            )
        return points

    async def delete_source(self, source_id: str) -> None:
        await self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id))]
                )
            ),
        )

    async def index_source(self, source: Source) -> None:
        """Replace the points of the source by those of its current tools."""
        points = await self._points(source, list(source.tools))  # embed first: a failure leaves the old points
        await self.delete_source(source.id)
        if points:
            await self.client.upsert(self.collection, points=points)

    async def reindex(self, sources: list[Source]) -> int:
        """Rebuild the whole collection; returns the number of tools indexed."""
        await self.ensure_collection(recreate=True)
        total = 0
        for source in sources:
            await self.index_source(source)
            total += len(source.tools)
        return total

    async def search(self, query: str, roles: list[str], filters: Filters, limit: int) -> list[str]:
        """Names of the best matching tools, best first."""
        flt = build_filter(roles, filters)
        indices, values = encode_query(query)
        sparse = models.SparseVector(indices=indices, values=values)
        dense = None
        if self.dense:
            try:
                dense = (await embed(self.settings, [query]))[0]
            except EmbeddingError as exc:
                logger.warning("Dense search skipped: %s", exc)
        if dense is not None:
            result = await self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(query=dense, using=DENSE, filter=flt, limit=PREFETCH),
                    models.Prefetch(query=sparse, using=SPARSE, filter=flt, limit=PREFETCH),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=["name"],
            )
        else:
            result = await self.client.query_points(
                self.collection, query=sparse, using=SPARSE, query_filter=flt, limit=limit, with_payload=["name"]
            )
        return [p.payload["name"] for p in result.points]
