"""What users do with the search: the log of the searches, their clicks and their verdicts, the dataset built from the
verdicts an admin approved, the aliases it teaches the index, and the statistics of the dashboard."""

import statistics
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchClick, SearchEvent, SearchFeedback, Source, Tool

MAX_ALIASES_PER_TOOL = 10
MAX_EVENTS_IN_STATS = 50_000


class FeedbackError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def record_search(
    db: AsyncSession, user_sub: str, query: str, filters: dict[str, Any], mode: str, results: list[str], took_ms: int
) -> str:
    event = SearchEvent(user_sub=user_sub, query=query, filters=filters, mode=mode, results=results, took_ms=took_ms)
    db.add(event)
    await db.commit()
    return event.id


async def tool_refs(db: AsyncSession, ids: set[str] | list[str]) -> dict[str, dict[str, str | None]]:
    """Tool id -> `{id, name, source}` to show it; a tool deleted since is only known by its id."""
    ids = set(ids)
    found = {}
    if ids:
        rows = await db.execute(select(Tool.id, Tool.name, Source.name).join(Source).where(Tool.id.in_(ids)))
        found = {i: {"id": i, "name": name, "source": source} for i, name, source in rows.all()}
    return {i: found.get(i, {"id": i, "name": i[:8], "source": None}) for i in ids}


async def _check_known(db: AsyncSession, ids: list[str]) -> None:
    known = set((await db.scalars(select(Tool.id).where(Tool.id.in_(ids)))).all()) if ids else set()
    if unknown := [i for i in ids if i not in known]:
        raise FeedbackError(f"Unknown tool: {', '.join(unknown)}")


async def _own_event(db: AsyncSession, search_id: str, user_sub: str) -> SearchEvent:
    event = await db.get(SearchEvent, search_id)
    if event is None or event.user_sub != user_sub:  # one only evaluates one's own searches
        raise FeedbackError("Search not found", 404)
    return event


async def record_click(db: AsyncSession, search_id: str, user_sub: str, tool_id: str, rank: int) -> None:
    await _own_event(db, search_id, user_sub)
    db.add(SearchClick(search_id=search_id, tool=tool_id, rank=rank))
    await db.commit()


async def submit_feedback(
    db: AsyncSession, search_id: str, user_sub: str, verdict: str, expected: list[str], comment: str | None
) -> SearchFeedback:
    """Store (or replace, while still pending) the verdict of the user on one of their searches."""
    await _own_event(db, search_id, user_sub)
    expected = list(dict.fromkeys(expected))
    if verdict == "found" and not expected:
        raise FeedbackError("Say which tool was the right one")
    await _check_known(db, expected)
    feedback = await db.scalar(
        select(SearchFeedback).where(SearchFeedback.search_id == search_id, SearchFeedback.user_sub == user_sub)
    )
    if feedback is not None and feedback.status != "pending":
        raise FeedbackError("This verdict was already reviewed", 409)
    if feedback is None:
        feedback = SearchFeedback(search_id=search_id, user_sub=user_sub, verdict=verdict, expected=expected)
        db.add(feedback)
    feedback.verdict, feedback.expected, feedback.comment = verdict, expected, (comment or "").strip() or None
    await db.commit()
    return feedback


async def review_feedback(
    db: AsyncSession, feedback_id: str, reviewer: str, status: str, expected: list[str] | None
) -> tuple[SearchFeedback, set[str]]:
    """Approve or reject a verdict (an admin may also correct the expected tools). Returns it and the ids of the
    tools whose learned aliases may have changed."""
    feedback = await db.get(SearchFeedback, feedback_id)
    if feedback is None:
        raise FeedbackError("Feedback not found", 404)
    touched = set(feedback.expected) if feedback.status == "approved" else set()
    if expected is not None:
        await _check_known(db, expected)
        feedback.expected = list(dict.fromkeys(expected))
    if status == "approved" and feedback.verdict == "found" and not feedback.expected:
        raise FeedbackError("A verdict that found a tool needs the expected tool")
    feedback.status, feedback.reviewed_by, feedback.reviewed_at = status, reviewer, _now()
    await db.commit()
    if feedback.status == "approved":
        touched |= set(feedback.expected)
    return feedback, touched


# --- What the approved verdicts teach ------------------------------------------------------------------------------


async def approved_rows(db: AsyncSession) -> list[tuple[SearchFeedback, SearchEvent]]:
    rows = await db.execute(
        select(SearchFeedback, SearchEvent)
        .join(SearchEvent, SearchFeedback.search_id == SearchEvent.id)
        .where(SearchFeedback.status == "approved")
        .order_by(SearchFeedback.created_at.desc())
    )
    return [(f, e) for f, e in rows.all()]


async def learned_aliases(db: AsyncSession) -> dict[str, list[str]]:
    """Tool id -> the queries users confirmed it answers (approved verdicts only; the newest, at most
    `MAX_ALIASES_PER_TOOL`). They are indexed with the tool, so that the next person asking the same way finds it."""
    aliases: dict[str, list[str]] = {}
    for feedback, event in await approved_rows(db):
        query = " ".join(event.query.split())
        for tool in feedback.expected:
            known = aliases.setdefault(tool, [])
            if query.lower() not in (a.lower() for a in known) and len(known) < MAX_ALIASES_PER_TOOL:
                known.append(query)
    return aliases


