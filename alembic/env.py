import asyncio
from logging.config import fileConfig

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from app.core.config import settings
from app.db.base import Base

# Import every model module here so Base.metadata sees all tables before
# autogenerate (or the initial hand-written migration) reads it.
import app.models.user  # noqa: F401,E402
import app.models.sos_session  # noqa: F401,E402
import app.models.push_subscription  # noqa: F401,E402

config = context.config
# Deliberately NOT using config.set_main_option()/get_section() for the URL:
# configparser treats "%" as interpolation syntax, and a URL-encoded DB
# password (e.g. containing "%40" for "@") breaks it. settings.DATABASE_URL
# is used directly below instead, bypassing configparser entirely.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# PostGIS creates its own system tables/views once the extension is enabled.
# GeoAlchemy2 makes them visible to reflection, so without this filter
# `alembic revision --autogenerate` would propose dropping them on every run.
POSTGIS_SYSTEM_TABLES = {
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in POSTGIS_SYSTEM_TABLES:
        return False
    return True


# GeoAlchemy2's reflected Geography/Geometry types routinely don't compare
# equal to the declared model type even when the column is identical, which
# makes autogenerate propose a bogus "alter column type" on every run once
# there's more than one geometry-holding table. Always hand-write migrations
# that touch a geometry column; never trust autogenerate's diff for them.
def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    if isinstance(metadata_type, (Geography, Geometry)):
        return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=compare_type,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=compare_type,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
