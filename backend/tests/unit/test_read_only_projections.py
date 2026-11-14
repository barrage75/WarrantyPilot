from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request

from app.api.routers import notifications, reports
from app.api.routers.overview import EquipmentWarrantyOverview


@pytest.fixture
def api_request():
    application = FastAPI()
    application.state.app_settings = SimpleNamespace(demo_today=date(2026, 11, 20))
    application.state.session_factory = MagicMock()
    session = application.state.session_factory.return_value.__enter__.return_value
    session.execute.return_value.mappings.return_value.all.return_value = []
    return Request({"type": "http", "app": application})


@pytest.mark.parametrize("days", [0, 30, 31])
def test_warranty_notification_window(monkeypatch, api_request, days):
    item = EquipmentWarrantyOverview(
        equipment_id="test-equipment",
        label="Test",
        brand="Test",
        model="Test",
        serial="TEST",
        category="headset",
        assigned_to=None,
        purchase_date=None,
        warranty_end=date(2026, 11, 20),
        days_left=days,
        coverage="expiring_soon",
        verdict="covered",
        open_case_id=None,
        invoice_document_id=None,
    )
    monkeypatch.setattr(notifications, "overview", lambda *_: [item])
    result = notifications.notifications(api_request)
    assert len(result) == (1 if days <= 30 else 0)
    if result:
        assert result[0].id == "warranty_expiring:test-equipment"
        assert result[0].params == {"equipment_label": "Test", "days_left": days}


def test_csv_empty_projection_and_report_error(monkeypatch, api_request):
    report = reports.SavingsReport(
        generated_at=datetime(2026, 11, 20, tzinfo=UTC),
        company="Appelia",
        covered_equipment_eur=0,
        possible_savings_eur=0,
        realized_savings_eur=0,
        journal_ok=True,
        journal_head=None,
        lines=[],
    )
    monkeypatch.setattr(reports, "savings", lambda _: report)
    response = reports.savings_csv(api_request)
    assert bytes(response.body).startswith(b"\xef\xbb\xbfDossier;")
    assert response.headers["content-disposition"].endswith("2026-11-20.csv")

    def fail(_):
        raise ValueError("report failed")

    monkeypatch.setattr(reports, "savings", fail)
    with pytest.raises(ValueError, match="report failed"):
        reports.savings_csv(api_request)
