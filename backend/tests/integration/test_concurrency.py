import asyncio
import time
from pathlib import Path
from threading import Event

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.api.dependencies import get_orchestrator
from app.api.main import create_app
from app.contracts.enums import CaseStatus, Channel
from app.core.db import create_schema, make_engine, make_session_factory
from app.core.settings import AppSettings
from app.core.tables import cases
from tests.auth_helpers import open_test_session
from tests.integration.helpers import create_case


def _file_database(
    tmp_path: Path, app_settings: AppSettings, filename: str
) -> tuple[AppSettings, Engine, sessionmaker[Session]]:
    database_url = f"sqlite:///{tmp_path / filename}"
    settings = app_settings.model_copy(update={"database_url": database_url})
    engine = make_engine(database_url)
    create_schema(engine)
    return settings, engine, make_session_factory(engine)


@pytest.mark.asyncio
async def test_scan_upload_and_validation_complete_concurrently(
    tmp_path: Path, app_settings: AppSettings
) -> None:
    settings, engine, session_factory = _file_database(
        tmp_path, app_settings, "concurrent-api.sqlite3"
    )
    case, person_id = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(cases)
            .where(cases.c.id == str(case.id))
            .values(status=CaseStatus.AWAITING_VALIDATION.value, channel=Channel.MANUAL.value)
        )
    application = create_app(app_settings=settings, app_engine=engine)
    invoice_path = Path(__file__).resolve().parents[3] / "data/appelia/invoices/invoice-041.pdf"
    invoice = invoice_path.read_bytes()

    try:
        async with application.router.lifespan_context(application):
            operator, token = open_test_session(
                application, role="operator", person_id=str(person_id)
            )
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:

                async def run_requests() -> None:
                    scan_response, upload_response, validation_response = await asyncio.gather(
                        client.post("/api/scan"),
                        client.post(
                            "/api/documents/upload",
                            files={"file": ("invoice-041.pdf", invoice, "application/pdf")},
                        ),
                        client.post(
                            f"/api/cases/{case.id}/validate",
                            json={"person_id": operator.person_id},
                        ),
                    )
                    assert scan_response.status_code == 202, scan_response.text
                    assert upload_response.status_code == 200, upload_response.text
                    assert validation_response.status_code == 200, validation_response.text
                    scan_id = scan_response.json()["scan_id"]
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        scan_result = await client.get(f"/api/scan/{scan_id}")
                        assert scan_result.status_code == 200, scan_result.text
                        if scan_result.json()["status"] != "running":
                            break
                        await asyncio.sleep(0.02)
                    assert scan_result.json()["status"] == "completed", scan_result.text

                await asyncio.wait_for(run_requests(), timeout=10)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_health_remains_responsive_while_orchestrator_waits_for_sqlite_lock(
    tmp_path: Path, app_settings: AppSettings
) -> None:
    settings, engine, session_factory = _file_database(
        tmp_path, app_settings, "sqlite-lock.sqlite3"
    )
    case, _ = create_case(session_factory)
    application = create_app(app_settings=settings, app_engine=engine)
    lock_acquired = Event()
    release_lock = Event()

    def hold_write_lock() -> None:
        with session_factory.begin() as session:
            session.execute(
                update(cases)
                .where(cases.c.id == str(case.id))
                .values(updated_at="2026-01-01T00:00:00+00:00")
            )
            lock_acquired.set()
            release_lock.wait(timeout=2)

    try:
        async with application.router.lifespan_context(application):
            orchestrator = get_orchestrator(Request({"type": "http", "app": application}))
            holder = asyncio.create_task(asyncio.to_thread(hold_write_lock))
            try:
                assert await asyncio.wait_for(asyncio.to_thread(lock_acquired.wait), timeout=2)
                transport = httpx.ASGITransport(app=application)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://testserver"
                ) as client:
                    started = time.monotonic()
                    run_task = asyncio.create_task(orchestrator.run(case.id))
                    await asyncio.sleep(0.05)
                    try:
                        response = await client.get("/api/health")
                        elapsed = time.monotonic() - started
                        lock_still_held = not release_lock.is_set()
                    finally:
                        release_lock.set()
                        await asyncio.wait_for(holder, timeout=2)
                        await asyncio.wait_for(run_task, timeout=5)
                assert response.status_code == 200
                assert lock_still_held
                assert elapsed < 1
            finally:
                release_lock.set()
                await asyncio.wait_for(holder, timeout=2)
    finally:
        release_lock.set()
        engine.dispose()
