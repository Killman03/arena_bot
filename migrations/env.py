from logging.config import fileConfig
import os
import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

from app.db.base import Base

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


def _get_database_url() -> str:
    """Resolve database URL from env or alembic.ini and normalize to async driver."""
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url or url.startswith("driver://"):
        raise RuntimeError(
            "DATABASE_URL is not set and alembic.ini has a placeholder. "
            "Set env var DATABASE_URL or update alembic.ini [sqlalchemy.url].\n"
            "Example: postgresql+asyncpg://user:pass@localhost:5432/dbname"
        )
    if url.startswith("postgresql://"):
        # enforce async driver for SQLAlchemy async engine
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # keep alembic's config in sync (offline mode reads from here)
    config.set_main_option("sqlalchemy.url", url)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode with URL only."""
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Configure context and run migrations inside a transaction (sync)."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async engine."""
    url = _get_database_url()
    connectable: AsyncEngine = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
