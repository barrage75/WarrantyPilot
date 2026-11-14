from __future__ import annotations

import json
import mailbox
import shutil
import sys
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import NAMESPACE_URL, uuid5

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.orm import Session

from app.contracts.enums import EventType, PurchaseGuardState, RightType
from app.contracts.models import Provenance, utc_now
from app.contracts.models import Settings as PolicySettings
from app.core.auth import access_role_for_job
from app.core.journal import append_event
from app.core.settings import AppSettings
from app.core.settings_store import write_settings
from app.core.tables import (
    Base,
    documents,
    equipment,
    equipment_documents,
    equipment_suppliers,
    events,
    facts,
    people,
    purchase_requests,
    rights,
    suppliers,
)
from app.followup.reminders import ReminderOutbox

if TYPE_CHECKING:
    from appelia.load import AppeliaDataset


def _load_appelia_dataset() -> AppeliaDataset:
    repository_root = str(Path(__file__).resolve().parents[3])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
    from data.appelia.load import load_dataset

    return cast("AppeliaDataset", load_dataset())


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def archive_journal(engine: Engine, settings: AppSettings) -> dict[str, Any]:
    stamp = utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    archive_dir = settings.journal_archive_dir.expanduser() / stamp
    archive_dir.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    if inspect(engine).has_table(events.name):
        with engine.connect() as connection:
            rows = [
                dict(row)
                for row in connection.execute(select(events).order_by(events.c.seq)).mappings()
            ]
    journal_path = archive_dir / "events.jsonl"
    with journal_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    anchor_file = settings.anchor_file.expanduser()
    if anchor_file.exists():
        shutil.copy2(anchor_file, archive_dir / anchor_file.name)
    return {
        "archive": str(archive_dir),
        "archived_events": len(rows),
        "archived_last_hash": str(rows[-1]["hash"]) if rows else None,
    }


