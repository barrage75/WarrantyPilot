import asyncio
import json
from threading import get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.api.main import create_app
from app.api.routers import cases, scan


async def test_scan_task_is_retained_until_done(monkeypatch, db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    release = asyncio.Event()

    async def run(*_):
        await release.wait()

    monkeypatch.setattr(scan, "_run_scan", run)
    await scan.start_scan(Request({"type": "http", "app": application}))
    assert len(application.state.scan_tasks) == 1
    task = next(iter(application.state.scan_tasks))
    release.set()
    await task
    await asyncio.sleep(0)
    assert not application.state.scan_tasks


@pytest.mark.parametrize("purchases", [[], [{"amount": 12, "state": "saving_realized"}]])
async def test_scan_purchase_read_runs_off_loop(monkeypatch, app_settings, purchases) -> None:
    loop_thread = get_ident()
    session = MagicMock()
    session.__enter__.return_value = session
    session.execute.return_value.mappings.return_value.all.return_value = purchases

    def totals(current, *_):
        assert get_ident() != loop_thread
        assert current is session
        return {
            "covered_equipment_eur": 20.0,
            "possible_savings_eur": 0.0,
            "realized_savings_eur": 12.0 if purchases else 0.0,
        }

    load_totals = MagicMock(side_effect=totals)
    monkeypatch.setattr(scan, "savings_totals", load_totals)

    def factory():
        assert get_ident() != loop_thread
        return session

    dataset = SimpleNamespace(
        documents=[], facts=[], rights=[], equipment=[], people=[SimpleNamespace(id=uuid4())]
    )
    monkeypatch.setattr(scan, "run_pdf_task", AsyncMock(return_value=dataset))
    application = SimpleNamespace(
        state=SimpleNamespace(
            scans={"scan": {}}, services={}, app_settings=app_settings, session_factory=factory
        )
    )
    await scan._run_scan(application, "scan")
    result = application.state.scans["scan"]
    assert result["status"] == "completed"
    load_totals.assert_called_once()
    assert result["covered_equipment_eur"] == 20.0
    assert result["realized_savings_eur"] == (12 if purchases else 0)


async def test_scan_database_error_is_reported(monkeypatch, app_settings) -> None:
    dataset = SimpleNamespace(
        documents=[], facts=[], rights=[], equipment=[], people=[SimpleNamespace(id=uuid4())]
    )
    monkeypatch.setattr(scan, "run_pdf_task", AsyncMock(return_value=dataset))
    application = SimpleNamespace(
        state=SimpleNamespace(
            scans={"scan": {}},
            services={},
            app_settings=app_settings,
            session_factory=MagicMock(side_effect=RuntimeError("read failed")),
        )
    )
    await scan._run_scan(application, "scan")
    assert application.state.scans["scan"] == {
        "status": "failed",
        "error": "RuntimeError",
        "documents_total": 0,
    }


@pytest.mark.parametrize("empty", [False, True])
async def test_sse_poll_runs_off_loop_without_changing_events(monkeypatch, empty) -> None:
    loop_thread = get_ident()
    row = {
        "seq": 3,
        "at": "now",
        "actor": "system",
        "type": "case_created",
        "payload": {},
        "hash": "abc",
    }
    current = MagicMock()
    current.__enter__.return_value = current
    current.execute.return_value.mappings.return_value.all.return_value = [] if empty else [row]

    def factory():
        assert get_ident() != loop_thread
        return current

    request = MagicMock()
    request.app.state.session_factory = factory
    request.is_disconnected = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr(cases, "_load_case", MagicMock())
    monkeypatch.setattr(cases.asyncio, "sleep", AsyncMock())
    response = await cases.stream_case_events(uuid4(), request, session=MagicMock())
    output = [item async for item in response.body_iterator]
    assert output == (
        []
        if empty
        else [{"id": "3", "event": "case_created", "data": json.dumps(row, separators=(",", ":"))}]
    )


async def test_sse_database_error_propagates(monkeypatch) -> None:
    request = MagicMock()
    request.app.state.session_factory.side_effect = RuntimeError("read failed")
    request.is_disconnected = AsyncMock(return_value=False)
    monkeypatch.setattr(cases, "_load_case", MagicMock())
    response = await cases.stream_case_events(uuid4(), request, session=MagicMock())
    with pytest.raises(RuntimeError, match="read failed"):
        await anext(response.body_iterator)
