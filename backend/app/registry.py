from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User
from app.db.models import Source, Tool
from app.schemas import SourceIn, ToolIn, ToolOut
from app.toolsearch.sparse import tokenize


def is_visible(source: Source, user: User) -> bool:
    return source.required_role is None or source.required_role in user.roles


def tool_out(source: Source, tool: Tool) -> ToolOut:
    return ToolOut(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        source=source.name,
        source_version=source.version,
        type=source.type,
        tags=tool.tags,
        source_url=source.openapi_url or source.url,
        method=tool.method,
        path=tool.path,
        input_schema=tool.input_schema,
        auth_mode=source.auth_mode,
        audience=source.audience,
        required_role=source.required_role,
    )


async def visible_tools(db: AsyncSession, user: User) -> list[ToolOut]:
    sources = (await db.scalars(select(Source).order_by(Source.name))).all()
    return [tool_out(s, t) for s in sources if is_visible(s, user) for t in s.tools if t.enabled]


async def name_conflicts(db: AsyncSession, payload: SourceIn) -> list[str]:
    """What in `payload` cannot be registered: a source name already taken, a tool declared twice. Tool names only
    have to be unique within their source."""
    taken = []
    if await db.scalar(select(Source.id).where(Source.name == payload.name)):
        taken.append(f"source '{payload.name}'")
    names = [t.name for t in payload.tools]
    taken.extend(f"tool '{n}' declared twice" for n in dict.fromkeys(n for n in names if names.count(n) > 1))
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
    source.tools.extend(Tool(**t.model_dump()) for t in wanted.values())


def filter_tools(
    tools: list[ToolOut],
    query: str = "",
    type: str | None = None,
    tags: tuple[str, ...] = (),
    source: str | None = None,
    version: str | None = None,
) -> list[ToolOut]:
    """Keyword match and filters on the registry itself, used when no search index is available. With a query, the
    tools matching every word are kept, those with the words in their name first."""
    kept = [
        t
        for t in tools
        if (not type or t.type == type)
        and (not source or t.source == source)
        and (not version or t.source_version == version)
        and all(tag in t.tags for tag in tags)
    ]
    words = set(tokenize(query))
    if not words:
        return kept
    ranked = []
    for tool in kept:
        in_name = set(tokenize(tool.name.replace("_", " ")))
        text = in_name | set(tokenize(" ".join([tool.description, " ".join(tool.tags), tool.source])))
        if words <= text:
            ranked.append((len(words & in_name), tool))  # a word found in the name counts more
    return [t for _, t in sorted(ranked, key=lambda r: -r[0])]
