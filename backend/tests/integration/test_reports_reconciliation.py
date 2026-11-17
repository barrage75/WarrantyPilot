import csv
import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.api.main import create_app
from app.contracts.enums import PurchaseGuardState
from app.core.tables import purchase_requests
from tests.auth_helpers import SAMY_ID, login
from tests.integration.helpers import create_case


@pytest.fixture
def client(db_engine, app_settings):
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application, base_url="http://testserver") as client:
        yield client


def _purchase(session, person_id, equipment_id, amount, state, case_id=None):
    purchase_id = str(uuid4())
    session.execute(
        insert(purchase_requests).values(
            id=purchase_id,
            requester_id=str(person_id),
            equipment_id=str(equipment_id),
            case_id=str(case_id) if case_id else None,
            item_description="Remplacement",
            amount=amount,
            state=state.value,
            resolved_at="2026-11-14T10:00:00+00:00"
            if state == PurchaseGuardState.SAVING_REALIZED
            else None,
        )
    )
    return purchase_id


def _csv_rows(client):
    content = client.get("/api/reports/savings.csv").content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(content), delimiter=";"))


def _assert_reconciles(client):
    report = client.get("/api/reports/savings").json()
    lines = report["lines"] + report["purchase_guard_lines"]
    realized = sum(line["amount_eur"] for line in lines if line["realized"])
    possible = sum(line["amount_eur"] for line in lines if not line["realized"])
    assert round(realized, 2) == report["realized_savings_eur"]
    assert round(possible, 2) == report["possible_savings_eur"]
    rows = _csv_rows(client)
    assert len(rows) == len(lines)
    assert [row["Dossier"] for row in rows[: len(report["lines"])]] == [
        line["case_id"] for line in report["lines"]
    ]
    assert (
        round(sum(float(row["Montant EUR"]) for row in rows if row["Réalisé"] == "oui"), 2)
        == (report["realized_savings_eur"])
    )
    assert (
        round(sum(float(row["Montant EUR"]) for row in rows if row["Réalisé"] == "non"), 2)
        == (report["possible_savings_eur"])
    )
    return report, rows


def test_report_lines_reconcile_with_totals_for_every_purchase_shape(client, session_factory):
    login(client, person_id=SAMY_ID)
    mixed, person_id = create_case(session_factory, email="mixed@example.test")
    kept_only, kept_person = create_case(session_factory, email="kept@example.test")
    bare, _ = create_case(session_factory, email="bare@example.test")
    with session_factory.begin() as session:
        _purchase(
            session, person_id, mixed.equipment_id, 40, PurchaseGuardState.SAVING_REALIZED, mixed.id
        )
        _purchase(
            session,
            person_id,
            mixed.equipment_id,
            15.5,
            PurchaseGuardState.PURCHASE_SUSPENDED,
            mixed.id,
        )
        _purchase(
            session, person_id, mixed.equipment_id, 999, PurchaseGuardState.PURCHASE_KEPT, mixed.id
        )
        _purchase(
            session,
            kept_person,
            kept_only.equipment_id,
            77,
            PurchaseGuardState.PURCHASE_KEPT,
            kept_only.id,
        )
        unlinked = _purchase(
            session, person_id, mixed.equipment_id, 120, PurchaseGuardState.AWAITING_DECISION
        )
        _purchase(session, person_id, mixed.equipment_id, 33, PurchaseGuardState.PURCHASE_KEPT)
    report, rows = _assert_reconciles(client)
    assert report["realized_savings_eur"] == 40
    assert report["possible_savings_eur"] == 135.5
    by_case = {}
    for line in report["lines"]:
        by_case.setdefault(line["case_id"], []).append(line)
    assert set(by_case) == {str(mixed.id), str(kept_only.id), str(bare.id)}
    assert all(line["channel"] and line["status"] for line in report["lines"])
    assert sorted((line["amount_eur"], line["realized"]) for line in by_case[str(mixed.id)]) == [
        (15.5, False),
        (40, True),
    ]
    assert [line["amount_eur"] for line in by_case[str(kept_only.id)]] == [0]
    assert [line["amount_eur"] for line in by_case[str(bare.id)]] == [0]
    assert report["purchase_guard_lines"] == [
        {
            "purchase_request_id": unlinked,
            "equipment_label": "Jabra Evolve2 65",
            "manufacturer": "Jabra",
            "state": "awaiting_decision",
            "amount_eur": 120,
            "realized": False,
            "resolved_at": None,
        }
    ]
    assert len(rows) == len(report["lines"]) + 1
    guard_row = rows[-1]
    assert guard_row["Montant EUR"] == "120.00"
    assert guard_row["Dossier"] == guard_row["Canal"] == guard_row["Référence"] == ""
    assert guard_row["Statut"] and guard_row["Équipement"] == "Jabra Evolve2 65"
    assert all(row["Dossier"] for row in rows[:-1])


def test_demo_report_shows_purchase_guard_line_and_reconciles(client):
    login(client, person_id=SAMY_ID)
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
    report, _ = _assert_reconciles(client)
    assert report["possible_savings_eur"] == 120
    assert [line["amount_eur"] for line in report["purchase_guard_lines"]] == [120]
    assert sum(line["amount_eur"] for line in report["lines"]) == 0
