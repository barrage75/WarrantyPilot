import unicodedata
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.contracts.models import Document, Fact


def normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if c.isalnum())


@dataclass(frozen=True)
class Duplicate:
    document_id: UUID
    kept_document_id: UUID
    reason: Literal["sha256", "invoice_supplier"]


@dataclass(frozen=True)
class DuplicateReport:
    kept: list[tuple[Document, list[Fact]]]
    duplicates: list[Duplicate]


def find_duplicates(items: list[tuple[Document, list[Fact]]]) -> DuplicateReport:
    kept: list[tuple[Document, list[Fact]]] = []
    duplicates: list[Duplicate] = []
    hashes: dict[str, UUID] = {}
    invoices: dict[tuple[str, str], UUID] = {}
    for document, facts in items:
        values = {
            fact.field: normalize(str(fact.value))
            for fact in facts
            if fact.field in {"invoice_number", "supplier_name"} and fact.value is not None
        }
        key = (values.get("invoice_number", ""), values.get("supplier_name", ""))
        sha = document.sha256.casefold()
        owner = hashes.get(sha)
        reason: Literal["sha256", "invoice_supplier"] = "sha256"
        if owner is None and all(key):
            owner = invoices.get(key)
            reason = "invoice_supplier"
        if owner is None:
            owner = document.id
            kept.append((document, facts))
        else:
            duplicates.append(Duplicate(document.id, owner, reason))
        hashes.setdefault(sha, owner)
        if all(key):
            invoices.setdefault(key, owner)
    return DuplicateReport(kept, duplicates)
