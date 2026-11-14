from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, inspect, select, update

from app.actions.browser.adapter import BrowserPortalAdapter
from app.actions.email.adapter import EmailActionAdapter
from app.api.main import create_app
from app.contracts.enums import CaseStatus, Channel, EventType
from app.contracts.models import utc_now
from app.core.tables import (
    action_results,
    case_steps,
    cases,
    documents,
    equipment,
    equipment_documents,
    equipment_suppliers,
    events,
    facts,
    people,
    rights,
    suppliers,
)
from tests.auth_helpers import KARIM_ID, login
from tests.integration.helpers import create_case


def test_reset_preflight_and_health_endpoints(db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        adapters = application.state.services["action_adapters"]
        assert isinstance(adapters[Channel.EMAIL_RESELLER], EmailActionAdapter)
        assert adapters[Channel.EMAIL_RESELLER].transport.name == "smtp-local"
        assert isinstance(adapters[Channel.BROWSER_PORTAL], BrowserPortalAdapter)
        assert client.get("/api/health").json() == {"status": "ok"}
        stale_message = app_settings.maildir_path / "stale-message"
        stale_message.write_text("synthetic", encoding="utf-8")
        app_settings.email_sent_ledger_path.write_text("synthetic\n", encoding="utf-8")
        reset = client.post("/api/demo/reset", json={"confirm": "RESET"})
        assert reset.status_code == 200
        assert not stale_message.exists()
        assert not app_settings.email_sent_ledger_path.exists()
        assert client.get("/api/cases").json() == []
        preflight = client.get("/api/demo/preflight")
        assert preflight.status_code == 200
        assert preflight.json()["ok"] is True
        journal = client.get("/api/journal/verify")
        assert journal.json()["ok"] is True
    table_names = set(inspect(db_engine).get_table_names())
    assert "alembic_version" in table_names
    with db_engine.connect() as connection:
        assert len(connection.execute(select(people.c.id)).all()) == 200
        assert len(connection.execute(select(equipment.c.id)).all()) == 230
        assert len(connection.execute(select(documents.c.id)).all()) == 65
        assert len(connection.execute(select(suppliers.c.id)).all()) == 3
        assert connection.execute(select(equipment_suppliers.c.equipment_id)).all()
        assert connection.execute(select(equipment_documents.c.document_id)).all()
        assert connection.execute(select(facts.c.id)).all()
        assert connection.execute(select(rights.c.id)).all()


def test_manual_takeover_requires_human_proof(db_engine, session_factory, app_settings) -> None:
    case, person_id = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(cases).where(cases.c.id == str(case.id)).values(status=CaseStatus.FAILED.value)
        )
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        operator = login(client, person_id=KARIM_ID)
        takeover = client.post(
            f"/api/cases/{case.id}/manual-takeover",
            json={},
        )
        assert takeover.status_code == 200
        assert takeover.json()["status"] == CaseStatus.MANUAL_TAKEOVER.value

        proof = client.post(
            f"/api/cases/{case.id}/manual-proof",
            json={
                "proof_type": "case_number",
                "reference": "TICKET-HUMAN-123",
                "proof_date": "2026-11-14",
            },
        )
        assert proof.status_code == 200
        assert proof.json()["status"] == CaseStatus.SENT.value

    with session_factory() as session:
        result = session.execute(select(action_results)).mappings().one()
        event = (
            session.execute(
                select(events)
                .where(events.c.type == EventType.ACTION_SUCCEEDED.value)
                .order_by(events.c.seq.desc())
                .limit(1)
            )
            .mappings()
            .one()
        )
    assert result["status"] == "success"
    assert result["proof"] == "case_number:TICKET-HUMAN-123 (2026-11-14)"
    assert event["actor"] == operator.actor


@pytest.mark.parametrize(
    ("attempt", "expected_status"),
    [
        (1, CaseStatus.FAILED),
        (2, CaseStatus.MANUAL_TAKEOVER),
    ],
)
def test_startup_recovers_interrupted_send(
    db_engine, session_factory, app_settings, attempt, expected_status
) -> None:
    case, _ = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(cases).where(cases.c.id == str(case.id)).values(status=CaseStatus.SENDING.value)
        )
        session.execute(
            insert(case_steps).values(
                id=str(uuid4()),
                case_id=str(case.id),
                step_name="execute",
                order=7,
                status="running",
                attempt=attempt,
                output={},
                updated_at=utc_now().isoformat(),
            )
        )
    application = create_app(app_settings=app_settings, app_engine=db_engine)

    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        recovered = client.get(f"/api/cases/{case.id}")

    assert recovered.status_code == 200
    assert recovered.json()["status"] == expected_status.value
    assert recovered.json()["status"] != CaseStatus.SENT.value
