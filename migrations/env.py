import asyncio
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.infrastructure.config import load_config
from app.infrastructure.db.base import Base
from app.infrastructure.db.transaction.model import Transaction
# Import all models to ensure they're registered with the Base
from app.infrastructure.db.wallet.model import Wallet

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
envConfig = load_config()
async_dsn = re.sub(
    r"^postgresql(\+[\w]+)?://", "postgresql+asyncpg://", envConfig.postgres_dsn
)
# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

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


def run_migrations_online():
    connectable = create_async_engine(
        async_dsn,
        poolclass=pool.NullPool,
    )

    async def run():
        async with connectable.connect() as async_connection:

            def do_run_migrations(sync_connection):
                context.configure(
                    connection=sync_connection,
                    target_metadata=target_metadata,
                    dialect_opts={"paramstyle": "named"},
                )
                with context.begin_transaction():
                    context.run_migrations()

            await async_connection.run_sync(do_run_migrations)

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
