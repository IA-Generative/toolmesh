from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import Source
from app.toolsearch import Filters, ToolIndex
from app.toolsearch.embeddings import EmbeddingError, embed
from app.toolsearch.sparse import encode_document, encode_query, tokenize
from tests.test_tools import auth, make_token

# --- Keyword vectors -----------------------------------------------------------------------------------------------


def test_tokens_are_folded_and_stop_words_dropped() -> None:
    assert tokenize("Météo d'une ville, en FRANCE!") == ["meteo", "ville", "france"]
    assert tokenize("get_weather the API") == ["get", "weather", "api"]
    assert tokenize("a - 1") == []


def test_repeated_words_weigh_more_but_saturate() -> None:
    once = dict(zip(*encode_document("sql"), strict=True))
    thrice = dict(zip(*encode_document("sql sql sql"), strict=True))
    many = dict(zip(*encode_document("sql " * 100), strict=True))
    (a,), (b,), (c,) = once.values(), thrice.values(), many.values()

    assert a < b < c < 2.2


def test_query_vector_has_unique_sorted_indices() -> None:
    indices, values = encode_query("météo meteo ville")

    assert indices == sorted(set(indices)) and len(indices) == 2
    assert values == [1.0, 1.0]


# --- Embeddings API ------------------------------------------------------------------------------------------------

EMB = Settings(
    embeddings_url="http://llm.test/v1/", embeddings_model="m", embeddings_api_key="k", embeddings_dimensions=3
)


def emb_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_embeddings_are_requested_in_batches_and_kept_in_order() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        calls.append(body | {"url": str(request.url), "auth": request.headers["authorization"]})
        # answer out of order, as some servers do
        data = [{"index": i, "embedding": [float(t)]} for i, t in enumerate(body["input"])]
        return httpx.Response(200, json={"data": data[::-1]})

    texts = [str(i) for i in range(70)]
    vectors = await embed(EMB, texts, emb_client(handler))

    assert [v[0] for v in vectors] == [float(i) for i in range(70)]
    assert [len(c["input"]) for c in calls] == [64, 6]
    assert calls[0]["url"] == "http://llm.test/v1/embeddings"
    assert (calls[0]["model"], calls[0]["dimensions"], calls[0]["auth"]) == ("m", 3, "Bearer k")


@pytest.mark.parametrize(
    ("response", "message"),
    [(httpx.Response(500), "500"), (httpx.Response(200, json={"data": []}), "unexpected number")],
    ids=["http-error", "wrong-count"],
)
async def test_embedding_failures_are_explained(response: httpx.Response, message: str) -> None:
    with pytest.raises(EmbeddingError, match=message):
        await embed(EMB, ["x"], emb_client(lambda _: response))


async def test_embeddings_need_a_configuration() -> None:
    with pytest.raises(EmbeddingError, match="not configured"):
        await embed(Settings(), ["x"])


# --- Index ---------------------------------------------------------------------------------------------------------

DIMS = {"web": 0, "meteo": 1, "sql": 2, "search": 3}


def fake_vector(text: str) -> list[float]:
    words = tokenize(text)
    vector = [float(sum(key in w for w in words)) for key in DIMS]
    return vector if any(vector) else [0.1] * len(DIMS)


@pytest.fixture
def fake_embed(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    sent: list[list[str]] = []

    async def fake(settings: Settings, texts: list[str], client: Any = None) -> list[list[float]]:
        sent.append(texts)
        return [fake_vector(t) for t in texts]

    monkeypatch.setattr("app.toolsearch.index.embed", fake)
    return sent


def index_for(dense: bool) -> ToolIndex:
    settings = Settings(
        qdrant_url="memory",
        **({"embeddings_url": "http://llm.test", "embeddings_model": "m", "embeddings_dimensions": 4} if dense else {}),
    )
    return ToolIndex(settings, AsyncQdrantClient(":memory:"))


async def load_sources(session_factory: async_sessionmaker[AsyncSession]) -> list[Source]:
    async with session_factory() as db:
        return list((await db.scalars(select(Source))).all())


@pytest.fixture
async def loaded(client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]) -> list[Source]:
    """The test registry (web_search, fetch_page, get_weather, get_forecast, summarize, query_database,...)."""
    return await load_sources(session_factory)


@pytest.fixture(params=[False, True], ids=["keyword", "hybrid"])
async def index(request: pytest.FixtureRequest, loaded: list[Source], fake_embed: list[list[str]]) -> ToolIndex:
    idx = index_for(dense=request.param)
    await idx.reindex(loaded)
    return idx


