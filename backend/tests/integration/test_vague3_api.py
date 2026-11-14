import time
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from app.api.main import create_app
from app.contracts.enums import CaseStatus, Channel, EventType, VerdictValue
from app.contracts.models import Verdict
from app.core.db import create_schema, make_engine
from app.core.settings_store import read_settings, write_settings
from app.core.tables import (
    actions,
    cases,
    data_checklists,
    equipment,
    events,
    incidents,
    people,
    verdicts,
)
from app.testing.fakes import FakeRulesEngine
from tests.auth_helpers import KARIM_ID, login


def _reset(client: TestClient) -> None:
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200


def _paul_id(session_factory) -> str:
    with session_factory() as session:
        return session.execute(
            select(people.c.id).where(people.c.name == "Paul Martin")
        ).scalar_one()


def test_chat_discloses_ai_and_creates_deterministic_case(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        with session_factory.begin() as session:
            settings = read_settings(session)
            write_settings(
                session,
                settings.model_copy(update={"auto_send_threshold_eur": Decimal("0")}),
            )
        conversation = client.post("/api/chat/conversations")
        assert conversation.status_code == 200
        disclosure = conversation.json()["disclosure_text"]
        assert "intelligence artificielle" in disclosure

        result = client.post(
            f"/api/chat/conversations/{conversation.json()['id']}/messages",
            json={
                "text": "Mon casque Jabra Evolve2 65 ne charge plus.",
                "reporter_id": _paul_id(session_factory),
            },
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["case_id"]
        assert body["equipment"] == "Jabra Evolve2 65"
        assert body["identified_equipment"] == "Jabra Evolve2 65"
        assert body["messages"][-1]["role"] == "assistant"

    with session_factory() as session:
        event = (
            session.execute(select(events).where(events.c.type == EventType.CHAT_DISCLOSURE.value))
            .mappings()
            .one()
        )
        case = session.execute(select(cases).where(cases.c.id == body["case_id"])).mappings().one()
    assert event["payload"]["disclosure_text"] == disclosure
    assert case["status"] == CaseStatus.AWAITING_VALIDATION.value


def test_chat_asks_when_reporter_has_multiple_matching_assets(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        paul_id = _paul_id(session_factory)
        with session_factory.begin() as session:
            session.execute(
                insert(equipment).values(
                    id=str(uuid4()),
                    brand="Jabra",
                    model="Evolve2 40",
                    serial="JABRA-EXAMPLE-2",
                    category="headset",
                    assigned_to=paul_id,
                    purchase_price=100,
                    currency="EUR",
                    in_loan_stock=False,
                    purchase_date=None,
                    invoice_number=None,
                    delivery_date=None,
                    ship_date=None,
                )
            )
        conversation = client.post("/api/chat/conversations").json()
        result = client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={"text": "Mon casque est en panne.", "reporter_id": paul_id},
        )

    assert result.status_code == 200
    assert result.json()["case_id"] is None
    assert result.json()["clarifying_questions"]


def test_chat_selects_foreign_equipment_by_exact_service_tag(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        conversation = client.post("/api/chat/conversations").json()
        result = client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={
                "text": "Le PC 7XK4L93 de Clément ne démarre plus",
                "reporter_id": KARIM_ID,
            },
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["case_id"]
        assert body["equipment"] == "Dell Latitude 7440"

    with session_factory() as session:
        dell = (
            session.execute(select(equipment).where(equipment.c.serial == "7XK4L93"))
            .mappings()
            .one()
        )
        case = session.execute(select(cases).where(cases.c.id == body["case_id"])).mappings().one()
        incident = (
            session.execute(select(incidents).where(incidents.c.id == case["incident_id"]))
            .mappings()
            .one()
        )
        verdict = (
            session.execute(select(verdicts).where(verdicts.c.id == case["verdict_id"]))
            .mappings()
            .one()
        )
        checklist = session.execute(
            select(data_checklists.c.steps).where(data_checklists.c.case_id == body["case_id"])
        ).scalar_one()
        event = (
            session.execute(
                select(events).where(
                    events.c.case_id == body["case_id"],
                    events.c.type == EventType.CASE_CREATED.value,
                )
            )
            .mappings()
            .one()
        )

    assert incident["reporter_id"] == KARIM_ID
    assert case["equipment_id"] == dell["id"]
    assert dell["assigned_to"] != KARIM_ID
    assert case["status"] == CaseStatus.AWAITING_VALIDATION.value
    assert verdict["value"] in {"covered", "likely_covered"}
    assert verdict["channel"] == "browser_portal"
    assert len(checklist) == 7
    assert all(not step["done"] for step in checklist.values())
    assert event["payload"]["assigned_to"] == dell["assigned_to"]


def test_unknown_service_tag_produces_clarifying_question(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    reporter_id = str(uuid4())
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        with session_factory.begin() as session:
            session.execute(
                insert(people).values(
                    id=reporter_id,
                    name="Personne sans équipement",
                    email="sans-equipement@appelia.example",
                )
            )
        conversation = client.post("/api/chat/conversations").json()
        result = client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={
                "text": "Le PC ZZZ9999 de Clément ne démarre plus",
                "reporter_id": reporter_id,
            },
        )

    assert result.status_code == 200, result.text
    assert result.json()["case_id"] is None
    assert result.json()["clarifying_questions"]


@pytest.fixture
def scan_engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'scan.sqlite3'}")
    create_schema(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_scan_runs_in_background_and_reports_document_progress(scan_engine, app_settings) -> None:
    app_settings.demo_today = date(2026, 12, 20)
    app_settings.database_url = str(scan_engine.url)
    application = create_app(app_settings=app_settings, app_engine=scan_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        started = client.post("/api/scan")
        assert started.status_code == 202
        scan_id = started.json()["scan_id"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            response = client.get(f"/api/scan/{scan_id}")
            assert response.status_code == 200
            result = response.json()
            if result["status"] != "running":
                break
            time.sleep(0.05)

    assert result["status"] == "completed", result
    assert result["progress"] == 100
    assert result["documentsDone"] == result["documentsTotal"] == 65
    assert result["coveredEquipmentEur"] > 0
    assert result["realizedSavingsEur"] == 0
    assert result["invoices"] == 60
    assert result["badge"] == "reproduction"
    assert result["expiring"]
    assert any(item["daysLeft"] == 25 for item in result["expiring"])
    assert all(
        item["daysLeft"] == (date.fromisoformat(item["endsAt"]) - app_settings.demo_today).days
        for item in result["expiring"]
    )


def test_purchase_guard_requires_reason_and_realizes_savings_after_both_conditions(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        recommendations = client.get("/api/purchase-requests").json()
        assert len(recommendations) == 1
        purchase = recommendations[0]
        assert purchase["equipment"] == "Jabra Evolve2 65"
        assert purchase["amountEur"] == 120
        assert purchase["verdict"] == "covered"

        rejected = client.post(
            f"/api/purchase-requests/{purchase['id']}/decision",
            json={"choice": "keep"},
        )
        assert rejected.status_code == 422

        suspended = client.post(
            f"/api/purchase-requests/{purchase['id']}/decision",
            json={"choice": "suspend"},
        )
        assert suspended.status_code == 200, suspended.text
        case_id = suspended.json()["caseId"]
        assert suspended.json()["state"] == "purchase_suspended"

        cancelled = client.post(
            f"/api/purchase-requests/{purchase['id']}/confirm-cancellation",
            json={},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "cancelled"
        with session_factory() as session:
            cancellation_event = (
                session.execute(
                    select(events).where(events.c.type == EventType.PURCHASE_GUARD_CANCELLED.value)
                )
                .mappings()
                .one()
            )
        assert cancellation_event["actor"] == f"human:{KARIM_ID}"

        with session_factory.begin() as session:
            session.execute(
                update(cases).where(cases.c.id == case_id).values(status=CaseStatus.RESOLVED.value)
            )
        realized = client.post(f"/api/purchase-requests/{purchase['id']}/resolve-case")

    assert realized.status_code == 200
    assert realized.json()["state"] == "saving_realized"
    assert realized.json()["cancelledAt"]
    assert realized.json()["resolvedAt"]


def test_purchase_cancellation_requires_existing_person(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        purchase = client.get("/api/purchase-requests").json()[0]
        suspended = client.post(
            f"/api/purchase-requests/{purchase['id']}/decision",
            json={"choice": "suspend"},
        )
        assert suspended.status_code == 200
        cancelled = client.post(
            f"/api/purchase-requests/{purchase['id']}/confirm-cancellation",
            json={"person_id": str(uuid4())},
        )

    assert cancelled.status_code == 403


def test_purchase_guard_allows_keep_only_with_reason(db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        _reset(client)
        purchase = client.get("/api/purchase-requests").json()[0]
        kept = client.post(
            f"/api/purchase-requests/{purchase['id']}/decision",
            json={"choice": "keep", "reason": "Budget déjà engagé"},
        )

    assert kept.status_code == 200
    assert kept.json()["state"] == "purchase_kept"
    assert kept.json()["reason"] == "Budget déjà engagé"


def test_manual_verdict_requires_human_takeover_and_proof(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    verdict = Verdict(
        value=VerdictValue.TO_VERIFY,
        channel=Channel.MANUAL,
        rule_id="manual-review",
        rule_version="1",
        explanation_fr="Une vérification humaine est nécessaire.",
        explanation_en="Human verification is required.",
    )
    with TestClient(application) as client:
        operator = login(client, person_id=KARIM_ID)
        _reset(client)
        application.state.services["rules_engine"] = FakeRulesEngine(verdict)
        person_id = _paul_id(session_factory)
        conversation = client.post("/api/chat/conversations").json()
        created = client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={
                "text": "Mon casque Jabra Evolve2 65 ne charge plus.",
                "reporter_id": person_id,
            },
        )
        assert created.status_code == 200, created.text
        case_id = created.json()["case_id"]
        assert case_id

        validated = client.post(
            f"/api/cases/{case_id}/validate",
            json={},
        )
        assert validated.status_code == 200, validated.text
        assert validated.json()["status"] == CaseStatus.MANUAL_TAKEOVER.value
        with session_factory() as session:
            stored_verdict = session.execute(
                select(verdicts.c.value)
                .join(cases, cases.c.verdict_id == verdicts.c.id)
                .where(cases.c.id == case_id)
            ).scalar_one()
            manual_action = (
                session.execute(select(actions).where(actions.c.case_id == case_id))
                .mappings()
                .one()
            )
            case_events = (
                session.execute(
                    select(events.c.type, events.c.payload).where(events.c.case_id == case_id)
                )
                .mappings()
                .all()
            )
        assert stored_verdict == VerdictValue.TO_VERIFY.value
        assert manual_action["channel"] == Channel.MANUAL.value
        assert manual_action["badge"] == "reproduction"
        assert not any(event["type"] == EventType.ACTION_FAILED.value for event in case_events)
        assert not any(
            event["type"] == EventType.STATUS_CHANGED.value
            and event["payload"].get("to") == CaseStatus.SENT.value
            for event in case_events
        )

        proof = client.post(
            f"/api/cases/{case_id}/manual-proof",
            json={
                "proof_type": "case_number",
                "reference": "TICKET-HUMAN-123",
                "proof_date": "2026-11-14",
            },
        )
        assert proof.status_code == 200, proof.text
        assert proof.json()["status"] == CaseStatus.SENT.value

    with session_factory() as session:
        status_events = (
            session.execute(
                select(events.c.payload).where(
                    events.c.case_id == case_id,
                    events.c.type == EventType.STATUS_CHANGED.value,
                )
            )
            .scalars()
            .all()
        )
        success_event = (
            session.execute(
                select(events).where(
                    events.c.case_id == case_id,
                    events.c.type == EventType.ACTION_SUCCEEDED.value,
                )
            )
            .mappings()
            .one()
        )
    assert any(
        payload.get("reason") == "prise en main humaine requise" for payload in status_events
    )
    assert success_event["actor"] == operator.actor
