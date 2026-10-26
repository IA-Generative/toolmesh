from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.db.models import Source, Tool
from app.schemas import SourceIn, ToolIn, ToolOut


def is_visible(source: Source, user: User) -> bool:
    return source.required_role is None or source.required_role in user.roles


def tool_out(source: Source, tool: Tool) -> ToolOut:
    return ToolOut(
        name=tool.name,
        description=tool.description,
        source=source.name,
        type=source.type,
        tags=tool.tags,
        source_url=source.openapi_url or source.url,
        method=tool.method,
        path=tool.path,
        input_schema=tool.input_schema,
        required_role=source.required_role,
    )


async def visible_tools(db: AsyncSession, user: User) -> list[ToolOut]:
    sources = (await db.scalars(select(Source).order_by(Source.name))).all()
    return [tool_out(s, t) for s in sources if is_visible(s, user) for t in s.tools if t.enabled]


async def name_conflicts(db: AsyncSession, payload: SourceIn) -> list[str]:
    """Names of the source and tools in `payload` that are already taken."""
    tool_names = [t.name for t in payload.tools] or ([payload.name] if payload.type == "skill" else [])
    taken = []
    if await db.scalar(select(Source.id).where(Source.name == payload.name)):
        taken.append(f"source '{payload.name}'")
    for name in tool_names:
        if await db.scalar(select(Tool.id).where(Tool.name == name)):
            taken.append(f"tool '{name}'")
    return taken


def build_source(payload: SourceIn, created_by: str) -> Source:
    source = Source(
        **payload.model_dump(exclude={"tools", "tags"}),
        created_by=created_by,
    )
    tools = payload.tools
    if not tools and payload.type == "skill":
        # A skill is its own single tool.
        tools = [ToolIn(name=payload.name, description=payload.description or "", tags=payload.tags)]
    source.tools = [Tool(**t.model_dump()) for t in tools]
    return source


async def dedupe_tool_names(
    db: AsyncSession, tools: list[ToolIn], source_name: str, exclude_source_id: str | None = None
) -> list[ToolIn]:
    """Discovered tool names must be unique across sources: a clash is renamed `<source>.<tool>`."""
    query = select(Tool.name).where(Tool.name.in_([t.name for t in tools]))
    if exclude_source_id:
        query = query.where(Tool.source_id != exclude_source_id)
    taken = set((await db.scalars(query)).all())
    return [
        t.model_copy(update={"name": f"{source_name}.{t.name}"[:100], "remote_name": t.remote_name or t.name})
        if t.name in taken
        else t
        for t in tools
    ]


def sync_tools(source: Source, discovered: list[ToolIn]) -> None:
    """Make the source's tools match `discovered` by name, keeping the `enabled` flag of those that stay."""
    wanted = {t.name: t for t in discovered}
    for tool in list(source.tools):
        if tool.name not in wanted:
            source.tools.remove(tool)
            continue
        incoming = wanted.pop(tool.name)
        tool.description, tool.tags, tool.method = incoming.description, incoming.tags, incoming.method
        tool.path, tool.input_schema = incoming.path, incoming.input_schema
        tool.remote_name = incoming.remote_name
    source.tools.extend(Tool(**t.model_dump()) for t in wanted.values())
