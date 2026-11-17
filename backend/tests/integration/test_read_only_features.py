import asyncio
import csv
import io
import json
import time
from datetime import UTC, datetime, timedelta
from datetime import time as datetime_time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.main import create_app
from app.api.routers.scan import _run_scan
from app.contracts.enums import EventType
from app.contracts.models import Action, ActionResult
from app.core.journal import append_event
from app.core.settings_store import read_settings, write_settings
from app.core.tables import action_results, actions, cases, equipment, events
from app.followup.reminders import ReminderPlanner
from tests.auth_helpers import SAMY_ID, login
from tests.integration.helpers import create_case


@pytest.fixture
def client(db_engine, app_settings):
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application, base_url="http://testserver") as client:
        yield client


@pytest.mark.parametrize(
    "path", ["equipment/overview", "reports/savings", "reports/savings.csv", "notifications"]
)
def test_read_endpoints_require_session(client, path):
    assert client.get(f"/api/{path}").status_code == 401
    login(client, role="operator", person_id=SAMY_ID)
    assert client.get(f"/api/{path}").status_code == 200


def test_empty_database(client):
    login(client, person_id=SAMY_ID)
    assert client.get("/api/equipment/overview").json() == []
    assert client.get("/api/notifications").json() == []
    report = client.get("/api/reports/savings").json()
    assert report["lines"] == []
    assert report["journal_head"] is None
    assert report["journal_ok"] is True
    assert all(
        report[key] == 0
        for key in ("covered_equipment_eur", "possible_savings_eur", "realized_savings_eur")
    )
    assert len(client.get("/api/reports/savings.csv").content.decode("utf-8-sig").splitlines()) == 1


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@SUM(1,2)", "\t=1+1", "\r=1+1"])
def test_savings_csv_escapes_formulas_and_uses_french_labels(client, session_factory, value):
    login(client, person_id=SAMY_ID)
    case, _ = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(equipment).where(equipment.c.id == str(case.equipment_id)).values(brand=value)
        )
        append_event(
            session,
            EventType.FOLLOWUP_RECEIVED,
            case_id=str(case.id),
            payload={"case_number": value},
        )
    response = client.get("/api/reports/savings.csv")
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 2
    assert rows[1][1] == f"'{value} Evolve2 65"
    assert rows[1][2] == f"'{value}"
    assert rows[1][3:5] == ["E-mail revendeur", "Préparé"]
    assert rows[1][8] == f"'{value}"


def test_seed_overview_filters_and_timing(client):
    login(client, person_id=SAMY_ID)
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
    start = time.perf_counter()
    response = client.get("/api/equipment/overview")
    elapsed = time.perf_counter() - start
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 230
    assert elapsed < 1, elapsed
    dell = next(item for item in items if item["serial"] == "7XK4L93")
    paul = next(
        item
        for item in items
        if item["brand"] == "Jabra"
        and item["assigned_to"]
        and item["assigned_to"]["name"] == "Paul Martin"
    )
    assert dell["coverage"] in {"active", "expiring_soon"}
    assert dell["verdict"] in {"covered", "likely_covered"}
    assert paul["coverage"] in {"active", "expiring_soon"}
    assert paul["invoice_document_id"]
    assert client.get("/api/equipment/overview", params={"q": "7xk4l93"}).json() == [dell]
    assert paul in client.get("/api/equipment/overview", params={"q": "pAuL mArTiN"}).json()
    assert client.get("/api/equipment/overview?q=not-a-device").json() == []
    for coverage in {item["coverage"] for item in items}:
        filtered = client.get("/api/equipment/overview", params={"coverage": coverage}).json()
        assert filtered and all(item["coverage"] == coverage for item in filtered)
    assert client.get("/api/equipment/overview?coverage=wrong").status_code == 422
    print(f"seed overview: {elapsed:.3f}s; Dell={json.dumps(dell)}; Paul={json.dumps(paul)}")


def test_report_matches_scan_after_claim_and_purchase_flows(client, session_factory):
    login(client, person_id=SAMY_ID)
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
    with session_factory.begin() as session:
        settings = read_settings(session)
        write_settings(
            session, settings.model_copy(update={"auto_send_threshold_eur": Decimal("0")})
        )
    paul = next(
        item
        for item in client.get("/api/equipment/overview?q=Paul%20Martin").json()
        if item["brand"] == "Jabra"
    )
    for text, reporter in [
        (f"Mon casque Jabra {paul['serial']} ne charge plus", paul["assigned_to"]["id"]),
        ("Le PC 7XK4L93 ne démarre plus", SAMY_ID),
    ]:
        conversation = client.post("/api/chat/conversations").json()
        created = client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={"text": text, "reporter_id": reporter},
        )
        assert created.status_code == 200, created.text
        assert created.json()["case_id"]
    purchase = client.get("/api/purchase-requests").json()[0]
    suspended = client.post(
        f"/api/purchase-requests/{purchase['id']}/decision", json={"choice": "suspend"}
    )
    assert suspended.status_code == 200, suspended.text
    case_id = suspended.json()["caseId"]
    assert (
        client.post(
            f"/api/purchase-requests/{purchase['id']}/confirm-cancellation", json={}
        ).status_code
        == 200
    )
    with session_factory.begin() as session:
        session.execute(update(cases).where(cases.c.id == case_id).values(status="resolved"))
        append_event(
            session,
            EventType.FOLLOWUP_RECEIVED,
            case_id=case_id,
            payload={"case_number": "TEST-RMA-123", "status": "resolved"},
        )
    assert client.post(f"/api/purchase-requests/{purchase['id']}/resolve-case").status_code == 200
    report = client.get("/api/reports/savings").json()
    application = client.app
    application.state.scans["test"] = {}
    asyncio.run(_run_scan(application, "test"))
    scan = application.state.scans["test"]
    assert scan["status"] == "completed", scan
    for key in ("covered_equipment_eur", "possible_savings_eur", "realized_savings_eur"):
        assert report[key] == scan[key]
    assert report["realized_savings_eur"] == 120
    line = next(line for line in report["lines"] if line["case_id"] == case_id)
    assert line["realized"] and line["resolved_at"] and line["reference"] == "TEST-RMA-123"
    assert len(report["lines"]) == 2
    assert report["journal_ok"]
    with session_factory() as session:
        assert (
            report["journal_head"]
            == session.execute(
                select(events.c.hash).order_by(events.c.seq.desc()).limit(1)
            ).scalar_one()
        )
    response = client.get("/api/reports/savings.csv")
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["content-disposition"].startswith(
        "attachment; filename=warrantypilot-economies-"
    )
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == [
        "Dossier",
        "Équipement",
        "Fabricant",
        "Canal",
        "Statut",
        "Montant EUR",
        "Réalisé",
        "Résolu le",
        "Référence",
    ]
    assert len(rows) == 3
    assert all(len(row[5].split(".")[-1]) == 2 for row in rows[1:])
    print("report:", json.dumps(report))
    print("CSV:", response.content.decode("utf-8-sig"))


