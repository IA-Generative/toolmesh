"""Metrics of the tool search over a set of queries with known answers (shared by `eval/run.py` and the dashboard)."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from app.toolsearch.index import Filters, ToolIndex


def score(ranking: Sequence[str], expected: Sequence[str]) -> tuple[float, float, float]:
    """(hit@1, hit@3, reciprocal rank) of a ranking. With no expected tool the right answer is no result at all."""
    if not expected:
        return (float(not ranking),) * 3
    ranks = [ranking.index(e) + 1 for e in expected if e in ranking]
    first = min(ranks) if ranks else None
    return (float(first == 1), float(first is not None and first <= 3), 1 / first if first else 0.0)


def filters_of(item: dict[str, Any]) -> Filters:
    flt = item.get("filters") or {}
    return Filters(flt.get("type"), tuple(flt.get("tags", ())), flt.get("source"), flt.get("version"))


async def evaluate(index: ToolIndex, queries: list[dict[str, Any]], roles: list[str]) -> dict[str, dict[str, float]]:
    """Mean hit@1, hit@3 and MRR per ranking (`keyword`, plus `dense` and `hybrid` when the index has embeddings), over
    the queries with an answer; `no_answer` is the share of the queries with none that got no result."""
    modes = ["keyword", "dense", "hybrid"] if index.dense else ["keyword"]
    rows: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    silent: dict[str, list[float]] = defaultdict(list)
    for item in queries:
        for mode in modes:
            ranking = await index.search(
                item["query"], roles, filters_of(item), 10, only=None if mode == "hybrid" else mode
            )
            result = score(ranking, item["expect"])
            (rows if item["expect"] else silent)[mode].append(result if item["expect"] else result[0])
    report: dict[str, dict[str, float]] = {}
    for mode in modes:
        n = len(rows[mode])
        report[mode] = {
            "queries": n,
            "hit1": sum(r[0] for r in rows[mode]) / n if n else 0.0,
            "hit3": sum(r[1] for r in rows[mode]) / n if n else 0.0,
            "mrr": sum(r[2] for r in rows[mode]) / n if n else 0.0,
            "no_answer": sum(silent[mode]) / len(silent[mode]) if silent[mode] else None,
        }
    return report
