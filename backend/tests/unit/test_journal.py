import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.contracts.enums import EventType
from app.core.db import create_schema, make_engine, make_session_factory
from app.core.journal import ZERO_HASH, anchor, append_event, verify
from app.core.tables import events


def test_anchor_rollback_does_not_write_file(session_factory, app_settings) -> None:
    with session_factory() as session:
        append_event(session, EventType.DEMO_RESET)
        anchor(session, app_settings)
        assert not app_settings.anchor_file.exists()
        session.rollback()
        assert verify(session, app_settings)["ok"] is True
        session.commit()
    assert not app_settings.anchor_file.exists()


def test_anchor_commit_writes_file(session_factory, app_settings) -> None:
    with session_factory() as session:
        append_event(session, EventType.DEMO_RESET)
        result = anchor(session, app_settings)
        assert not app_settings.anchor_file.exists()
        session.commit()
        assert json.loads(app_settings.anchor_file.read_text()) == result
        assert verify(session, app_settings)["ok"] is True


def test_hash_chain_is_valid_and_secrets_are_redacted(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        first = append_event(
            session,
            EventType.CASE_CREATED,
            payload={
                "access_token": "private",
                "nested": {"apiKey": "hidden", "description": "visible"},
            },
        )
        second = append_event(session, EventType.FACT_EXTRACTED, payload={"field": "serial"})
        assert first.prev_hash == ZERO_HASH
        assert second.prev_hash == first.hash
        assert first.payload == {
            "access_token": "***",
            "nested": {"apiKey": "***", "description": "visible"},
        }
        assert verify(session, app_settings) == {
            "ok": True,
            "checked": 2,
            "first_bad_seq": None,
            "anchors_ok": True,
        }


def test_sqlite_rejects_event_update_and_delete(session_factory) -> None:
    with session_factory.begin() as session:
        event = append_event(session, EventType.DEMO_RESET)
    with session_factory() as session:
        with pytest.raises(IntegrityError, match="events are append-only"):
            session.execute(
                text("UPDATE events SET actor = 'human:tamper' WHERE seq = :seq"),
                {"seq": event.seq},
            )
        session.rollback()
    with (
        session_factory() as session,
        pytest.raises(IntegrityError, match="events are append-only"),
    ):
        session.execute(
            text("DELETE FROM events WHERE seq = :seq"),
            {"seq": event.seq},
        )


def test_verify_reports_exact_first_modified_sequence(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        append_event(session, EventType.DEMO_RESET, payload={"n": 1})
        append_event(session, EventType.CASE_CREATED, payload={"n": 2})
    with session_factory() as session:
        session.execute(text("DROP TRIGGER events_no_update"))
        session.execute(
            text("UPDATE events SET payload = :payload WHERE seq = 2"),
            {"payload": json.dumps({"n": 999})},
        )
        session.commit()
        result = verify(session, app_settings)
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2


def test_anchor_tampering_is_detected(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        append_event(session, EventType.DEMO_RESET)
        saved_anchor = anchor(session, app_settings)
    with session_factory() as session:
        assert verify(session, app_settings)["anchors_ok"] is True
    anchor_file = app_settings.anchor_file
    anchor_data = json.loads(anchor_file.read_text(encoding="utf-8").splitlines()[0])
    anchor_data["hmac"] = "0" * 64
    anchor_file.write_text(json.dumps(anchor_data) + "\n", encoding="utf-8")
    with session_factory() as session:
        result = verify(session, app_settings)
    assert result["ok"] is False
    assert result["anchors_ok"] is False
    assert result["first_bad_seq"] == saved_anchor["seq"]


def test_missing_anchor_file_is_detected(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        append_event(session, EventType.DEMO_RESET)
        anchor(session, app_settings)
    app_settings.anchor_file.unlink()

    with session_factory() as session:
        result = verify(session, app_settings)

    assert result["ok"] is False
    assert result["anchors_ok"] is False


def test_deleted_anchor_line_is_detected(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        append_event(session, EventType.DEMO_RESET)
        anchor(session, app_settings)
        anchor(session, app_settings)
    lines = app_settings.anchor_file.read_text(encoding="utf-8").splitlines()
    app_settings.anchor_file.write_text(lines[1] + "\n", encoding="utf-8")

    with session_factory() as session:
        result = verify(session, app_settings)

    assert result["ok"] is False
    assert result["anchors_ok"] is False


def test_concurrent_appends_keep_a_contiguous_valid_chain(tmp_path, app_settings) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'concurrent-journal.db'}")
    create_schema(engine)
    factory = make_session_factory(engine)

    def write_event(index: int) -> None:
        with factory.begin() as session:
            append_event(session, EventType.FACT_EXTRACTED, payload={"index": index})

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(write_event, range(20)))
        with factory() as session:
            sequences = session.execute(select(events.c.seq).order_by(events.c.seq)).scalars().all()
            result = verify(session, app_settings)
        assert sequences == list(range(1, 21))
        assert result["ok"] is True
        assert result["checked"] == 20
    finally:
        engine.dispose()
