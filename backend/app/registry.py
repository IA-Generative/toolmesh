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
