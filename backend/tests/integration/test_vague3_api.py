import time
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from app.api.main import create_app
from app.contracts.enums import CaseStatus, EventType
from app.core.tables import cases, equipment, events, people


def _reset(client: TestClient) -> None:
    assert client.post("/api/demo/reset").status_code == 200


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
        _reset(client)
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


def test_scan_runs_in_background_and_reports_document_progress(db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
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
    assert result["invoices"] == 60
    assert result["badge"] == "reproduction"


def test_purchase_guard_requires_reason_and_realizes_savings_after_both_conditions(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
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

        cancelled = client.post(f"/api/purchase-requests/{purchase['id']}/confirm-cancellation")
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "cancelled"

        with session_factory.begin() as session:
            session.execute(
                update(cases).where(cases.c.id == case_id).values(status=CaseStatus.RESOLVED.value)
            )
        realized = client.post(f"/api/purchase-requests/{purchase['id']}/resolve-case")

    assert realized.status_code == 200
    assert realized.json()["state"] == "saving_realized"
    assert realized.json()["cancelledAt"]
    assert realized.json()["resolvedAt"]


def test_purchase_guard_allows_keep_only_with_reason(db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        _reset(client)
        purchase = client.get("/api/purchase-requests").json()[0]
        kept = client.post(
            f"/api/purchase-requests/{purchase['id']}/decision",
            json={"choice": "keep", "reason": "Budget déjà engagé"},
        )

    assert kept.status_code == 200
    assert kept.json()["state"] == "purchase_kept"
    assert kept.json()["reason"] == "Budget déjà engagé"
