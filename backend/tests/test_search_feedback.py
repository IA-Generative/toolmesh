from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import searchlog
from app.config import Settings, get_settings
from app.db.models import SearchEvent, SearchFeedback
from app.main import app
from app.toolsearch import Filters
from tests.test_tools import auth, make_token
from tests.test_toolsearch import found, index_for, load_sources

ALICE = auth(make_token(["user"], sub="alice"))
BOB = auth(make_token(["user"], sub="bob"))
ADMIN = auth(make_token(["user", "admin"], sub="boss"))


async def search(client: AsyncClient, q: str = "weather", headers: dict[str, str] = ALICE, **params: Any) -> dict:
    response = await client.get("/api/me/tools/search", params={"q": q, **params}, headers=headers)
    assert response.status_code == 200
    return response.json()


async def ids_of(client: AsyncClient) -> dict[str, str]:
    """Tool name -> id, for the tools of the test registry (their names are unique there)."""
    tools = (await client.get("/api/me/tools", headers=ADMIN)).json()["tools"]
    return {t["name"]: t["id"] for t in tools}


async def verdict(client: AsyncClient, search_id: str, headers: dict[str, str] = ALICE, **body: Any):
    """Post a verdict; `expected` holds tool names, turned into ids (an unknown name is sent as it is)."""
    ids = await ids_of(client)
    body = {"verdict": "found", "expected": ["get_weather"]} | body
    body["expected"] = [ids.get(n, n) for n in body["expected"]]
    return await client.post(f"/api/search/{search_id}/feedback", json=body, headers=headers)


async def pending(client: AsyncClient) -> list[dict]:
    return (await client.get("/api/admin/search/feedback", headers=ADMIN)).json()


async def approve(client: AsyncClient, feedback_id: str, **body: Any):
    ids = await ids_of(client)
    if "expected" in body:
        body["expected"] = [ids.get(n, n) for n in body["expected"]]
    return await client.patch(
        f"/api/admin/search/feedback/{feedback_id}", json={"status": "approved"} | body, headers=ADMIN
    )


# --- Logging a search ----------------------------------------------------------------------------------------------


