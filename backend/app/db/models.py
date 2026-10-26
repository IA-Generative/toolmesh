from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
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
