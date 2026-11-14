from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from app.contracts.enums import (
    DocumentKind,
    DocumentSource,
    FactField,
    FactSource,
    RightType,
)
from app.contracts.interfaces import DocumentExtractor
from app.contracts.models import Document, Equipment, Fact, Person, Provenance, Right
from app.ingestion.registry import ExtractorRegistry
from app.ingestion.text_invoice import TextInvoiceExtractor

from .constants import UUID_NAMESPACE

DATA_DIRECTORY = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppeliaDataset:
    people: tuple[Person, ...]
    equipment: tuple[Equipment, ...]
    documents: tuple[Document, ...]
    facts: tuple[Fact, ...]
    rights: tuple[Right, ...]
    suppliers: tuple[dict[str, Any], ...]
    annotations: tuple[dict[str, Any], ...]
    traps: tuple[dict[str, Any], ...]
    demo_cases: tuple[dict[str, Any], ...]
    equipment_records: tuple[dict[str, Any], ...]


def load_dataset(
    directory: Path | None = None,
    *,
    facturx_extractor: DocumentExtractor | None = None,
    on_document: Callable[[int, int], None] | None = None,
) -> AppeliaDataset:
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
            invoice_number=record["invoice_number"],
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
    documents_by_filename = {item.filename: item for item in documents}
    equipment_by_serial = {item["serial"]: item for item in equipment_records}
    equipment_ids = {serial: UUID(item["id"]) for serial, item in equipment_by_serial.items()}
    annotations_by_filename = {item["filename"]: item for item in annotations}
    extracted_facts: list[Fact] = []
    registry = facturx_extractor or ExtractorRegistry()
    if on_document is not None:
        on_document(0, len(documents))
    for index, document in enumerate(documents, start=1):
        if document.kind != DocumentKind.INVOICE:
            if on_document is not None:
                on_document(index, len(documents))
            continue
        annotation = annotations_by_filename[document.filename]
        line_serials = [line["serials"] for line in annotation["lines"]]
        related_equipment = list(
            dict.fromkeys(equipment_ids[serial] for serials in line_serials for serial in serials)
        )
        extractor = (
            registry if document.source == DocumentSource.FACTURX else TextInvoiceExtractor()
        )
        for fact in extractor.extract(document, (data_directory / document.filename).read_bytes()):
            line_match = re.match(r"lines\[(\d+)\]\.", fact.field)
            serials = (
                line_serials[int(line_match[1])]
                if line_match is not None
                else [serial for line in line_serials for serial in line]
            )
            associated_ids = (
                list(dict.fromkeys(equipment_ids[serial] for serial in serials))
                if serials
                else related_equipment
            )
            for equipment_id in associated_ids:
                key = f"{fact.field}:{fact.value}:{equipment_id}"
                provenance = Provenance(
                    id=uuid5(document.id, f"provenance:{key}"),
                    document_id=document.id,
                    page=fact.provenance.page,
                    excerpt=fact.provenance.excerpt,
                    char_span=fact.provenance.char_span,
                )
                extracted_facts.append(
                    fact.model_copy(
                        update={
                            "id": uuid5(document.id, key),
                            "equipment_id": equipment_id,
                            "provenance": provenance,
                        }
                    )
                )
        if on_document is not None:
            on_document(index, len(documents))

    facts = list(extracted_facts)
    rights: list[Right] = []
    equipment_records_by_scenario = {
        item["scenario"]: item for item in equipment_records if item["scenario"]
    }

    def add_support_fact(
        item: dict[str, Any],
        document: Document,
        field: FactField,
        value: Any,
        excerpt: str,
    ) -> None:
        key = f"{item['id']}:{field.value}:{value}"
        facts.append(
            Fact(
                id=uuid5(document.id, key),
                equipment_id=UUID(item["id"]),
                document_id=document.id,
                field=field.value,
                value=value,
                provenance=Provenance(
                    id=uuid5(document.id, f"provenance:{key}"),
                    document_id=document.id,
                    excerpt=excerpt,
                ),
                confidence=1,
                source=FactSource.STRUCTURED,
            )
        )

    def add_right(
        item: dict[str, Any],
        document: Document,
        right_type: RightType,
        rule_id: str,
        start: date,
        end: date,
        excerpt: str,
    ) -> None:
        key = f"{item['id']}:{rule_id}"
        rights.append(
            Right(
                id=uuid5(UUID_NAMESPACE, key),
                equipment_id=UUID(item["id"]),
                right_type=right_type,
                rule_id=rule_id,
                start_date=start,
                end_date=end,
                evidence=[
                    Provenance(
                        id=uuid5(document.id, f"right:{key}"),
                        document_id=document.id,
                        excerpt=excerpt,
                    )
                ],
            )
        )

    lease_document = documents_by_filename["documents/contrat-location-imprimantes.pdf"]
    lease_start = date(2024, 1, 15)
    lease_end = date(2027, 1, 14)
    for item in equipment_records:
        if item["acquisition_mode"] == "lease":
            add_right(
                item,
                lease_document,
                RightType.LEASE_CONTRACT,
                "lease-hp-laserjet",
                lease_start,
                lease_end,
                "Période du 2024-01-15 au 2027-01-14.",
            )
            add_support_fact(
                item,
                lease_document,
                FactField.LEASE_CONTRACT,
                True,
                "Matériel listé au contrat de location LocaPrint Test.",
            )

    certificate_by_scenario = {
        "trap-10": documents_by_filename["documents/jabra-warranty-plus-001.pdf"],
        "warranty-plus-2": documents_by_filename["documents/jabra-warranty-plus-002.pdf"],
    }
    for scenario, document in certificate_by_scenario.items():
        item = equipment_records_by_scenario[scenario]
        extension_months = int(item["warranty_plus_months"])
        warranty_end = _add_months(
            date.fromisoformat(item["purchase_date"]),
            int(item["warranty_months"]),
        ) - timedelta(days=1)
        extension_start = warranty_end + timedelta(days=1)
        extension_end = _add_months(extension_start, extension_months) - timedelta(days=1)
        add_right(
            item,
            document,
            RightType.EXTENSION,
            "jabra-warranty-plus",
            extension_start,
            extension_end,
            f"Warranty+ : extension_months {extension_months}.",
        )
        add_support_fact(
            item,
            document,
            FactField.WARRANTY_PLUS_CERTIFICATE,
            True,
            "Jabra Warranty+ Confirmation Notice.",
        )
        add_support_fact(
            item,
            document,
            FactField.EXTENSION_MONTHS,
            extension_months,
            f"extension_months : {extension_months}.",
        )

    dell_document = documents_by_filename["documents/contrat-dell-prosupport.pdf"]
    dell_laptops = [
        item
        for item in equipment_records
        if item["category"] == "laptop" and item["brand"] == "Dell"
    ]
    covered_dell_laptops = [
        next(item for item in dell_laptops if item["scenario"] == "demo-dell"),
        *[item for item in dell_laptops if item["scenario"] != "demo-dell"][:19],
    ]
    for item in covered_dell_laptops:
        add_right(
            item,
            dell_document,
            RightType.EXTENSION,
            "dell-prosupport",
            date(2025, 1, 1),
            date(2027, 12, 31),
            "Contrat Dell ProSupport, extension_months : 36.",
        )
        add_support_fact(
            item,
            dell_document,
            FactField.SERVICE_CONTRACT,
            True,
            "Dell ProSupport — numéro de série couvert.",
        )
        add_support_fact(
            item,
            dell_document,
            FactField.EXTENSION_MONTHS,
            36,
            "extension_months : 36.",
        )

    return AppeliaDataset(
        people=people,
        equipment=equipment,
        documents=documents,
        facts=tuple(facts),
        rights=tuple(rights),
        suppliers=tuple(suppliers),
        annotations=tuple(annotations),
        traps=tuple(trap_data["traps"]),
        demo_cases=tuple(trap_data["demo_cases"]),
        equipment_records=tuple(equipment_records),
    )


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return value.replace(year=year, month=month, day=min(value.day, last_day))