ALL = ["user", "admin"]


async def test_the_best_match_comes_first(index: ToolIndex) -> None:
    assert (await index.search("search the web", ALL, Filters(), 5))[0] == "web_search"
    assert (await index.search("météo ville", ALL, Filters(), 5))[0] in {"get_weather", "get_forecast"}


async def test_filters_narrow_the_results(index: ToolIndex) -> None:
    api = await index.search("web météo", ALL, Filters(type="api"), 10)
    assert api and {"web_search", "fetch_page"}.isdisjoint(api)

    assert await index.search("météo", ALL, Filters(tags=("données", "météo")), 10)
    assert await index.search("météo", ALL, Filters(tags=("nope",)), 10) == []
    assert await index.search("météo", ALL, Filters(source="weather-api"), 10)
    # keywords alone find nothing there; with embeddings the nearest tools of the source come back, but only those
    assert set(await index.search("météo", ALL, Filters(source="search-mcp"), 10)) <= {"web_search", "fetch_page"}
    assert await index.search("météo", ALL, Filters(version="9"), 10) == []


async def test_restricted_tools_are_only_found_with_the_role(index: ToolIndex) -> None:
    assert "query_database" in await index.search("sql", ["user", "admin"], Filters(), 10)
    assert "query_database" not in await index.search("sql", ["user"], Filters(), 10)
    assert "query_database" not in await index.search("sql", [], Filters(), 10)


async def test_reindexing_one_source_replaces_its_points(
    index: ToolIndex, loaded: list[Source], session_factory: async_sessionmaker[AsyncSession]
) -> None:
    source = next(s for s in await load_sources(session_factory) if s.name == "weather-api")
    source.tools[:] = [t for t in source.tools if t.name == "get_weather"]
    await index.index_source(source)

    assert "get_forecast" not in await index.search("météo", ALL, Filters(), 10)
    assert "get_weather" in await index.search("météo", ALL, Filters(), 10)

    await index.delete_source(source.id)
    assert {"get_weather", "get_forecast"}.isdisjoint(await index.search("météo", ALL, Filters(), 10))


async def test_disabled_tools_are_not_found(loaded: list[Source], fake_embed: list[list[str]]) -> None:
    next(t for s in loaded for t in s.tools if t.name == "get_forecast").enabled = False
    idx = index_for(dense=False)
    await idx.reindex(loaded)

    assert "get_forecast" not in await idx.search("météo", ALL, Filters(), 10)


async def test_the_dense_vector_finds_what_keywords_miss(loaded: list[Source], fake_embed: list[list[str]]) -> None:
    keyword, hybrid = index_for(dense=False), index_for(dense=True)
    await keyword.reindex(loaded)
    await hybrid.reindex(loaded)

    # "internet" is nowhere in the tools: only the embedding (here: the word "web" folded into the query) can link it
    assert await keyword.search("internet", ALL, Filters(), 3) == []
    query = "web internet"
    assert "web_search" in await hybrid.search(query, ALL, Filters(), 3)


async def test_hybrid_search_survives_an_embedding_outage(
    loaded: list[Source], monkeypatch: pytest.MonkeyPatch, fake_embed: list[list[str]]
) -> None:
    idx = index_for(dense=True)
    await idx.reindex(loaded)

    async def down(*_: Any, **__: Any) -> list[list[float]]:
        raise EmbeddingError("down")

    monkeypatch.setattr("app.toolsearch.index.embed", down)

    assert (await idx.search("web", ALL, Filters(), 5))[0] in {"web_search", "fetch_page"}


# --- Route ---------------------------------------------------------------------------------------------------------


@pytest.fixture
async def with_index(index: ToolIndex, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ToolIndex]:
    monkeypatch.setattr("app.routers.tools.get_index", lambda _: index)
    yield index


def names(response) -> list[str]:
    return [t["name"] for t in response.json()["tools"]]


async def test_search_route_uses_the_index(client: AsyncClient, with_index: ToolIndex) -> None:
    response = await client.get(
        "/api/me/tools/search", params={"q": "search the web"}, headers=auth(make_token(["user"]))
    )

    assert response.status_code == 200
    assert names(response)[0] == "web_search"
    assert response.json()["mode"] == ("hybrid" if with_index.dense else "keyword")


