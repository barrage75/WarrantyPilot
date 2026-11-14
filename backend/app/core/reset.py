from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.contracts.enums import EventType
from app.core.journal import append_event
from app.core.settings import AppSettings
from app.core.tables import Base, documents, equipment, facts, people, rights

if TYPE_CHECKING:
    from appelia.load import AppeliaDataset


def _load_appelia_dataset() -> AppeliaDataset:
    repository_root = str(Path(__file__).resolve().parents[3])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
    from data.appelia.load import load_dataset

    return cast("AppeliaDataset", load_dataset())


def reset_demo(engine: Engine, settings: AppSettings) -> None:
    if engine.dialect.name != "sqlite":
        raise ValueError("demo reset is restricted to the local SQLite database")
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
                }
                for person in dataset.people
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
                    "delivery_date": item.delivery_date,
                    "ship_date": item.ship_date,
                }
                for item in dataset.equipment
            ],
        )
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
        append_event(
            session,
            EventType.DEMO_RESET,
            payload={
                "records_loaded": (
                    len(dataset.people)
                    + len(dataset.equipment)
                    + len(dataset.documents)
                    + len(dataset.facts)
                    + len(dataset.rights)
                )
            },
        )