def reset_demo(engine: Engine, settings: AppSettings, *, actor: str = "system") -> None:
    if engine.dialect.name != "sqlite":
        raise ValueError("demo reset is restricted to the local SQLite database")
    archive = archive_journal(engine, settings)
    ReminderOutbox(settings.followup_outbox_path).clear()
    maildir_path = settings.maildir_path.expanduser()
    if maildir_path.is_symlink():
        maildir_path.unlink()
    elif maildir_path.exists():
        shutil.rmtree(maildir_path)
    maildir = mailbox.Maildir(str(maildir_path), create=True)
    maildir.add_folder("sent")
    settings.email_sent_ledger_path.expanduser().unlink(missing_ok=True)
    database_path = engine.url.database
    if database_path and database_path != ":memory:":
        db_path = Path(database_path).expanduser()
        engine.dispose()
        for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            if path.exists():
                path.unlink()
    else:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER IF EXISTS events_no_update"))
            connection.execute(text("DROP TRIGGER IF EXISTS events_no_delete"))
            Base.metadata.drop_all(connection)
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    settings.anchor_file.expanduser().unlink(missing_ok=True)
    alembic_config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    with engine.connect() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")
    dataset = _load_appelia_dataset()
    with Session(engine) as session, session.begin():
        session.execute(
            people.insert(),
            [
                {
                    "id": str(person.id),
                    "name": person.name,
                    "email": person.email,
                    "role": person.role,
                    "access_role": access_role_for_job(person.role),
                }
                for person in dataset.people
            ],
        )
        session.execute(
            suppliers.insert(),
            [
                {
                    "id": supplier["id"],
                    "name": supplier["name"],
                    "address": supplier["address"],
                    "postal_code": supplier["postal_code"],
                    "city": supplier["city"],
                    "country": supplier["country"],
                    "siret": supplier["siret"],
                    "email": supplier["email"],
                }
                for supplier in dataset.suppliers
            ],
        )
        session.execute(
            equipment.insert(),
            [
                {
                    "id": str(item.id),
                    "brand": item.brand,
                    "model": item.model,
                    "serial": item.serial,
                    "category": item.category,
                    "assigned_to": str(item.assigned_to) if item.assigned_to else None,
                    "purchase_price": item.purchase_price,
                    "currency": item.currency,
                    "in_loan_stock": item.in_loan_stock,
                    "purchase_date": item.purchase_date,
                    "invoice_number": item.invoice_number,
                    "delivery_date": item.delivery_date,
                    "ship_date": item.ship_date,
                }
                for item in dataset.equipment
            ],
        )
        supplier_ids = {supplier["id"] for supplier in dataset.suppliers}
        session.execute(
            equipment_suppliers.insert(),
            [
                {
                    "equipment_id": item["id"],
                    "supplier_id": item["supplier_id"],
                }
                for item in dataset.equipment_records
                if item["supplier_id"] in supplier_ids
            ],
        )
        document_ids = {item.filename: item.id for item in dataset.documents}
        equipment_ids = {item["serial"]: item["id"] for item in dataset.equipment_records}
        document_links = {
            (equipment_ids[serial], str(document_ids[annotation["filename"]]))
            for annotation in dataset.annotations
            if annotation["filename"] in document_ids
            for line in annotation["lines"]
            for serial in line["serials"]
            if serial in equipment_ids
        }
        session.execute(
            documents.insert(),
            [
                {
                    "id": str(item.id),
                    "kind": item.kind.value,
                    "filename": item.filename,
                    "sha256": item.sha256,
                    "mime": item.mime,
                    "source": item.source.value,
                    "untrusted": item.untrusted,
                }
                for item in dataset.documents
            ],
        )
        session.execute(
            equipment_documents.insert(),
            [
                {"equipment_id": equipment_id, "document_id": document_id}
                for equipment_id, document_id in sorted(document_links)
            ],
        )
        if dataset.facts:
            session.execute(
                facts.insert(),
                [
                    {
                        "id": str(item.id),
                        "equipment_id": str(item.equipment_id) if item.equipment_id else None,
                        "document_id": str(item.document_id) if item.document_id else None,
                        "incident_id": str(item.incident_id) if item.incident_id else None,
                        "field": item.field,
                        "value": item.value,
                        "provenance": item.provenance.model_dump(mode="json"),
                        "confidence": item.confidence,
                        "source": item.source.value,
                    }
                    for item in dataset.facts
                ],
            )
        if dataset.rights:
            session.execute(
                rights.insert(),
                [
                    {
                        "id": str(item.id),
                        "equipment_id": str(item.equipment_id),
                        "right_type": item.right_type.value,
                        "rule_id": item.rule_id,
                        "start_date": item.start_date,
                        "end_date": item.end_date,
                        "evidence": [proof.model_dump(mode="json") for proof in item.evidence],
                    }
                    for item in dataset.rights
                ],
            )
        paul = next(person for person in dataset.people if person.name == "Paul Martin")
        paul_headset = next(
            item
            for item in dataset.equipment
            if item.assigned_to == paul.id and item.brand == "Jabra" and item.model == "Evolve2 65"
        )
        warranty_start = paul_headset.purchase_date or settings.demo_today
        annotation = next(
            (
                item
                for item in dataset.annotations
                if item["invoice_number"] == paul_headset.invoice_number
            ),
            None,
        )
        evidence: list[dict[str, Any]] = []
        if annotation is not None:
            document = next(
                item for item in dataset.documents if item.filename == annotation["filename"]
            )
            evidence = [
                Provenance(
                    document_id=document.id,
                    page=annotation["pages"]["invoice_date"],
                    excerpt=f"Facture {annotation['invoice_number']} pour le casque attribué.",
                ).model_dump(mode="json")
            ]
        session.execute(
            rights.insert().values(
                id=str(uuid5(NAMESPACE_URL, f"warrantypilot:appelia:right:{paul_headset.id}")),
                equipment_id=str(paul_headset.id),
                right_type=RightType.MANUFACTURER_WARRANTY.value,
                rule_id="jabra-evolve",
                start_date=warranty_start,
                end_date=_add_months(warranty_start, 24) - timedelta(days=1),
                evidence=evidence,
            )
        )
        session.execute(
            purchase_requests.insert().values(
                id=str(uuid5(NAMESPACE_URL, "warrantypilot:appelia:paul-martin-purchase")),
                requester_id=str(paul.id),
                equipment_id=str(paul_headset.id),
                case_id=None,
                item_description="Jabra Evolve2 65 neuf",
                amount="120.00",
                state=PurchaseGuardState.RECOMMENDATION.value,
                decision_reason=None,
                cancelled_at=None,
                resolved_at=None,
            )
        )
        allowlist = list(
            dict.fromkeys(
                [
                    *(supplier["email"] for supplier in dataset.suppliers),
                    "warranty@revendeur-test.example",
                    "support@jabra.example",
                    "support@locaprint-test.example",
                ]
            )
        )
        write_settings(
            session,
            PolicySettings(
                auto_send_threshold_eur=Decimal("300"),
                email_allowlist=allowlist,
            ),
        )
        append_event(
            session,
            EventType.DEMO_RESET,
            actor=actor,
            payload={
                **archive,
                "records_loaded": (
                    len(dataset.people)
                    + len(dataset.equipment)
                    + len(dataset.documents)
                    + len(dataset.facts)
                    + len(dataset.rights)
                    + len(dataset.suppliers)
                    + len(document_links)
                    + 1
                ),
            },
        )


def main() -> int:
    from app.core.db import make_engine
    from app.core.journal import configure_journal_key
    from app.core.settings import get_settings

    settings = get_settings()
    if settings.environment != "dev" or not settings.demo_mode:
        print("demo seed is restricted to WP_ENV=dev with demo_mode", file=sys.stderr)
        return 2
    configure_journal_key(settings.journal_anchor_key)
    engine = make_engine(settings.database_url)
    try:
        reset_demo(engine, settings, actor="system")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
