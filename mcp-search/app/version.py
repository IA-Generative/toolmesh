import tomllib
from pathlib import Path


def get_version() -> str:
    """Version of the server: the one release-please keeps in pyproject.toml."""
    try:
        return tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())["project"][
            "version"
        ]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0.0.0"
