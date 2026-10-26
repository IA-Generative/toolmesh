"""The Qdrant collection holding one point per tool: a keyword vector, an optional dense vector and the payload
used for filtering. Search fuses both rankings with reciprocal rank fusion."""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from app.config import Settings
from app.db.models import Source, Tool
from app.toolsearch.embeddings import EmbeddingError, embed
from app.toolsearch.sparse import encode_document, encode_query, tokenize
from app.toolsearch.text import dense_text, humanize, sparse_parts

logger = logging.getLogger(__name__)

DENSE = "dense"
SPARSE = "sparse"
PREFETCH = 50


@dataclass
class Hit:
    name: str
    score: float
    dense_score: float | None  # cosine similarity, None when the tool was not a dense match


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
                models.IsEmptyCondition(is_empty=models.PayloadField(key="required_role")),
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

    async def _expected_dense_size(self) -> int | None:
        if not self.dense:
            return None
        if not self._dense_size:
            self._dense_size = len((await embed(self.settings, ["dimension probe"], kind="query"))[0])
        return self._dense_size

    async def ensure_collection(self, recreate: bool = False) -> bool:
        """Create the collection if it does not exist, or if it does not fit the embeddings (none before, another size
        now) or `recreate` is set; returns whether it did, i.e. whether the index is empty and must be filled."""
        size = await self._expected_dense_size()
        if await self.client.collection_exists(self.collection):
            if not recreate and await self._current_dense_size() == size:
                return False
            await self.client.delete_collection(self.collection)
        await self.client.create_collection(
            self.collection,
            vectors_config={DENSE: models.VectorParams(size=size, distance=models.Distance.COSINE)} if size else {},
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        for field in ("type", "source", "source_id", "version", "tags", "required_role"):
            await self.client.create_payload_index(self.collection, field, models.PayloadSchemaType.KEYWORD)
        await self.client.create_payload_index(self.collection, "enabled", models.PayloadSchemaType.BOOL)
        return True

    async def _current_dense_size(self) -> int | None:
        vectors = (await self.client.get_collection(self.collection)).config.params.vectors
        dense = vectors.get(DENSE) if isinstance(vectors, dict) else None
        return dense.size if dense else None

    def _payload(self, source: Source, tool: Tool, doc_hash: str) -> dict:
        return {
            "name": tool.name,
            "source": source.name,
            "source_id": source.id,
            "type": source.type,
            "version": source.version,
            "tags": tool.tags or [],
            "required_role": source.required_role,
            "enabled": tool.enabled,
            "doc_hash": doc_hash,
        }

    def _doc_hash(self, dense_text_: str, parts: list[tuple[str, float]]) -> str:
        """Identifies what the vectors of a tool were computed from: when it changes, they must be computed again."""
        s = self.settings
        fingerprint = [dense_text_, parts, s.embeddings_model, s.embeddings_document_prefix, s.embeddings_dimensions]
        return hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False).encode()).hexdigest()[:16]

    async def _indexed(self, source_id: str) -> dict[str, str | None]:
        """Point id -> doc_hash of what the index holds for a source."""
        found: dict[str, str | None] = {}
        offset = None
        flt = models.Filter(must=[models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id))])
        while True:
            points, offset = await self.client.scroll(
                self.collection,
                scroll_filter=flt,
                limit=256,
                offset=offset,
                with_payload=["doc_hash"],
                with_vectors=False,
            )
            found.update({str(p.id): (p.payload or {}).get("doc_hash") for p in points})
            if offset is None:
                return found

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
        """Bring the points of the source in line with its tools. Only the tools whose text changed are embedded again;
        the others just get their payload (version, role, enabled...) refreshed."""
        wanted: dict[str, tuple[Tool, str, list[tuple[str, float]], str]] = {}
        for tool in source.tools:
            text, parts = dense_text(source, tool), sparse_parts(source, tool)
            wanted[str(UUID(tool.id))] = (tool, text, parts, self._doc_hash(text, parts))
        indexed = await self._indexed(source.id)

        changed = [pid for pid, (_, _, _, h) in wanted.items() if indexed.get(pid) != h]
        dense = {}
        if self.dense and changed:
            vectors = await embed(
                self.settings, [wanted[pid][1] for pid in changed]
            )  # first: a failure changes nothing
            dense = dict(zip(changed, vectors, strict=True))
        gone = [pid for pid in indexed if pid not in wanted]
        if gone:
            await self.client.delete(self.collection, points_selector=models.PointIdsList(points=gone))
        points = []
        for pid in changed:
            tool, _, parts, doc_hash = wanted[pid]
            indices, values = encode_document(parts)
            vector: dict = {SPARSE: models.SparseVector(indices=indices, values=values)}
            if pid in dense:
                vector[DENSE] = dense[pid]
            points.append(models.PointStruct(id=pid, vector=vector, payload=self._payload(source, tool, doc_hash)))
        if points:
            await self.client.upsert(self.collection, points=points)
        unchanged = [pid for pid in wanted if pid not in changed]
        if unchanged:
            await self.client.batch_update_points(
                self.collection,
                update_operations=[
                    models.SetPayloadOperation(
                        set_payload=models.SetPayload(
                            payload=self._payload(source, wanted[pid][0], wanted[pid][3]), points=[pid]
                        )
                    )
                    for pid in unchanged
                ],
            )

    async def reindex(self, sources: list[Source]) -> int:
        """Rebuild the whole collection; returns the number of tools indexed."""
        await self.ensure_collection(recreate=True)
        total = 0
        for source in sources:
            await self.index_source(source)
            total += len(source.tools)
        return total

    async def _rank(self, using: str, query, flt: models.Filter) -> list[tuple[str, float]]:
        result = await self.client.query_points(
            self.collection, query=query, using=using, query_filter=flt, limit=PREFETCH, with_payload=["name"]
        )
        return [(p.payload["name"], p.score) for p in result.points]

    async def search(
        self,
        query: str,
        roles: list[str],
        filters: Filters,
        limit: int,
        only: Literal["keyword", "dense"] | None = None,
    ) -> list[str]:
        """Names of the best matching tools, best first. `only` restricts the ranking to one kind of vector."""
        return [hit.name for hit in await self.search_scored(query, roles, filters, limit, only)]

    async def search_scored(
        self,
        query: str,
        roles: list[str],
        filters: Filters,
        limit: int,
        only: Literal["keyword", "dense"] | None = None,
    ) -> list["Hit"]:
        """The keyword and dense rankings fused by weighted reciprocal rank fusion, plus a bonus for the tools whose
        whole name is in the query (an identifier typed as such must come first, whatever the embedding thinks)."""
        settings = self.settings
        flt = build_filter(roles, filters)
        indices, values = encode_query(query)
        keyword = (
            await self._rank(SPARSE, models.SparseVector(indices=indices, values=values), flt)
            if only != "dense"
            else []
        )
        dense: list[tuple[str, float]] = []
        if self.dense and only != "keyword":
            try:
                vector = (await embed(settings, [query], kind="query"))[0]
                dense = await self._rank(DENSE, vector, flt)
            except EmbeddingError as exc:
                logger.warning("Dense search skipped: %s", exc)
        if settings.search_min_dense_score is not None:
            dense = [(n, s) for n, s in dense if s >= settings.search_min_dense_score]

        scores: dict[str, float] = {}
        k = settings.search_rrf_k
        for weight, ranking in ((settings.search_keyword_weight, keyword), (settings.search_dense_weight, dense)):
            for rank, (name, _) in enumerate(ranking, start=1):
                scores[name] = scores.get(name, 0.0) + weight / (k + rank)
        query_words = set(tokenize(query))
        for name in scores:
            name_words = set(tokenize(humanize(name)))
            if name_words and name_words <= query_words:
                scores[name] += settings.search_name_bonus
        dense_scores = dict(dense)
        ranked = sorted(scores, key=lambda n: -scores[n])[:limit]
        return [Hit(n, scores[n], dense_scores.get(n)) for n in ranked]