async def test_search_route_applies_filters_and_limit(client: AsyncClient, with_index: ToolIndex) -> None:
    user = auth(make_token(["user"]))

    by_type = await client.get("/api/me/tools/search", params={"q": "météo web", "type": "api"}, headers=user)
    assert names(by_type) and all(n in {"get_weather", "get_forecast"} for n in names(by_type))

    by_tag = await client.get(
        "/api/me/tools/search", params=[("q", "météo"), ("tag", "données"), ("tag", "météo")], headers=user
    )
    assert set(names(by_tag)) == {"get_weather", "get_forecast"}

    limited = await client.get("/api/me/tools/search", params={"q": "météo", "limit": 1}, headers=user)
    assert len(names(limited)) == 1


async def test_search_route_never_leaks_a_restricted_tool(
    client: AsyncClient, with_index: ToolIndex, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An index that is wrong (stale, or filtering badly) must not widen what the caller sees.
    async def everything(*_: Any) -> list[str]:
        return ["query_database", "web_search"]

    monkeypatch.setattr(with_index, "search", everything)

    response = await client.get("/api/me/tools/search", params={"q": "sql"}, headers=auth(make_token(["user"])))

    assert names(response) == ["web_search"]


async def test_search_route_falls_back_when_the_index_fails(
    client: AsyncClient, with_index: ToolIndex, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_: Any) -> list[str]:
        raise RuntimeError("qdrant is down")

    monkeypatch.setattr(with_index, "search", broken)

    response = await client.get("/api/me/tools/search", params={"q": "weather"}, headers=auth(make_token(["user"])))

    assert response.json()["mode"] == "basic"
    assert "get_weather" in names(response)


async def test_search_without_index_matches_words_in_the_registry(client: AsyncClient) -> None:
    user = auth(make_token(["user"]))

    found = await client.get("/api/me/tools/search", params={"q": "weather city"}, headers=user)
    assert (found.json()["mode"], names(found)[:1]) == ("basic", ["get_weather"])

    assert names(await client.get("/api/me/tools/search", params={"q": "zzz"}, headers=user)) == []
    assert "query_database" not in names(await client.get("/api/me/tools/search", params={"q": "sql"}, headers=user))


async def test_filters_alone_do_not_need_a_query(client: AsyncClient) -> None:
    response = await client.get(
        "/api/me/tools/search", params={"type": "mcp", "source": "search-mcp"}, headers=auth(make_token(["user"]))
    )

    assert response.json()["mode"] == "filter"
    assert set(names(response)) == {"web_search", "fetch_page"}


async def test_search_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/me/tools/search", params={"q": "x"})).status_code == 401


# --- Keeping the index in sync / admin -----------------------------------------------------------------------------


async def test_creating_refreshing_and_deleting_a_source_updates_the_index(
    client: AsyncClient, fake_embed: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    idx = index_for(dense=False)
    monkeypatch.setattr("app.toolsearch.get_index", lambda _: idx)
    user = auth(make_token(["user"]))
    body = {
        "name": "orders-api",
        "type": "api",
        "url": "http://o.test",
        "openapi_url": "http://o.test/o.json",
        "tools": [{"name": "list_orders", "description": "List the orders", "method": "GET", "path": "/orders"}],
    }

    created = await client.post("/api/sources", json=body, headers=user)
    assert "list_orders" in await idx.search("orders", ALL, Filters(), 5)

    await client.delete(f"/api/sources/{created.json()['id']}", headers=user)
    assert await idx.search("orders", ALL, Filters(), 5) == []


async def test_an_index_failure_does_not_break_the_registry(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Broken:
        async def ensure_collection(self) -> None:
            raise RuntimeError("qdrant is down")

        async def delete_source(self, _: str) -> None:
            raise RuntimeError("qdrant is down")

    monkeypatch.setattr("app.toolsearch.get_index", lambda _: Broken())
    user = auth(make_token(["user"]))

    created = await client.post(
        "/api/sources", json={"name": "rewrite", "type": "skill", "description": "x"}, headers=user
    )
    assert created.status_code == 201
    assert (await client.delete(f"/api/sources/{created.json()['id']}", headers=user)).status_code == 204


async def test_reindex_is_for_admins_and_needs_an_index(
    client: AsyncClient, fake_embed: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = auth(make_token(["user", "admin"]))
    assert (await client.post("/api/admin/reindex", headers=auth(make_token(["user"])))).status_code == 403
    assert (await client.post("/api/admin/reindex", headers=admin)).status_code == 503

    idx = index_for(dense=False)
    monkeypatch.setattr("app.routers.admin.get_index", lambda _: idx)
    response = await client.post("/api/admin/reindex", headers=admin)

    assert response.status_code == 200
    assert response.json()["tools"] == 7
    assert "web_search" in await idx.search("web", ALL, Filters(), 5)
