"""Measure the quality of the tool search on a fixed catalogue and a fixed set of queries.

    uv run python -m eval.run                       # keywords only
    uv run python -m eval.run --embedder api        # the embeddings API configured with TOOLMESH_EMBEDDINGS_*
    uv run --with fastembed python -m eval.run \
        --embedder fastembed:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

Each query is run in three rankings (keywords, dense vectors, both fused) through the same code as the API. The metrics:
hit@1 and hit@3 (an expected tool is among the first 1 / 3 results), MRR (mean of 1 / rank of the first expected tool).
Use it to compare embedding models, prefixes and any change of how tools are turned into text before shipping it.
"""

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.config import Settings
from app.db.models import Source, Tool
from app.toolsearch import index as index_module
from app.toolsearch.evaluation import score
from app.toolsearch.index import Filters, ToolIndex
from app.toolsearch.text import humanize, parameters

HERE = Path(__file__).parent
ROLES = ["user", "admin"]


def load_sources() -> list[Source]:
    sources = []
    for i, raw in enumerate(json.loads((HERE / "catalog.json").read_text())):
        source = Source(
            id=f"{i:032x}",
            name=raw["name"],
            type=raw["type"],
            description=raw.get("description"),
            version=raw.get("version"),
            required_role=raw.get("required_role"),
            created_by="eval",
        )
        source.tools = [
            Tool(
                id=f"{i:016x}{j:016x}",
                name=t["name"],
                description=t["description"],
                tags=t["tags"],
                method=t["method"],
                path=t["path"],
                input_schema=t["input_schema"],
                enabled=True,
            )
            for j, t in enumerate(raw["tools"])
        ]
        sources.append(source)
    return sources


