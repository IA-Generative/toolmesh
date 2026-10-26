import logging
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Source
from app.searchlog import learned_aliases
from app.toolsearch.index import Filters, ToolIndex

logger = logging.getLogger(__name__)

__all__ = ["Filters", "ToolIndex", "get_index", "sync_source", "sync_source_with_feedback", "forget_source"]


@lru_cache
def _index(
    url: str,
    api_key: str | None,
    collection: str,
    emb_url: str | None,
    emb_model: str | None,
    dims: int | None,
    emb_key: str | None,
):
    settings = Settings(
        qdrant_url=url,
        qdrant_api_key=api_key,
        qdrant_collection=collection,
        embeddings_url=emb_url,
        embeddings_model=emb_model,
        embeddings_dimensions=dims,
        embeddings_api_key=emb_key,
    )
    return ToolIndex(settings)


def get_index(settings: Settings) -> ToolIndex | None:
    """The tool index, or None when no Qdrant is configured."""
    if not settings.qdrant_url:
        return None
    return _index(
        settings.qdrant_url,
        settings.qdrant_api_key,
        settings.qdrant_collection,
        settings.embeddings_url,
        settings.embeddings_model,
        settings.embeddings_dimensions,
        settings.embeddings_api_key,
    )


async def sync_source(settings: Settings, source: Source, aliases: dict[str, list[str]] | None = None) -> None:
    """Keep the index up to date; a failure is logged, never raised (a reindex repairs it)."""
    index = get_index(settings)
    if index is None:
        return
    try:
        await index.ensure_collection()
        await index.index_source(source, aliases)
    except Exception:
        logger.exception("Could not index the tools of %s", source.name)


async def sync_source_with_feedback(settings: Settings, db: AsyncSession, source: Source) -> None:
    """`sync_source`, with the aliases learned from the approved verdicts of users."""
    if get_index(settings) is None:
        return
    try:
        aliases = await learned_aliases(db)
    except Exception:
        logger.exception("Could not read the learned aliases")
        aliases = None
    await sync_source(settings, source, aliases)


async def forget_source(settings: Settings, source_id: str) -> None:
    index = get_index(settings)
    if index is None:
        return
    try:
        await index.delete_source(source_id)
    except Exception:
        logger.exception("Could not remove the tools of source %s from the index", source_id)
