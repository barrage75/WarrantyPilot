import sqlite3
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.enums import EventType
from app.core.db import create_schema, make_engine, make_session_factory
from app.core.orchestrator import Orchestrator
from app.core.settings import AppSettings
from app.core.tables import actions, cases, events, incidents, verdicts
from app.core.warranty import evaluate_equipment
from app.intake.documents import DocumentIntake
from app.intake.service import IntakeService
from app.intake.transports import MaildirInbox
from tests.integration.intake.test_evidence_linking import invoice, seed_device
from tests.integration.intake.test_intake import add, client, mail


@pytest.fixture
def stored_intake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[Engine, sessionmaker[Session], IntakeService], None, None]:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    engine = make_engine(f"sqlite:///{tmp_path / 'intake.db'}")
    create_schema(engine)
    factory = make_session_factory(engine)
    intake = IntakeService(MaildirInbox(tmp_path / "inbox"), DocumentIntake(tmp_path / "docs"))
    with factory.begin() as session:
        device, person = seed_device(session)
        intake.documents.ingest(session, "facture.xml", invoice())
    assert isinstance(intake.inbox, MaildirInbox)
    add(intake.inbox, mail(f"Mon casque {device.serial} est en panne.", sender=str(person.email)))
    yield engine, factory, intake
    engine.dispose()


def test_real_poll_evaluates_after_committing_receipt(
    stored_intake: tuple[Engine, sessionmaker[Session], IntakeService],
    app_settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, intake = stored_intake
    prepare = Orchestrator._prepare_run
    checked: list[UUID] = []

    def committed_prepare(self: Orchestrator, case_id: UUID):
        with closing(sqlite3.connect(str(engine.url.database), timeout=0.1)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM events WHERE type = ? AND case_id = ?",
                (EventType.INTAKE_MESSAGE_RECEIVED.value, str(case_id)),
            ).fetchone()[0]
        assert count == 1, "intake receipt must commit before shared orchestration"
        checked.append(case_id)
        return prepare(self, case_id)

    monkeypatch.setattr(Orchestrator, "_prepare_run", committed_prepare)
    with (
        client(engine, factory, app_settings, intake) as api,
        patch("app.core.orchestrator.evaluate_equipment", wraps=evaluate_equipment) as shared,
    ):
        response = api.post("/api/intake/poll")
        assert response.status_code == 200, response.text
        case_id = response.json()["messages"][0]["case_id"]
        with factory() as session:
            verdict = session.execute(
                select(verdicts).join(cases, cases.c.verdict_id == verdicts.c.id)
            ).one()
            assert verdict.value == "covered"
            assert verdict.rule_id == "jabra-evolve"
            assert verdict.checks
            row = session.execute(select(cases)).one()
            assert row.status == "awaiting_validation"
            assert session.execute(select(actions)).first() is None
        assert response.json()["messages"][0]["verdict"] == "covered"
        assert api.post("/api/intake/poll").json()["messages"][0]["state"] == "duplicate"
    assert checked == [UUID(case_id)]
    shared.assert_called_once()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(cases)) == 1
        assert session.scalar(select(func.count()).select_from(verdicts)) == 1
        receipt = session.execute(
            select(events.c.seq).where(events.c.type == EventType.INTAKE_MESSAGE_RECEIVED.value)
        ).scalar_one()
        computed = session.execute(
            select(events.c.seq).where(events.c.type == EventType.VERDICT_COMPUTED.value)
        ).scalar_one()
        assert receipt < computed


def test_poll_retries_evaluation_from_committed_duplicate_receipt(
    stored_intake: tuple[Engine, sessionmaker[Session], IntakeService],
    app_settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, intake = stored_intake
    prepare = Orchestrator._prepare_run

    def unavailable(self: Orchestrator, case_id: UUID):
        raise RuntimeError("evaluation unavailable")

    with client(engine, factory, app_settings, intake) as api:
        monkeypatch.setattr(Orchestrator, "_prepare_run", unavailable)
        with pytest.raises(RuntimeError, match="evaluation unavailable"):
            api.post("/api/intake/poll")
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(cases)) == 1
            assert session.execute(select(cases.c.verdict_id)).scalar_one() is None
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(events)
                    .where(events.c.type == EventType.INTAKE_MESSAGE_RECEIVED.value)
                )
                == 1
            )
        monkeypatch.setattr(Orchestrator, "_prepare_run", prepare)
        response = api.post("/api/intake/poll")
        assert response.status_code == 200, response.text
        assert response.json()["messages"][0]["state"] == "duplicate"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(cases)) == 1
        assert session.execute(select(verdicts.c.rule_id)).scalar_one() == "jabra-evolve"
        assert session.execute(select(actions)).first() is None


def test_poll_receipt_failure_never_starts_evaluation(
    stored_intake: tuple[Engine, sessionmaker[Session], IntakeService],
    app_settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory, intake = stored_intake

    def fail_receipt(*args: object, **kwargs: object) -> None:
        raise RuntimeError("receipt unavailable")

    with (
        client(engine, factory, app_settings, intake) as api,
        patch.object(Orchestrator, "run") as run,
    ):
        monkeypatch.setattr("app.intake.service.append_event", fail_receipt)
        with pytest.raises(RuntimeError, match="receipt unavailable"):
            api.post("/api/intake/poll")
    run.assert_not_called()
    with factory() as session:
        assert session.execute(select(cases)).first() is None
        assert session.execute(select(incidents)).first() is None
        assert session.execute(select(verdicts)).first() is None
        assert (
            session.execute(
                select(events).where(events.c.type == EventType.INTAKE_MESSAGE_RECEIVED.value)
            ).first()
            is None
        )


def test_concurrent_real_pollers_evaluate_one_case(
    stored_intake: tuple[Engine, sessionmaker[Session], IntakeService], app_settings: AppSettings
) -> None:
    engine, factory, intake = stored_intake
    with (
        client(engine, factory, app_settings, intake) as api,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        responses = list(pool.map(lambda _: api.post("/api/intake/poll"), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert sorted(response.json()["messages"][0]["state"] for response in responses) == [
        "duplicate",
        "failure",
    ]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(cases)) == 1
        assert session.execute(select(verdicts.c.rule_id)).scalar_one() == "jabra-evolve"
        assert session.execute(select(actions)).first() is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(events)
                .where(events.c.type == EventType.INTAKE_MESSAGE_RECEIVED.value)
            )
            == 1
        )