def fastembed_transport(model_name: str):
    """A stand-in for the embeddings API that runs a local model (development only: `uv run --with fastembed`)."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name)

    async def request(settings: Settings, texts: list[str], client=None) -> list[list[float]]:
        return await asyncio.get_running_loop().run_in_executor(None, lambda: [v.tolist() for v in model.embed(texts)])

    return request


def _name_description(source: Source, tool: Tool) -> str:
    return f"{humanize(tool.name)}. {tool.description}"


def _with_tags(source: Source, tool: Tool) -> str:
    return _name_description(source, tool) + (". " + ", ".join(tool.tags) if tool.tags else "")


def _with_params(source: Source, tool: Tool) -> str:
    names = ", ".join(n for n, _ in parameters(tool))
    return _with_tags(source, tool) + (f". Inputs: {names}" if names else "")


def _description_first(source: Source, tool: Tool) -> str:
    return f"{tool.description} ({humanize(tool.name)})"


# Alternatives to `app.toolsearch.text.dense_text`, to compare with `--dense-text`.
DENSE_TEXTS = {
    "name+description": _name_description,
    "name+description+tags": _with_tags,
    "name+description+tags+inputs": _with_params,
    "description-first": _description_first,
}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default="none", help="none | api | fastembed:<model>")
    parser.add_argument("--query-prefix", default="")
    parser.add_argument("--document-prefix", default="")
    parser.add_argument("--dense-text", default="current", help="how a tool is turned into text for the dense vector")
    parser.add_argument("--dense-weight", type=float, default=Settings().search_dense_weight)
    parser.add_argument("--keyword-weight", type=float, default=Settings().search_keyword_weight)
    parser.add_argument("--rrf-k", type=int, default=Settings().search_rrf_k)
    parser.add_argument("--name-bonus", type=float, default=Settings().search_name_bonus)
    parser.add_argument("--min-dense-score", type=float, default=None)
    parser.add_argument("--verbose", action="store_true", help="show the queries whose expected tool is not first")
    args = parser.parse_args()

    tuning = {
        "search_dense_weight": args.dense_weight,
        "search_keyword_weight": args.keyword_weight,
        "search_rrf_k": args.rrf_k,
        "search_name_bonus": args.name_bonus,
        "search_min_dense_score": args.min_dense_score,
    }
    settings = Settings(
        embeddings_query_prefix=args.query_prefix, embeddings_document_prefix=args.document_prefix, **tuning
    )
    if args.embedder.startswith("fastembed:"):
        settings.embeddings_url, settings.embeddings_model = "local", args.embedder.split(":", 1)[1]
        index_module.embed_transport = fastembed_transport(settings.embeddings_model)
        from app.toolsearch import embeddings

        embeddings._request = index_module.embed_transport
    elif args.embedder == "api":
        env = Settings()
        settings = Settings(
            embeddings_query_prefix=args.query_prefix or env.embeddings_query_prefix,
            embeddings_document_prefix=args.document_prefix or env.embeddings_document_prefix,
            **tuning,
        )
    if args.dense_text != "current":
        index_module.dense_text = DENSE_TEXTS[args.dense_text]
    index = ToolIndex(settings, AsyncQdrantClient(":memory:"))
    await index.reindex(load_sources())

    queries = json.loads((HERE / "queries.json").read_text())
    modes = ["keyword", "dense", "hybrid"] if index.dense else ["keyword"]
    totals: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    by_category: dict[tuple[str, str], list[tuple[float, float, float]]] = defaultdict(list)
    misses: list[str] = []
    for item in queries:
        flt = item.get("filters", {})
        filters = Filters(flt.get("type"), tuple(flt.get("tags", ())), flt.get("source"), flt.get("version"))
        for mode in modes:
            ranking = await index.search(item["query"], ROLES, filters, 10, only=None if mode == "hybrid" else mode)
            result = score(ranking, item["expect"])
            totals[mode].append(result)
            by_category[(item["category"], mode)].append(result)
            if mode == modes[-1] and result[0] < 1:
                misses.append(f"  {item['query']!r} -> expected {item['expect']}, got {ranking[:3]}")

    def mean(rows: list[tuple[float, float, float]], i: int) -> float:
        return sum(r[i] for r in rows) / len(rows)

    gap: dict[str, list[float]] = {"relevant": [], "no-answer": []}
    if index.dense:
        for item in queries:
            flt = item.get("filters", {})
            filters = Filters(flt.get("type"), tuple(flt.get("tags", ())), flt.get("source"), flt.get("version"))
            hits = await index.search_scored(item["query"], ROLES, filters, 10, only="dense")
            scores = [h.dense_score for h in hits if h.dense_score is not None and h.name in item["expect"]]
            if item["expect"] and scores:
                gap["relevant"].append(max(scores))
            elif not item["expect"] and hits:
                gap["no-answer"].append(max(h.dense_score for h in hits if h.dense_score is not None))

    print(f"{len(queries)} queries, {sum(len(s.tools) for s in load_sources())} tools, embedder: {args.embedder}\n")
    print(f"{'':16}" + "".join(f"{m:>26}" for m in modes))
    print(f"{'':16}" + "".join(f"{'hit@1':>9}{'hit@3':>9}{'MRR':>8}" for _ in modes))
    for category in dict.fromkeys(i["category"] for i in queries):
        cells = "".join(
            "".join(f"{mean(by_category[(category, m)], i):{w}.2f}" for i, w in enumerate((9, 9, 8))) for m in modes
        )
        print(f"{category:16}{cells}")
    answered = {m: [r for item, r in zip(queries, rows, strict=True) if item["expect"]] for m, rows in totals.items()}
    for label, rows in (("with an answer", answered), ("ALL", totals)):
        if label == "ALL" and rows is answered:
            continue
        print(
            f"{label:16}"
            + "".join("".join(f"{mean(rows[m], i):{w}.2f}" for i, w in enumerate((9, 9, 8))) for m in modes)
        )
    if gap["no-answer"] and gap["relevant"]:
        relevant, absent = sorted(gap["relevant"]), sorted(gap["no-answer"])
        print(
            "\ndense cosine score of the right tool (relevant queries): "
            f"min {relevant[0]:.2f}, 10th percentile {relevant[len(relevant) // 10]:.2f}, "
            f"median {relevant[len(relevant) // 2]:.2f}\n"
            f"best dense score of a query without answer: median {absent[len(absent) // 2]:.2f}, max {absent[-1]:.2f}\n"
            "-> a --min-dense-score between the two keeps the right tools and drops unrelated questions"
        )
    if args.verbose and misses:
        print(f"\nnot first in the last ranking ({modes[-1]}):")
        print("\n".join(misses))


if __name__ == "__main__":
    asyncio.run(main())
