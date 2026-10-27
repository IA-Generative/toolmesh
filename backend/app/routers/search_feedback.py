from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import searchlog
from app.auth import CurrentUser, require_role
from app.config import Settings, get_settings
from app.db.models import SearchEvent, SearchFeedback, Source, Tool
from app.db.session import get_db
from app.toolsearch import ToolIndex, get_index, sync_source_with_feedback
from app.toolsearch.embeddings import EmbeddingError
from app.toolsearch.evaluation import evaluate

DB = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

# What a user does with the results of a search.
user_router = APIRouter(prefix="/api/search", tags=["search quality"])
# What an admin does with it: follow the quality, curate the dataset.
admin_router = APIRouter(prefix="/api/admin/search", tags=["search quality"], dependencies=[require_role("admin")])


def _fail(exc: searchlog.FeedbackError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


class ClickIn(BaseModel):
    tool_id: str = Field(max_length=32)
    rank: int = Field(ge=1, le=100)


class FeedbackIn(BaseModel):
    verdict: Literal["found", "not_found"]
    # Ids of the tools that were the right answer. With `not_found`, empty means the catalogue has nothing for it.
    expected: list[str] = Field(default=[], max_length=10)
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    id: str
    search_id: str
    verdict: str
    expected: list[str]
    comment: str | None
    status: str


@user_router.post("/{search_id}/click", status_code=status.HTTP_204_NO_CONTENT)
async def click(search_id: str, payload: ClickIn, user: CurrentUser, db: DB) -> Response:
    """A result of the search was opened."""
    try:
        await searchlog.record_click(db, search_id, user.sub, payload.tool_id, payload.rank)
    except searchlog.FeedbackError as exc:
        raise _fail(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@user_router.post("/{search_id}/feedback", status_code=status.HTTP_201_CREATED)
async def feedback(search_id: str, payload: FeedbackIn, user: CurrentUser, db: DB) -> FeedbackOut:
    """Say whether the search found what was looked for, and which tool was the right one. An admin reviews it before
    it becomes part of the dataset."""
    try:
        saved = await searchlog.submit_feedback(
            db, search_id, user.sub, payload.verdict, payload.expected, payload.comment
        )
    except searchlog.FeedbackError as exc:
        raise _fail(exc) from exc
    return FeedbackOut(
        id=saved.id,
        search_id=saved.search_id,
        verdict=saved.verdict,
        expected=saved.expected,
        comment=saved.comment,
        status=saved.status,
    )


@admin_router.get("/stats")
async def stats(db: DB, days: Annotated[int, Query(ge=1, le=365)] = 30) -> dict[str, Any]:
    return await searchlog.stats(db, days)


class ToolRef(BaseModel):
    id: str
    name: str
    source: str | None  # None: the tool was deleted since


class ReviewItem(BaseModel):
    id: str
    created_at: datetime
    query: str
    filters: dict[str, Any]
    mode: str
    results: list[ToolRef]
    verdict: str
    expected: list[str]  # tool ids
    comment: str | None
    status: str


@admin_router.get("/feedback")
async def list_feedback(
    db: DB,
    status_: Annotated[Literal["pending", "approved", "rejected"], Query(alias="status")] = "pending",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ReviewItem]:
    rows = await db.execute(
        select(SearchFeedback, SearchEvent)
        .join(SearchEvent, SearchFeedback.search_id == SearchEvent.id)
        .where(SearchFeedback.status == status_)
        .order_by(SearchFeedback.created_at.desc())
        .limit(limit)
    )
    rows = rows.all()
    refs = await searchlog.tool_refs(db, {i for _, e in rows for i in e.results})
    return [
        ReviewItem(
            id=f.id,
            created_at=f.created_at,
            query=e.query,
            filters=e.filters,
            mode=e.mode,
            results=[ToolRef(**refs[i]) for i in e.results],
            verdict=f.verdict,
            expected=f.expected,
            comment=f.comment,
            status=f.status,
        )
        for f, e in rows
    ]


class ReviewIn(BaseModel):
    status: Literal["approved", "rejected", "pending"]
    # An admin may correct which tools were the right answer.
    expected: list[str] | None = Field(default=None, max_length=10)


@admin_router.patch("/feedback/{feedback_id}")
async def review(feedback_id: str, payload: ReviewIn, user: CurrentUser, db: DB, settings: AppSettings) -> FeedbackOut:
    """Approve (it joins the dataset and teaches the index), reject or reopen a verdict."""
    try:
        saved, touched = await searchlog.review_feedback(db, feedback_id, user.sub, payload.status, payload.expected)
    except searchlog.FeedbackError as exc:
        raise _fail(exc) from exc
    if touched and get_index(settings) is not None:  # the aliases of these tools changed: index them again
        owners = select(Tool.source_id).where(Tool.id.in_(touched))  # no DISTINCT on the rows: JSON has no equality
        sources = (await db.scalars(select(Source).where(Source.id.in_(owners)))).all()
        for source in sources:
            await sync_source_with_feedback(settings, db, source)
    return FeedbackOut(
        id=saved.id,
        search_id=saved.search_id,
        verdict=saved.verdict,
        expected=saved.expected,
        comment=saved.comment,
        status=saved.status,
    )


@admin_router.get("/dataset")
async def dataset(db: DB) -> list[dict[str, Any]]:
    """The approved verdicts, in the format of `backend/eval/queries.json`."""
    return await searchlog.dataset(db)


class EvaluationOut(BaseModel):
    queries: int
    metrics: dict[str, dict[str, float | None]]


@admin_router.post("/evaluate")
async def run_evaluation(db: DB, settings: AppSettings) -> EvaluationOut:
    """Measure the search on the dataset, over a temporary index of the registry built *without* the learned aliases:
    what the strategy itself achieves on the real queries, not what it was taught by the same queries."""
    queries = await searchlog.dataset(db)
    if not queries:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The dataset is empty: approve some verdicts first")
    index = ToolIndex(settings, AsyncQdrantClient(":memory:"))
    try:
        await index.reindex(list((await db.scalars(select(Source))).all()))
        return EvaluationOut(queries=len(queries), metrics=await evaluate(index, queries, ["admin"]))
    except EmbeddingError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
