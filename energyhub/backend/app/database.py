from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_contracts() -> None:
    """Migraciones ligeras para no perder los datos de versiones anteriores."""
    inspector = inspect(engine)
    if "contracts" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("contracts")}
    additions = {
        "tariff_profile_id": "VARCHAR(60) DEFAULT 'pepe_variable'",
        "has_pepephone_discount": "BOOLEAN DEFAULT 0",
        "bono_social_category": "VARCHAR(20) DEFAULT 'none'",
        "bono_social_energy_limit_kwh": "FLOAT DEFAULT 1587",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE contracts ADD COLUMN {name} {definition}"))
        if "tariff_profile_id" not in columns:
            connection.execute(
                text(
                    "UPDATE contracts SET tariff_profile_id = 'manual' "
                    "WHERE lower(provider) NOT LIKE '%pepe%'"
                )
            )


def _migrate_devices() -> None:
    inspector = inspect(engine)
    if "devices" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("devices")}
    if "energy_entity_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE devices ADD COLUMN energy_entity_id VARCHAR(160)")
            )


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_contracts()
    _migrate_devices()
