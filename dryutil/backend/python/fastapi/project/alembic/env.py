import asyncio
import os
import importlib.util
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from dotenv import load_dotenv

load_dotenv()

# Load models via importlib (folder name starts with digit)
def _load_index():
    _path = os.path.join(os.path.dirname(__file__), "..", "src", "shared", "utility", "l", "706", "index.py")
    spec  = importlib.util.spec_from_file_location("xshop_idx", os.path.abspath(_path))
    mod   = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_load_index()  # registers all models into Base.metadata

from src.db_config import Base

config = context.config
# %% escaping needed for configparser when URL has % chars
_db_url = os.getenv("DATABASE_URL", "").replace("%", "%%")
config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
