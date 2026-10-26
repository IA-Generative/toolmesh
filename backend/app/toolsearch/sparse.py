"""Keyword vectors for Qdrant: hashed tokens weighted by a saturating term frequency (BM25 without length
normalisation). Qdrant applies the IDF itself (`Modifier.IDF`), so the weights here only depend on the text."""

import re
import unicodedata
import zlib
from collections import Counter

K1 = 1.2

STOP_WORDS = frozenset(
    "a an and are as at be by for from has in is it its of on or that the to was with "
    "au aux ce ces dans de des du elle en est et il je la le les leur ma mon ne nos notre nous on ou par pas pour qu "
    "que qui sa se ses son sur ta te tes ton tu un une vos votre vous".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-cased words without accents or stop words, e.g. "Météo d'une ville" -> ["meteo", "ville"]."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [t for t in re.findall(r"[a-z0-9]+", folded) if len(t) > 1 and t not in STOP_WORDS]


def _index(token: str) -> int:
    return zlib.crc32(token.encode())


def encode_document(text: str) -> tuple[list[int], list[float]]:
    counts = Counter(tokenize(text))
    items = sorted((_index(t), n * (K1 + 1) / (n + K1)) for t, n in counts.items())
    return [i for i, _ in items], [v for _, v in items]


def encode_query(text: str) -> tuple[list[int], list[float]]:
    indices = sorted({_index(t) for t in tokenize(text)})
    return indices, [1.0] * len(indices)
