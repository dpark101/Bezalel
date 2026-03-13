"""
Bezalel.AI — Alembic Migration Environment

Configures Alembic to work with the async SQLAlchemy engine used by the
FastAPI backend. Supports both online (connected) and offline (SQL script)
migration modes.
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Add the backend directory to sys.path so we can import app modules.
# This assumes alembic.ini lives in the backend root alongside config.py.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings          # noqa: E402 — must come after path fix
from database import Base            # noqa: E402

# Import all model modules so that Base.metadata is fully populated.
# Add new model files here as they are created.
import models  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Set the SQLAlchemy URL from the application settings.
# Convert the async URL (postgresql+asyncpg://) to a sync URL for Alembic's
# offline mode, while keeping async for online mode.
ASYNC_URL = settings.DATABASE_URL
SYNC_URL = ASYNC_URL.replace("+asyncpg", "")

config.set_main_option("sqlalchemy.url", SYNC_URL)

# Interpret the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object for autogenerate support.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations — generates SQL without a live database connection.
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine. Calls to
    context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations — connects to the database and applies changes.
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a database connection context."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine for compatibility with asyncpg."""
    configuration = config.get_section(config.config_ini_section, {})
    # Override with the async URL for the actual connection.
    configuration["sqlalchemy.url"] = ASYNC_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point — choose offline or online mode.
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
