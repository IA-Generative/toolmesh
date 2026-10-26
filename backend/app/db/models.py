from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _new_id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Source(Base):
    """Where tools come from: an MCP server, an API, or a skill (a single tool)."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(10))  # mcp | api | skill
    description: Mapped[str | None] = mapped_column(Text)
    # Version of the API (`info.version` of its OpenAPI document) or of the MCP server, read at the discovery.
    version: Mapped[str | None] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(2048))
    openapi_url: Mapped[str | None] = mapped_column(String(2048))
    auth_mode: Mapped[str] = mapped_column(String(20), default="none")  # token_exchange | none
    audience: Mapped[str | None] = mapped_column(String(255))
    # Glob patterns on "METHOD /path" selecting the endpoints of an API that become tools.
    endpoint_include: Mapped[list[str]] = mapped_column(JSON, default=list)
    endpoint_exclude: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Realm role required to see the source's tools; None means any authenticated caller.
    required_role: Mapped[str | None] = mapped_column(String(100))
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tools: Mapped[list["Tool"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", lazy="selectin", order_by="Tool.name"
    )


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    # Unique across sources: the name is how the front addresses a tool.
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(2048))
    input_schema: Mapped[dict | None] = mapped_column(JSON)
    # Name the tool has on its server when it was renamed here to stay unique (`<source>.<tool>`); None otherwise.
    remote_name: Mapped[str | None] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    source: Mapped[Source] = relationship(back_populates="tools")


class SearchEvent(Base):
    """A search made through GET /api/me/tools/search with a query: the base of the quality statistics."""

    __tablename__ = "search_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_sub: Mapped[str] = mapped_column(String(255))
    query: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(10))
    results: Mapped[list[str]] = mapped_column(JSON, default=list)
    took_ms: Mapped[int] = mapped_column(Integer, default=0)


class SearchClick(Base):
    """The user opened a result: an implicit sign that it was the one looked for."""

    __tablename__ = "search_clicks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_events.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(100))
    rank: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SearchFeedback(Base):
    """What a user says about a search. Once an admin approves it, it is part of the dataset and teaches the index."""

    __tablename__ = "search_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_events.id", ondelete="CASCADE"), index=True)
    user_sub: Mapped[str] = mapped_column(String(255))
    verdict: Mapped[str] = mapped_column(String(10))  # found | not_found
    # The tools that were the right answer. Empty with `not_found`: the catalogue has nothing for this query.
    expected: Mapped[list[str]] = mapped_column(JSON, default=list)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | approved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
