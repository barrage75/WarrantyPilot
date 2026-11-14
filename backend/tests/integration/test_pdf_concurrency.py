import asyncio
from threading import Event, get_ident
from types import SimpleNamespace
from uuid import uuid4

import pytest
from data.appelia import load
from sqlalchemy import func, insert, select

from app.api.routers.scan import _run_scan
from app.contracts.models import Fact, Provenance
from app.core.db import create_schema, make_engine, make_session_factory
from app.core.tables import documents, events, facts, people
from app.ingestion.pdf_executor import PDF_EXECUTOR
from app.ingestion.registry import ExtractorRegistry
from app.intake import documents as intake_documents
from app.intake.documents import DocumentIntake


@pytest.fixture
def file_sessions(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'concurrency.sqlite3'}")
    create_schema(engine)
    try:
        yield engine, make_session_factory(engine)
    finally:
        engine.dispose()


async def test_upload_extraction_waits_for_at_most_one_scan_document(
    file_sessions, tmp_path, app_settings, monkeypatch
):
    _, factory = file_sessions
    first_scan_started = Event()
    release_scan = Event()
    upload_queued = asyncio.Event()
    seen = []
    submissions = 0
    original_submit = PDF_EXECUTOR.submit

    def submit(*args, **kwargs):
        nonlocal submissions
        submissions += 1
        future = original_submit(*args, **kwargs)
        if submissions == 2:
            upload_queued.set()
        return future

    class ScanExtractor:
        def extract(self, document, content):
            seen.append(document.filename)
            if len(seen) == 1:
                first_scan_started.set()
                assert release_scan.wait(10), "scan was not released"
            return []

    class UploadExtractor:
        def extract(self, document, content):
            assert len(seen) == 1, "upload waited behind multiple scan documents"
            return []

    monkeypatch.setattr(PDF_EXECUTOR, "submit", submit)
    monkeypatch.setattr(load, "TextInvoiceExtractor", ScanExtractor)
    application = SimpleNamespace(
        state=SimpleNamespace(
            scans={"test": {}},
            services={"extractor": ScanExtractor()},
            app_settings=app_settings,
            session_factory=factory,
        )
    )
    intake = DocumentIntake(tmp_path / "uploads", ExtractorRegistry(facturx=UploadExtractor()))
    scan_task = asyncio.create_task(_run_scan(application, "test"))
    upload_task = None
    with factory() as session:
        try:
            assert await asyncio.to_thread(first_scan_started.wait, 5)
            upload_task = asyncio.create_task(
                intake.ingest_async(session, "upload.xml", b"<Invoice><ID>upload</ID></Invoice>")
            )
            await asyncio.wait_for(upload_queued.wait(), 5)
            assert not scan_task.done()
            release_scan.set()
            result = await asyncio.wait_for(upload_task, 10)
            session.commit()
            assert result["state"] == "extracted"
            await asyncio.wait_for(scan_task, 10)
            assert application.state.scans["test"]["status"] == "completed"
            assert len(seen) == 60
            assert application.state.scans["test"]["documents_done"] == 65
        finally:
            release_scan.set()
            await asyncio.gather(
                scan_task, *([upload_task] if upload_task else []), return_exceptions=True
            )


async def test_upload_inspection_and_extraction_leave_database_available(
    file_sessions, tmp_path, monkeypatch
):
    engine, factory = file_sessions
    inspected = Event()
    extracted = Event()
    original_inspect = intake_documents.inspect_document
    with factory() as session:

        def assert_writer_available():
            assert not session.in_transaction()
            with engine.begin() as connection:
                connection.execute(insert(people).values(id=str(uuid4()), name="Other writer"))

        def inspect(filename, content):
            assert_writer_available()
            inspected.set()
            return original_inspect(filename, content)

        class Extractor:
            def extract(self, document, content):
                assert_writer_available()
                extracted.set()
                return [
                    Fact(
                        document_id=document.id,
                        field="invoice_number",
                        value="upload",
                        source="structured",
                        confidence=1,
                        provenance=Provenance(document_id=document.id, excerpt="upload"),
                    )
                ]

        monkeypatch.setattr(intake_documents, "inspect_document", inspect)
        intake = DocumentIntake(tmp_path / "uploads", ExtractorRegistry(facturx=Extractor()))
        result = await intake.ingest_async(session, "upload.xml", b"<Invoice/>")
        assert inspected.is_set() and extracted.is_set()
        assert session.in_transaction()
        assert result["duplicate"] is False
        assert session.scalar(select(func.count()).select_from(documents)) == 1
        assert session.scalar(select(func.count()).select_from(facts)) == 1
        assert session.scalar(select(func.count()).select_from(events)) == 2
        session.rollback()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(documents)) == 0
        assert session.scalar(select(func.count()).select_from(facts)) == 0
        assert session.scalar(select(func.count()).select_from(events)) == 0
        assert session.scalar(select(func.count()).select_from(people)) == 2


async def test_async_dataset_matches_synchronous_facts_rights_and_progress(monkeypatch):
    sync_progress = []
    async_progress = []
    loop_thread = get_ident()
    progress_threads = []
    worker_threads = []
    original_run_pdf_task = load.run_pdf_task

    async def run_step(step):
        def run():
            worker_threads.append(get_ident())
            return step()

        return await original_run_pdf_task(run)

    def on_document(done, total):
        progress_threads.append(get_ident())
        async_progress.append((done, total))

    monkeypatch.setattr(load, "run_pdf_task", run_step)
    expected = await asyncio.to_thread(
        load.load_dataset, on_document=lambda done, total: sync_progress.append((done, total))
    )
    actual = await load.load_dataset_async(on_document=on_document)
    assert actual == expected
    assert async_progress == sync_progress == [(done, 65) for done in range(66)]
    assert progress_threads == [loop_thread] * 66
    assert len(worker_threads) == 60
    assert len(set(worker_threads)) == 1
    assert loop_thread not in worker_threads
