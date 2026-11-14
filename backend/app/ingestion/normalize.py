import re
from collections import defaultdict
from uuid import UUID

from app.contracts.enums import FactField
from app.contracts.models import Equipment, Fact
from app.ingestion import fields as invoice_fields
from app.ingestion.controls.duplicates import normalize as normalize_value

_LINE_FIELD = re.compile(r"lines\[(\d+)\]\.([a-z_]+)")

_HEADER_ALIASES = {
    invoice_fields.SUPPLIER_NAME: FactField.RESELLER_NAME.value,
    invoice_fields.SUPPLIER_ADDRESS: FactField.RESELLER_ADDRESS.value,
    invoice_fields.CUSTOMER_NAME: FactField.BUYER_NAME.value,
    invoice_fields.WARRANTY_DURATION_MONTHS: FactField.WARRANTY_TERM_MONTHS.value,
}
_LINE_ALIASES = {
    invoice_fields.MODEL: (FactField.MODEL_NUMBER.value, FactField.PRODUCT_TYPE.value),
    invoice_fields.SERIAL: (FactField.SERIAL_NUMBER.value,),
    invoice_fields.SKU: (FactField.SKU.value,),
    invoice_fields.WARRANTY_DURATION_MONTHS: (FactField.WARRANTY_TERM_MONTHS.value,),
}


def _line_parts(fact: Fact) -> tuple[int, str] | None:
    match = _LINE_FIELD.fullmatch(fact.field)
    return (int(match[1]), match[2]) if match else None


def _document_id(fact: Fact) -> UUID | None:
    return fact.document_id or fact.provenance.document_id


def _serial_values(value: object) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else re.split(r"[,;|\n]+", str(value))
    return [str(item).strip() for item in values if item is not None and str(item).strip()]


def _normalized_facts(fact: Fact, fields: tuple[str, ...]) -> list[Fact]:
    return [
        fact if field == fact.field else fact.model_copy(update={"field": field})
        for field in fields
    ]


def normalize_facts(facts: list[Fact], equipment: Equipment) -> list[Fact]:
    line_groups: dict[tuple[UUID, int], list[Fact]] = defaultdict(list)
    line_documents: set[UUID] = set()

    for fact in facts:
        parts = _line_parts(fact)
        if parts:
            document_id = _document_id(fact)
            if document_id is not None:
                line_documents.add(document_id)
                if fact.equipment_id in (None, equipment.id):
                    line_groups[(document_id, parts[0])].append(fact)

    matched_lines: dict[tuple[UUID, int], set[str] | None] = {}
    matched_documents: set[UUID] = set()
    for key, line_facts in line_groups.items():
        serial_facts = []
        models = []
        for fact in line_facts:
            parts = _line_parts(fact)
            if parts and parts[1] == invoice_fields.SERIAL:
                serial_facts.append(fact)
            elif parts and parts[1] == invoice_fields.MODEL:
                models.append(fact.value)
        serials = [value for fact in serial_facts for value in _serial_values(fact.value)]
        if serials:
            matching_serial_values = {
                normalize_value(value)
                for value in serials
                if normalize_value(value) == normalize_value(equipment.serial)
            }
            if not matching_serial_values:
                continue
            matched_lines[key] = matching_serial_values
            matched_documents.add(key[0])
            continue

        if any(normalize_value(str(model)) == normalize_value(equipment.model) for model in models):
            matched_lines[key] = None
            matched_documents.add(key[0])

    normalized: list[Fact] = []
    for fact in facts:
        parts = _line_parts(fact)
        if parts:
            document_id = _document_id(fact)
            if document_id is None:
                continue
            key = (document_id, parts[0])
            if key not in matched_lines or fact.equipment_id not in (None, equipment.id):
                continue
            matching_serials = matched_lines[key]
            if parts[1] == invoice_fields.SERIAL and matching_serials is not None:
                values = [
                    value
                    for value in _serial_values(fact.value)
                    if normalize_value(value) in matching_serials
                ]
                for value in values:
                    normalized.extend(
                        _normalized_facts(
                            fact.model_copy(update={"value": value}),
                            _LINE_ALIASES.get(parts[1], (fact.field,)),
                        )
                    )
                continue
            normalized.extend(_normalized_facts(fact, _LINE_ALIASES.get(parts[1], (fact.field,))))
            continue

        if fact.equipment_id not in (None, equipment.id):
            continue
        document_id = _document_id(fact)
        if document_id in line_documents and document_id not in matched_documents:
            continue
        normalized.extend(_normalized_facts(fact, (_HEADER_ALIASES.get(fact.field, fact.field),)))

    return normalized
