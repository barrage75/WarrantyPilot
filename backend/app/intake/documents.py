import hashlib
import logging
import os
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

from lxml import etree
from pypdf import PdfReader
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.contracts.enums import DocumentKind, DocumentSource, EventType
from app.contracts.models import Document, Fact
from app.core.journal import append_event
from app.core.tables import documents, facts
from app.ingestion.controls.duplicates import find_duplicates
from app.ingestion.controls.suspicious import (
    detect_suspicious,
    scan_text,
    security_fact,
)
from app.ingestion.registry import ExtractorRegistry

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
logger = logging.getLogger(__name__)


class InvalidDocument(ValueError):
    def __init__(self, detail: str, status_code: int = 415) -> None:
        super().__init__(detail)
        self.status_code = status_code


def safe_filename(filename: str) -> str:
    decoded = unquote(filename)
    if (
        not filename
        or any(c in decoded for c in ("/", "\\", "\x00", ":"))
        or decoded in {".", ".."}
        or any(ord(c) < 32 for c in decoded)
    ):
        raise InvalidDocument("Nom de fichier interdit", 400)
    cleaned = re.sub(r"[^\w. -]", "_", filename, flags=re.ASCII).strip(" .")
    if not cleaned or len(cleaned) > 180:
        raise InvalidDocument("Nom de fichier invalide", 400)
    return cleaned


def inspect_document(filename: str, content: bytes) -> tuple[str, str, bool]:
    name = safe_filename(filename)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise InvalidDocument("Document supérieur à 10 Mo", 413)
    suffix = Path(name).suffix.lower()
    if content.startswith(b"%PDF-") and suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(content))
            structured = any(
                name.lower() in {"factur-x.xml", "zugferd-invoice.xml"}
                for name in reader.attachments
            )
            if not reader.pages:
                raise ValueError("PDF vide")
        except Exception as exc:
            raise InvalidDocument("PDF invalide") from exc
        return name, "application/pdf", structured
    if suffix == ".xml" and content.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"<"):
        try:
            root = etree.fromstring(
                content,
                etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False),
            )
            if root.getroottree().docinfo.doctype:
                raise ValueError("DTD interdite")
            if etree.QName(root).localname not in {"Invoice", "CrossIndustryInvoice"}:
                raise ValueError("Facture UBL ou CII attendue")
        except (ValueError, etree.XMLSyntaxError) as exc:
            raise InvalidDocument("Facture XML invalide") from exc
        return name, "application/xml", True
    raise InvalidDocument("Seuls les PDF et factures XML sont acceptés")


class DocumentIntake:
    def __init__(self, root: Path, registry: ExtractorRegistry | None = None) -> None:
        self.root = root
        self.registry = registry or ExtractorRegistry()

    def ingest(
        self,
        session: Session,
        filename: str,
        content: bytes,
        *,
        source: DocumentSource = DocumentSource.UPLOAD,
    ) -> dict[str, object]:
        name, mime, structured = inspect_document(filename, content)
        sha = hashlib.sha256(content).hexdigest()
        previous = session.execute(select(documents.c.id).where(documents.c.sha256 == sha)).first()
        if previous is not None:
            return {"document_id": str(previous.id), "duplicate": True, "reason": "sha256"}
        document = Document(
            kind=DocumentKind.INVOICE,
            filename=name,
            sha256=sha,
            mime=mime,
            source=DocumentSource.FACTURX if structured else source,
        )
        report = (
            detect_suspicious(content)
            if mime == "application/pdf"
            else scan_text(content.decode("utf-8", errors="replace"))
        )
        extracted = security_fact(document, report)
        state = "quarantined" if report.suspicious else "extracted"
        # Never give suspicious documents to an LLM. Structured XML is data only.
        if structured or (not report.suspicious and os.getenv("MISTRAL_API_KEY")):
            try:
                extracted = self.registry.extract(document, content)
            except Exception as exc:
                logger.warning("Intake extraction failed: %s", type(exc).__name__)
                state = "quarantined" if report.suspicious else "pending_extraction"
            if report.suspicious and not any(f.field == "security.suspicious" for f in extracted):
                extracted.extend(security_fact(document, report))
        elif not report.suspicious:
            state = "pending_extraction"
        if any(f.field == "security.suspicious" for f in extracted):
            state = "quarantined"
        known: list[tuple[Document, list[Fact]]] = []
        for row in session.execute(select(documents)).mappings():
            known_document = Document.model_validate(dict(row))
            known_facts = [
                Fact.model_validate(dict(fact))
                for fact in session.execute(
                    select(facts).where(facts.c.document_id == row["id"])
                ).mappings()
            ]
            known.append((known_document, known_facts))
        duplicates = find_duplicates([*known, (document, extracted)]).duplicates
        duplicate = next((d for d in duplicates if d.document_id == document.id), None)
        if duplicate is not None:
            return {
                "document_id": str(duplicate.kept_document_id),
                "duplicate": True,
                "reason": duplicate.reason,
            }
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{sha}{Path(name).suffix.lower()}"
        # Content addressing prevents client filenames from becoming filesystem paths.
        path.write_bytes(content)
        document.filename = str(path)
        session.execute(insert(documents).values(**document.model_dump(mode="json")))
        for fact in extracted:
            session.execute(insert(facts).values(**fact.model_dump(mode="json")))
            append_event(
                session,
                EventType.FACT_EXTRACTED,
                actor="system",
                payload={"fact_id": str(fact.id), "document_id": str(document.id)},
            )
        append_event(
            session,
            EventType.FOLLOWUP_RECEIVED,
            actor="system",
            payload={
                "component": "intake",
                "intake_kind": "document",
                "document_id": str(document.id),
                "original_filename": name,
                "source": source.value,
                "state": state,
                "untrusted": True,
            },
        )
        return {
            "document_id": str(document.id),
            "duplicate": False,
            "state": state,
            "suspicious": report.suspicious
            or any(f.field == "security.suspicious" for f in extracted),
            "facts": len(extracted),
        }