def test_notifications_stable_sorted_sourced_and_read_only(client, session_factory, app_settings):
    case, _ = create_case(session_factory)
    login(client, person_id=SAMY_ID)
    with session_factory.begin() as session:
        session.execute(update(cases).where(cases.c.id == str(case.id)).values(status="failed"))
        append_event(
            session,
            EventType.FOLLOWUP_RECEIVED,
            case_id=str(case.id),
            payload={
                "kind": "return_deadline",
                "due_on": (app_settings.demo_today + timedelta(days=5)).isoformat(),
                "source": "test RMA",
            },
        )
    first = client.get("/api/notifications").json()
    assert first == client.get("/api/notifications").json()
    assert [item["kind"] for item in first] == ["case_failed", "return_deadline"]
    assert [item["id"] for item in first] == [
        f"case_failed:{case.id}",
        f"return_deadline:{case.id}",
    ]
    assert all("text" not in item for item in first)
    with session_factory.begin() as session:
        session.execute(
            update(cases).where(cases.c.id == str(case.id)).values(status="awaiting_validation")
        )
        append_event(
            session,
            EventType.FOLLOWUP_RECEIVED,
            case_id=str(case.id),
            payload={"kind": "return_deadline", "due_on": "invalid", "source": "test RMA"},
        )
        count = len(session.execute(select(events)).all())
    assert [item["kind"] for item in client.get("/api/notifications").json()] == [
        "case_awaiting_validation"
    ]
    with session_factory() as session:
        assert len(session.execute(select(events)).all()) == count
    print("notifications:", json.dumps(first))


def test_report_exposes_journal_failure(client, session_factory, app_settings):
    login(client, person_id=SAMY_ID)
    with session_factory.begin() as session:
        append_event(session, EventType.CHAT_DISCLOSURE, payload={})
    app_settings.anchor_file.parent.mkdir(parents=True, exist_ok=True)
    app_settings.anchor_file.write_text("invalid anchor\n")
    assert client.get("/api/reports/savings").json()["journal_ok"] is False


def test_expiring_seed_and_reminder_notifications(client, session_factory, app_settings):
    login(client, person_id=SAMY_ID)
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
    app_settings.demo_today = app_settings.demo_today.replace(year=2027, month=3, day=1)
    client.app.state.reminder_scheduler.planner = ReminderPlanner(
        demo_today=app_settings.demo_today
    )
    paul = next(
        item
        for item in client.get("/api/equipment/overview?q=Paul%20Martin").json()
        if item["brand"] == "Jabra"
    )
    notifications = client.get("/api/notifications").json()
    notice = next(
        item for item in notifications if item["id"] == f"warranty_expiring:{paul['equipment_id']}"
    )
    assert notice["params"]["days_left"] == 18
    assert notice["due_at"] == "2027-03-19T00:00:00Z"
    case, _ = create_case(session_factory)
    action = Action(
        case_id=case.id,
        channel="email_reseller",
        kind="test",
        idempotency_key="test-reminder",
        payload={},
        badge="simulated",
    )
    result = ActionResult(
        action_id=action.id, status="success", proof="test@example.test", badge="simulated"
    )
    sent = datetime.combine(app_settings.demo_today - timedelta(days=8), datetime_time.min, UTC)
    with session_factory.begin() as session:
        session.execute(update(cases).where(cases.c.id == str(case.id)).values(status="sent"))
        session.execute(actions.insert().values(**action.model_dump(mode="json")))
        session.execute(action_results.insert().values(**result.model_dump(mode="json")))
        append_event(
            session,
            EventType.ACTION_SUCCEEDED,
            case_id=str(case.id),
            payload={"action_id": str(action.id)},
            at=sent,
        )
    notices = client.get("/api/notifications").json()
    reminder = next(item for item in notices if item["id"] == f"reminder_due:{case.id}")
    assert reminder["params"]["reminder_number"] == 1
    with session_factory.begin() as session:
        append_event(
            session,
            EventType.FOLLOWUP_RECEIVED,
            case_id=str(case.id),
            payload={"message_id": "response@example.test"},
            at=sent + timedelta(days=1),
        )
    assert not any(item["id"] == reminder["id"] for item in client.get("/api/notifications").json())
