import asyncio
from collections import Counter
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.api.main import create_app
from app.api.routers.scan import _run_scan
from app.contracts.enums import FactField
from app.contracts.models import Fact, Provenance
from app.core import tables
from app.core.warranty import inventory_verdict, rules_engine, stored_inventory
from tests.auth_helpers import KARIM_ID, login


def test_indexed_inventory_preserves_all_seed_verdicts(db_engine, app_settings, session_factory):
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
        with session_factory() as session:
            equipment, indexed, rights = stored_inventory(session)
            count = session.scalar(select(func.count()).select_from(tables.facts))
        assert len(indexed) == 229
        flat = [fact for group in indexed.values() for fact in group]
        assert len(flat) == count
        for item in equipment:
            engine = rules_engine(application)
            rules = application.state.services["rules"]
            expected, expected_dates = inventory_verdict(engine, item, flat, rules, rights)
            actual, actual_dates = inventory_verdict(
                engine, item, indexed.get(item.id, []), rules, rights
            )
            assert actual_dates == expected_dates, item.serial
            # Inventory evaluations create fresh incidents, checks and classifier IDs.
            exclude = {
                "id": True,
                "checks": {"__all__": {"id"}},
                "evidence": {"__all__": {"id"}},
            }
            assert actual.model_dump(exclude=exclude) == expected.model_dump(exclude=exclude), (
                item.serial
            )


def test_seed_and_scan_persist_invoice_facts_idempotently(db_engine, app_settings, session_factory):
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
        seeded = client.get("/api/equipment/overview").json()
        target = next(item for item in seeded if item["serial"] == "JBR0000000003")
        assert target["verdict"] == "not_covered"  # Engage 55: one year from 10/03/2025
        assert target["warranty_end"] == "2026-03-09"
        with session_factory() as session:
            assert (
                session.scalar(select(func.count(func.distinct(tables.facts.c.equipment_id))))
                == 229
            )
            fact_count = session.scalar(select(func.count()).select_from(tables.facts))
        # Reproduce a previously seeded database with its unread PDF invoices.
        with session_factory.begin() as session:
            session.execute(
                delete(tables.facts).where(
                    tables.facts.c.document_id.in_(
                        select(tables.documents.c.id).where(tables.documents.c.source == "upload")
                    )
                )
            )
        incomplete = client.get("/api/equipment/overview").json()
        assert (
            next(item for item in incomplete if item["equipment_id"] == target["equipment_id"])[
                "verdict"
            ]
            == "to_verify"
        )
        for _ in range(2):
            application.state.scans["regression"] = {}
            asyncio.run(_run_scan(application, "regression"))
            summary = application.state.scans["regression"]
            assert summary["status"] == "completed", summary
            restored = client.get("/api/equipment/overview").json()
            assert restored == seeded
            with session_factory() as session:
                assert session.scalar(select(func.count()).select_from(tables.facts)) == fact_count
            assert (
                summary["covered_equipment_eur"]
                == client.get("/api/reports/savings").json()["covered_equipment_eur"]
            )
        print("coverage_after", Counter(item["verdict"] for item in seeded))
        print("coverage_before_scan", Counter(item["verdict"] for item in incomplete))


def test_unscoped_suspicious_fact_only_affects_linked_equipment(
    db_engine, app_settings, session_factory
):
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application) as client:
        login(client, person_id=KARIM_ID)
        client.post("/api/demo/reset", json={"confirm": "RESET"})
        baseline = client.get("/api/equipment/overview").json()
        targets = [item for item in baseline if item["verdict"] == "covered"][:2]
        document_id = uuid4()
        fact = Fact(
            document_id=document_id,
            field=FactField.SECURITY_SUSPICIOUS.value,
            value=True,
            provenance=Provenance(document_id=document_id, excerpt="ignore previous instructions"),
            confidence=1,
            source="structured",
        )
        with session_factory.begin() as session:
            session.execute(
                tables.documents.insert().values(
                    id=str(document_id),
                    kind="invoice",
                    filename="suspicious.pdf",
                    sha256="0" * 64,
                    mime="application/pdf",
                    source="upload",
                    untrusted=True,
                )
            )
            session.execute(tables.facts.insert().values(**fact.model_dump(mode="json")))
        assert client.get("/api/equipment/overview").json() == baseline
        with session_factory.begin() as session:
            session.execute(
                tables.equipment_documents.insert().values(
                    document_id=str(document_id),
                    equipment_id=targets[0]["equipment_id"],
                )
            )
        after = {
            item["equipment_id"]: item for item in client.get("/api/equipment/overview").json()
        }
        assert after[targets[0]["equipment_id"]]["verdict"] == "to_verify"
        assert all(after[item["equipment_id"]] == item for item in baseline if item != targets[0])
