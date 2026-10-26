"""How a tool is turned into text for the two indexes.

Identifiers are the weak spot of both: an embedding model reads `findPetsByStatus` as one rare word, and a keyword index
cannot match "pets" to it. So the name is split into words (`find pets by status`), and what the tool takes as input
(parameter names and descriptions) is searched too: "ville" finds a tool through its `city` parameter."""

import re

from app.db.models import Source, Tool

MAX_PARAMS = 12
MAX_PARAM_DESCRIPTION = 120


def humanize(identifier: str) -> str:
    """`findPetsByStatus`, `get_weather`, `/pet/{petId}` -> `find pets by status`, `get weather`, `pet pet id`."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier)
    return " ".join(re.findall(r"[A-Za-z0-9]+", spaced)).lower()


def parameters(tool: Tool) -> list[tuple[str, str]]:
    """(humanized name, description) of the inputs of the tool, at most `MAX_PARAMS`."""
    properties = (tool.input_schema or {}).get("properties") or {}
    found = []
    for name, schema in list(properties.items())[:MAX_PARAMS]:
        schema = schema if isinstance(schema, dict) else {}
        description = str(schema.get("description") or "")[:MAX_PARAM_DESCRIPTION]
        found.append((humanize(name), description))
    return found


def sparse_parts(source: Source, tool: Tool) -> list[tuple[str, float]]:
    """(text, weight) pairs for the keyword vector: what is in the name counts most, then the tags."""
    params = parameters(tool)
    route = f"{tool.method} {tool.path}" if tool.method and tool.path else ""
    return [
        (humanize(tool.name), 3.0),
        (" ".join(tool.tags or []), 2.0),
        (tool.description, 1.0),
        (humanize(route), 1.0),
        (" ".join(f"{n} {d}" for n, d in params), 1.0),
        (f"{humanize(source.name)} {source.description or ''}", 1.0),
    ]


def dense_text(source: Source, tool: Tool) -> str:
    """The sentence-like text embedded for a tool: short, in natural language, most telling parts first."""
    lines = [f"{humanize(tool.name)}. {tool.description}".strip()]
    if tool.tags:
        lines.append("Tags: " + ", ".join(tool.tags))
    params = parameters(tool)
    if params:
        lines.append("Inputs: " + "; ".join(f"{n} ({d})" if d else n for n, d in params))
    if tool.method and tool.path:
        lines.append(f"Endpoint: {tool.method} {humanize(tool.path)}")
    lines.append(f"Source: {humanize(source.name)}" + (f" - {source.description}" if source.description else ""))
    return "\n".join(lines)
