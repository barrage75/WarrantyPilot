from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.settings import AppSettings, get_settings
from app.core.tables import Base


def make_engine(database_url: str) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "isolation_level": None,
            "timeout": 30,
        }
        if database_url.endswith(":memory:") or database_url.endswith("/:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            database_path = database_url.removeprefix("sqlite:///")
            if database_path and database_path != ":memory:":
                Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        @event.listens_for(engine, "begin")
        def begin_immediate(connection: Any) -> None:
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def install_event_triggers(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS events_no_update
                BEFORE UPDATE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS events_no_delete
                BEFORE DELETE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'events are append-only');
                END
                """
            )
        )


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    install_event_triggers(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_engine(settings: AppSettings | None = None) -> Engine:
    return make_engine((settings or get_settings()).database_url)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


engine = get_engine()
SessionLocal = make_session_factory(engine)