async def dataset(db: AsyncSession) -> list[dict[str, Any]]:
    """The approved verdicts in the format of `backend/eval/queries.json`: usable by `eval.run` and the dashboard."""
    items, seen = [], set()
    for feedback, event in reversed(await approved_rows(db)):
        key = (event.query.lower(), tuple(sorted(feedback.expected)), repr(event.filters))
        if key in seen:
            continue
        seen.add(key)
        item: dict[str, Any] = {
            "query": event.query,
            "expect": feedback.expected,
            "category": "feedback" if feedback.expected else "no-answer",
        }
        if event.filters:
            item["filters"] = event.filters
        items.append(item)
    return items


async def purge_old_events(db: AsyncSession, retention_days: int) -> int:
    """Delete the searches older than the retention, except those with an approved verdict (the dataset)."""
    cutoff = _now() - timedelta(days=retention_days)
    keep = select(SearchFeedback.search_id).where(SearchFeedback.status == "approved")
    result = await db.execute(delete(SearchEvent).where(SearchEvent.created_at < cutoff, SearchEvent.id.not_in(keep)))
    await db.commit()
    return result.rowcount or 0


# --- Dashboard -----------------------------------------------------------------------------------------------------


def _percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


async def stats(db: AsyncSession, days: int) -> dict[str, Any]:
    since = _now() - timedelta(days=days)
    events = (
        await db.scalars(
            select(SearchEvent)
            .where(SearchEvent.created_at >= since)
            .order_by(SearchEvent.created_at)
            .limit(MAX_EVENTS_IN_STATS)
        )
    ).all()
    ids = {e.id for e in events}
    clicks = (
        [c for c in (await db.scalars(select(SearchClick).where(SearchClick.search_id.in_(ids)))).all()] if ids else []
    )
    verdicts = (
        list((await db.scalars(select(SearchFeedback).where(SearchFeedback.search_id.in_(ids)))).all()) if ids else []
    )
    by_event = {e.id: e for e in events}

    per_day: dict[date, Counter] = {since.date() + timedelta(days=i): Counter() for i in range(days + 1)}
    for e in events:
        day = per_day.setdefault(_aware(e.created_at).date(), Counter())
        day["searches"] += 1
        day["zero_results"] += not e.results
    for f in verdicts:
        day = per_day.setdefault(_aware(by_event[f.search_id].created_at).date(), Counter())
        day[f.verdict] += 1
    for c in clicks:
        per_day.setdefault(_aware(by_event[c.search_id].created_at).date(), Counter())["clicks"] += 1

    zero = Counter(" ".join(e.query.lower().split()) for e in events if not e.results)
    missed = Counter()
    for f in verdicts:
        if f.verdict == "not_found":
            missed[(" ".join(by_event[f.search_id].query.lower().split()), tuple(f.expected))] += 1
    chosen = Counter(c.tool for c in clicks) + Counter(t for f in verdicts if f.verdict == "found" for t in f.expected)
    clicked = {c.search_id for c in clicks}
    first_clicks: dict[str, int] = {}
    for c in clicks:
        first_clicks[c.search_id] = min(first_clicks.get(c.search_id, c.rank), c.rank)
    took = [e.took_ms for e in events]
    judged = Counter(f.verdict for f in verdicts)
    pending = await db.scalar(
        select(func.count()).select_from(SearchFeedback).where(SearchFeedback.status == "pending")
    )
    approved = await db.scalar(
        select(func.count()).select_from(SearchFeedback).where(SearchFeedback.status == "approved")
    )

    top_missed, top_chosen = missed.most_common(10), chosen.most_common(10)
    refs = await tool_refs(db, {i for (_, t), _ in top_missed for i in t} | {t for t, _ in top_chosen})

    def share(part: int, whole: int) -> float | None:
        return part / whole if whole else None

    return {
        "days": days,
        "searches": len(events),
        "zero_results": sum(not e.results for e in events),
        "zero_result_rate": share(sum(not e.results for e in events), len(events)),
        "by_mode": dict(Counter(e.mode for e in events)),
        "latency_ms": {"mean": round(statistics.fmean(took)) if took else 0, "p95": _percentile(took, 0.95)},
        "clicks": len(clicks),
        "click_rate": share(len(clicked), len(events)),
        "click_mrr": statistics.fmean(1 / r for r in first_clicks.values()) if first_clicks else None,
        "verdicts": {"found": judged["found"], "not_found": judged["not_found"]},
        "found_rate": share(judged["found"], judged["found"] + judged["not_found"]),
        "dataset": {"pending": pending or 0, "approved": approved or 0},
        "by_day": [
            {
                "date": day.isoformat(),
                "searches": c["searches"],
                "zero_results": c["zero_results"],
                "found": c["found"],
                "not_found": c["not_found"],
                "clicks": c["clicks"],
            }
            for day, c in sorted(per_day.items())
        ],
        "top_zero_result_queries": [{"query": q, "count": n} for q, n in zero.most_common(10)],
        "top_missed": [{"query": q, "expected": [refs[i] for i in t], "count": n} for (q, t), n in top_missed],
        "tools_chosen": [{"tool": refs[t], "count": n} for t, n in top_chosen],
    }