async def test_a_search_with_a_query_is_logged_and_gets_an_id(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    result = await search(client, "weather", type="api")

    assert result["search_id"]
    async with session_factory() as db:
        event = await db.get(SearchEvent, result["search_id"])
    assert (event.user_sub, event.query, event.mode) == ("alice", "weather", "basic")
    assert event.filters == {"type": "api"} and event.results == [t["id"] for t in result["tools"]]


async def test_filters_alone_and_a_disabled_log_leave_no_trace(client: AsyncClient) -> None:
    assert (await search(client, "", type="api"))["search_id"] is None

    app.dependency_overrides[get_settings] = lambda: Settings(keycloak_url="http://kc.test", search_log_enabled=False)
    assert (await search(client, "weather"))["search_id"] is None


# --- Clicks and verdicts -------------------------------------------------------------------------------------------


async def test_a_click_is_recorded_for_the_owner_of_the_search_only(client: AsyncClient) -> None:
    search_id = (await search(client))["search_id"]
    click = {"tool_id": (await ids_of(client))["get_weather"], "rank": 1}

    assert (await client.post(f"/api/search/{search_id}/click", json=click, headers=ALICE)).status_code == 204
    assert (await client.post(f"/api/search/{search_id}/click", json=click, headers=BOB)).status_code == 404
    assert (await client.post("/api/search/nope/click", json=click, headers=ALICE)).status_code == 404
    assert (
        await client.post(f"/api/search/{search_id}/click", json={"tool_id": "x", "rank": 0}, headers=ALICE)
    ).status_code == 422


async def test_a_verdict_names_a_known_tool(client: AsyncClient) -> None:
    search_id = (await search(client))["search_id"]
    ids = await ids_of(client)

    ok = await verdict(client, search_id)
    assert (ok.status_code, ok.json()["status"], ok.json()["expected"]) == (201, "pending", [ids["get_weather"]])
    assert (await verdict(client, search_id, expected=[])).status_code == 422  # "found" needs the tool
    assert (await verdict(client, search_id, expected=["nope"])).status_code == 422
    assert (await verdict(client, search_id, headers=BOB)).status_code == 404  # not their search
    nothing = await verdict(client, search_id, verdict="not_found", expected=[], comment="  rien  ")
    assert (nothing.status_code, nothing.json()["comment"]) == (201, "rien")


async def test_a_pending_verdict_is_replaced_but_a_reviewed_one_is_final(client: AsyncClient) -> None:
    search_id = (await search(client))["search_id"]
    first = (await verdict(client, search_id)).json()
    second = (await verdict(client, search_id, expected=["get_forecast"])).json()

    assert second["id"] == first["id"] and second["expected"] == [(await ids_of(client))["get_forecast"]]
    await approve(client, first["id"])
    assert (await verdict(client, search_id)).status_code == 409


# --- Review and dataset --------------------------------------------------------------------------------------------


async def test_only_admins_reach_the_dashboard(client: AsyncClient) -> None:
    for method, url in (
        ("GET", "/api/admin/search/stats"),
        ("GET", "/api/admin/search/feedback"),
        ("GET", "/api/admin/search/dataset"),
        ("POST", "/api/admin/search/evaluate"),
        ("PATCH", "/api/admin/search/feedback/x"),
    ):
        assert (await client.request(method, url, json={"status": "approved"}, headers=ALICE)).status_code == 403
        assert (await client.request(method, url, json={"status": "approved"})).status_code == 401


async def test_the_admin_reviews_the_verdicts(client: AsyncClient) -> None:
    search_id = (await search(client, "weather city"))["search_id"]
    await verdict(client, search_id, comment="le premier résultat")

    ids = await ids_of(client)
    items = await pending(client)
    assert len(items) == 1
    assert (items[0]["query"], items[0]["verdict"], items[0]["expected"], items[0]["comment"]) == (
        "weather city",
        "found",
        [ids["get_weather"]],
        "le premier résultat",
    )
    weather = next(r for r in items[0]["results"] if r["id"] == ids["get_weather"])
    assert (weather["name"], weather["source"]) == ("get_weather", "weather-api")

    reviewed = await approve(client, items[0]["id"], expected=["get_forecast"])
    assert reviewed.json()["expected"] == [ids["get_forecast"]]
    assert await pending(client) == []
    assert (await approve(client, items[0]["id"], expected=["nope"])).status_code == 422
    assert (
        await client.patch("/api/admin/search/feedback/nope", json={"status": "approved"}, headers=ADMIN)
    ).status_code == 404


async def test_the_dataset_holds_the_approved_verdicts_in_the_eval_format(client: AsyncClient) -> None:
    kept = (await search(client, "weather city", type="api"))["search_id"]
    nothing = (await search(client, "tarte aux pommes"))["search_id"]
    refused = (await search(client, "something else"))["search_id"]
    for sid, body in ((kept, {}), (nothing, {"verdict": "not_found", "expected": []}), (refused, {})):
        await verdict(client, sid, **body)
    by_query = {i["query"]: i["id"] for i in await pending(client)}
    await approve(client, by_query["weather city"])
    await approve(client, by_query["tarte aux pommes"])
    await client.patch(
        f"/api/admin/search/feedback/{by_query['something else']}", json={"status": "rejected"}, headers=ADMIN
    )

    data = (await client.get("/api/admin/search/dataset", headers=ADMIN)).json()

    weather = (await ids_of(client))["get_weather"]
    assert sorted(data, key=lambda i: i["query"]) == [
        {"query": "tarte aux pommes", "expect": [], "category": "no-answer"},
        {"query": "weather city", "expect": [weather], "category": "feedback", "filters": {"type": "api"}},
    ]


async def test_the_dataset_has_no_duplicates(client: AsyncClient) -> None:
    for user in (ALICE, BOB):
        sid = (await search(client, "Weather  city", headers=user))["search_id"]
        await verdict(client, sid, headers=user)
    for item in await pending(client):
        await approve(client, item["id"])

    assert len((await client.get("/api/admin/search/dataset", headers=ADMIN)).json()) == 1


# --- What approved verdicts teach ----------------------------------------------------------------------------------


async def test_approved_queries_become_aliases_of_the_tool(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    for i in range(12):
        sid = (await search(client, f"zebra {i}"))["search_id"]
        await verdict(client, sid)
    for item in await pending(client):
        await approve(client, item["id"])
    sid = (await search(client, "rejected phrase"))["search_id"]
    await verdict(client, sid)
    rejected = next(i for i in await pending(client) if i["query"] == "rejected phrase")
    await client.patch(f"/api/admin/search/feedback/{rejected['id']}", json={"status": "rejected"}, headers=ADMIN)

    async with session_factory() as db:
        aliases = await searchlog.learned_aliases(db)

    learned = aliases[(await ids_of(client))["get_weather"]]
    assert len(learned) == searchlog.MAX_ALIASES_PER_TOOL
    assert learned[0] == "zebra 11"  # the newest first
    assert "rejected phrase" not in learned


async def test_a_verdict_targets_one_of_two_tools_sharing_a_name(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tool_id
) -> None:
    twin = {
        "name": "weather-twin",
        "type": "api",
        "url": "http://w2.test",
        "openapi_url": "http://w2.test/o.json",
        "tools": [{"name": "get_weather", "description": "Weather, the other one", "method": "GET", "path": "/w"}],
    }
    created = await client.post("/api/sources", json=twin, headers=ALICE)
    twin_id = created.json()["tools"][0]["id"]
    original_id = await tool_id("get_weather", "weather-api")
    assert twin_id != original_id

    sid = (await search(client, "weather twin"))["search_id"]
    saved = await client.post(
        f"/api/search/{sid}/feedback", json={"verdict": "found", "expected": [twin_id]}, headers=ALICE
    )
    await approve(client, saved.json()["id"])

    async with session_factory() as db:
        aliases = await searchlog.learned_aliases(db)
    assert aliases == {twin_id: ["weather twin"]}


async def test_approving_a_verdict_teaches_the_index(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    index = index_for(dense=False)
    await index.reindex(await load_sources(session_factory))
    for target in ("app.toolsearch.get_index", "app.routers.search_feedback.get_index"):
        monkeypatch.setattr(target, lambda _: index)
    assert await found(index, "zebra crossing", ["user"], Filters(), 5) == []

    sid = (await search(client, "zebra crossing"))["search_id"]
    await verdict(client, sid, expected=["get_weather"])
    item = (await pending(client))[0]
    await approve(client, item["id"])

    assert (await found(index, "zebra crossing", ["user"], Filters(), 5))[0] == "get_weather"
    await client.patch(f"/api/admin/search/feedback/{item['id']}", json={"status": "rejected"}, headers=ADMIN)
    assert await found(index, "zebra crossing", ["user"], Filters(), 5) == []  # un-taught


async def test_the_evaluation_ignores_what_the_dataset_taught(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = await client.post("/api/admin/search/evaluate", headers=ADMIN)
    assert empty.status_code == 422

    sid = (await search(client, "weather city"))["search_id"]  # a plain keyword match finds it
    await verdict(client, sid)
    sid = (await search(client, "zebra crossing"))["search_id"]  # nothing says "zebra": only a taught alias would
    await verdict(client, sid)
    sid = (await search(client, "tarte aux pommes"))["search_id"]
    await verdict(client, sid, verdict="not_found", expected=[])
    for item in await pending(client):
        await approve(client, item["id"])

    response = await client.post("/api/admin/search/evaluate", headers=ADMIN)

    assert response.status_code == 200
    body = response.json()
    assert body["queries"] == 3
    keyword = body["metrics"]["keyword"]
    assert keyword["queries"] == 2 and keyword["hit1"] == 0.5 and keyword["no_answer"] == 1.0  # "zebra" is not found


# --- Dashboard -----------------------------------------------------------------------------------------------------


async def test_the_statistics_summarise_searches_clicks_and_verdicts(client: AsyncClient) -> None:
    ids = await ids_of(client)
    hit = (await search(client, "weather city"))["search_id"]
    await client.post(f"/api/search/{hit}/click", json={"tool_id": ids["get_weather"], "rank": 2}, headers=ALICE)
    await client.post(f"/api/search/{hit}/click", json={"tool_id": ids["get_forecast"], "rank": 4}, headers=ALICE)
    await verdict(client, hit)
    miss = (await search(client, "tarte aux pommes"))["search_id"]  # no result
    await verdict(client, miss, verdict="not_found", expected=["get_weather"], headers=ALICE)
    await search(client, "tarte aux pommes", headers=BOB)

    stats = (await client.get("/api/admin/search/stats", params={"days": 7}, headers=ADMIN)).json()

    assert stats["searches"] == 3 and stats["zero_results"] == 2
    assert stats["zero_result_rate"] == pytest.approx(2 / 3)
    assert stats["by_mode"] == {"basic": 3}
    assert (stats["clicks"], stats["click_rate"], stats["click_mrr"]) == (
        2,
        pytest.approx(1 / 3),
        0.5,
    )  # first click: rank 2
    assert (stats["verdicts"], stats["found_rate"]) == ({"found": 1, "not_found": 1}, 0.5)
    assert stats["dataset"] == {"pending": 2, "approved": 0}
    assert stats["top_zero_result_queries"] == [{"query": "tarte aux pommes", "count": 2}]
    weather = {"id": ids["get_weather"], "name": "get_weather", "source": "weather-api"}
    assert stats["top_missed"] == [{"query": "tarte aux pommes", "expected": [weather], "count": 1}]
    assert {"tool": weather, "count": 2} in stats["tools_chosen"]  # one click and one verdict
    assert len(stats["by_day"]) == 8 and stats["by_day"][-1]["searches"] == 3
    assert stats["latency_ms"]["p95"] >= 0


async def test_statistics_of_an_empty_log(client: AsyncClient) -> None:
    stats = (await client.get("/api/admin/search/stats", headers=ADMIN)).json()

    assert (stats["searches"], stats["zero_result_rate"], stats["found_rate"], stats["click_mrr"]) == (
        0,
        None,
        None,
        None,
    )
    assert stats["top_zero_result_queries"] == [] and len(stats["by_day"]) == 31


# --- Retention -----------------------------------------------------------------------------------------------------


async def test_old_searches_are_purged_unless_they_belong_to_the_dataset(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    old = datetime.now(UTC) - timedelta(days=200)
    async with session_factory() as db:
        for name in ("forgotten", "kept", "recent"):
            db.add(
                SearchEvent(
                    id=name.ljust(32, "0"),
                    user_sub="alice",
                    query=name,
                    mode="basic",
                    results=[],
                    took_ms=1,
                    created_at=datetime.now(UTC) if name == "recent" else old,
                )
            )
        db.add(
            SearchFeedback(
                search_id="kept".ljust(32, "0"),
                user_sub="alice",
                verdict="found",
                expected=["get_weather"],
                status="approved",
            )
        )
        await db.commit()

        assert await searchlog.purge_old_events(db, 90) == 1
        remaining = set((await db.scalars(select(SearchEvent.query))).all())

    assert remaining == {"kept", "recent"}
