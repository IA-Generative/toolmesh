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


def stem(token: str) -> str:
    """Strip a plural `s` (English and French alike) so that "tickets" matches "ticket"."""
    return token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token


def tokenize(text: str) -> list[str]:
    """Words without accents, case, plural `s` or stop words, identifiers split: `findPetsByStatus` -> find pet by
    statu... -> ["find", "pet", "statu"]; "Météo d'une ville" -> ["meteo", "ville"]."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)  # camelCase, before the case is lost
    folded = unicodedata.normalize("NFKD", spaced).encode("ascii", "ignore").decode().lower()
    return [stem(t) for t in re.findall(r"[a-z0-9]+", folded) if len(t) > 1 and t not in STOP_WORDS]


def _index(token: str) -> int:
    return zlib.crc32(token.encode())


def encode_document(parts: str | list[tuple[str, float]]) -> tuple[list[int], list[float]]:
    """Keyword vector of a text, or of (text, weight) parts: a word found in a part counts `weight` times."""
    counts: Counter[str] = Counter()
    for text, weight in [(parts, 1.0)] if isinstance(parts, str) else parts:
        for token in tokenize(text):
            counts[token] += weight
    items = sorted((_index(t), n * (K1 + 1) / (n + K1)) for t, n in counts.items())
    return [i for i, _ in items], [v for _, v in items]


def encode_query(text: str) -> tuple[list[int], list[float]]:
    indices = sorted({_index(t) for t in tokenize(text)})
    return indices, [1.0] * len(indices)
