import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


async def run_migrations(database_url: str) -> None:
    # Alembic's async env runs its own event loop, so it needs a thread of its own.
    await asyncio.to_thread(command.upgrade, alembic_config(database_url), "head")
