from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.contracts.enums import DocumentKind, DocumentSource
from app.contracts.models import Document, Equipment, Person

DATA_DIRECTORY = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppeliaDataset:
    people: tuple[Person, ...]
    equipment: tuple[Equipment, ...]
    documents: tuple[Document, ...]
    suppliers: tuple[dict[str, Any], ...]
    annotations: tuple[dict[str, Any], ...]
    traps: tuple[dict[str, Any], ...]
    demo_cases: tuple[dict[str, Any], ...]
    equipment_records: tuple[dict[str, Any], ...]


def load_dataset(directory: Path | None = None) -> AppeliaDataset:
    """Load the committed synthetic records without writing to or connecting to a database."""
    data_directory = directory or DATA_DIRECTORY
    people_records = _read_json(data_directory / "people.json")
    equipment_records = _read_json(data_directory / "equipment.json")
    suppliers = _read_json(data_directory / "suppliers.json")
    document_records = _read_json(data_directory / "documents.json")
    annotations = _read_json(data_directory / "annotations.json")
    trap_data = _read_json(data_directory / "traps.json")

    people = tuple(
        Person(
            id=UUID(record["id"]),
            name=f"{record['first_name']} {record['last_name']}",
            email=record["email"],
            role=record["role"],
        )
        for record in people_records
    )
    equipment = tuple(
        Equipment(
            id=UUID(record["id"]),
            brand=record["brand"],
            model=record["model"],
            serial=record["serial"],
            category=record["category"],
            assigned_to=UUID(record["assigned_to"]) if record["assigned_to"] else None,
            purchase_price=record["purchase_price"],
            currency=record["currency"],
            in_loan_stock=record["in_loan_stock"],
            purchase_date=record["purchase_date"],
            delivery_date=record["delivery_date"],
        )
        for record in equipment_records
    )
    documents = tuple(
        Document(
            id=UUID(record["id"]),
            kind=DocumentKind(record["kind"]),
            filename=record["filename"],
            sha256=record["sha256"],
            mime=record["mime"],
            source=DocumentSource(record["source"]),
            untrusted=True,
        )
        for record in document_records
    )
    return AppeliaDataset(
        people=people,
        equipment=equipment,
        documents=documents,
        suppliers=tuple(suppliers),
        annotations=tuple(annotations),
        traps=tuple(trap_data["traps"]),
        demo_cases=tuple(trap_data["demo_cases"]),
        equipment_records=tuple(equipment_records),
    )


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)
