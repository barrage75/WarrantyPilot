from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.contracts import enums
from app.contracts.enums import EventType
from app.core.tables import events


@pytest.mark.parametrize(
    "event_type", [EventType.INTAKE_MESSAGE_RECEIVED, EventType.INTAKE_DOCUMENT_RECEIVED]
)
def test_intake_event_migration(tmp_path: Path, event_type: EventType) -> None:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["0008_intake_events"]
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    legacy_types = tuple(
        value
        for value in EventType
        if value not in {EventType.INTAKE_MESSAGE_RECEIVED, EventType.INTAKE_DOCUMENT_RECEIVED}
    )
    event_id = str(uuid4())
    receipt = {
        "id": event_id,
        "at": "2026-11-14T00:00:00+00:00",
        "actor": "system",
        "type": event_type.value,
        "payload": {},
        "prev_hash": "0" * 64,
        "hash": "1" * 64,
    }
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            with patch.object(enums, "EventType", legacy_types):
                command.upgrade(config, "0006_chat_disclosure_event")
            with pytest.raises(IntegrityError, match="ck_events_type"):
                connection.execute(insert(events).values(**receipt))
            connection.execute(
                insert(events).values(
                    **{**receipt, "id": "legacy-event", "type": EventType.CHAT_DISCLOSURE.value}
                )
            )
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert connection.scalar(select(events.c.id)) == "legacy-event"
        with engine.connect() as connection, connection.begin() as transaction:
            connection.execute(insert(events).values(**receipt))
            assert (
                connection.scalar(select(events.c.type).where(events.c.id == event_id))
                == event_type.value
            )
            with pytest.raises(IntegrityError, match="events are append-only"):
                connection.execute(
                    update(events).where(events.c.id == event_id).values(actor="changed")
                )
            with pytest.raises(IntegrityError, match="events are append-only"):
                connection.execute(delete(events).where(events.c.id == event_id))
            transaction.rollback()
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0007_purchase_guard_lifecycle")
            with pytest.raises(IntegrityError, match="ck_events_type"):
                connection.execute(insert(events).values(**receipt))
            with pytest.raises(IntegrityError, match="events are append-only"):
                connection.execute(delete(events))
            with pytest.raises(IntegrityError, match="events are append-only"):
                connection.execute(update(events).values(actor="changed"))
            assert connection.scalar(select(events.c.id)) == "legacy-event"
    finally:
        engine.dispose()
