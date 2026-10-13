"""Read the project version straight from pyproject.toml.

Avoids depending on the package being installed (editable or not) so the
version is correct in dev, tests, and the built image alike.
"""

import tomllib
from functools import lru_cache
from pathlib import Path

_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


@lru_cache
def get_version() -> str:
    with _PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
