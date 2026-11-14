"""Local intake endpoints; bounded multipart parsing uses Python's MIME parser."""

import os
from collections.abc import Sequence
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_orchestrator, get_session, require_session
from app.contracts.enums import DocumentSource, EventType
from app.core.auth import Operator
from app.core.orchestrator import Orchestrator
from app.core.tables import documents, events, facts
from app.intake.documents import MAX_DOCUMENT_BYTES, DocumentIntake, InvalidDocument
from app.intake.service import IntakeService
from app.intake.transports import MaildirInbox

router = APIRouter(tags=["intake"])


class DocumentItem(BaseModel):
    id: str
    name: str
    source: DocumentSource
    state: Literal["extracted", "pending_extraction", "quarantined"]
    suspicious: bool
    facts_count: int
    created_at: str | None


class DocumentFact(BaseModel):
    field: str
    value: Any
    confidence: float


class DocumentDetail(DocumentItem):
    facts: list[DocumentFact]


class DocumentPage(BaseModel):
    items: list[DocumentItem]
    total: int
    limit: int
    offset: int


def document_detail(session: Session, document_id: str) -> DocumentDetail:
    row = session.execute(select(documents).where(documents.c.id == document_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    extracted = (
        session.execute(
            select(facts).where(facts.c.document_id == document_id).order_by(facts.c.id)
        )
        .mappings()
        .all()
    )
    receipts = (
        session.execute(
            select(events)
            .where(
                events.c.type == EventType.INTAKE_DOCUMENT_RECEIVED.value,
                events.c.payload["document_id"].as_string() == document_id,
            )
            .order_by(events.c.seq)
        )
        .mappings()
        .all()
    )
    payload = receipts[-1]["payload"] if receipts else {}
    suspicious = any(f["field"] == "security.suspicious" for f in extracted)
    state = payload.get("state")
    if state not in {"extracted", "pending_extraction", "quarantined"}:
        state = "quarantined" if suspicious else "extracted" if extracted else "pending_extraction"
    name = next(
        (
            str(receipt["payload"]["original_filename"])
            for receipt in reversed(receipts)
            if receipt["payload"].get("original_filename")
        ),
        str(row["filename"]),
    )
    return DocumentDetail(
        id=row["id"],
        name=Path(name.replace("\\", "/")).name,
        source=row["source"],
        state=state,
        suspicious=suspicious or state == "quarantined",
        facts_count=len(extracted),
        created_at=receipts[0]["at"] if receipts else None,
        facts=[
            DocumentFact(field=f["field"], value=f["value"], confidence=f["confidence"])
            for f in extracted
        ],
    )


@router.get("/documents", response_model=DocumentPage)
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DocumentPage:
    received_at = (
        select(func.min(events.c.at))
        .where(
            events.c.type == EventType.INTAKE_DOCUMENT_RECEIVED.value,
            events.c.payload["document_id"].as_string() == documents.c.id,
        )
        .correlate(documents)
        .scalar_subquery()
    )
    ids: Sequence[str] = session.scalars(
        select(documents.c.id)
        .order_by(received_at.desc(), documents.c.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return DocumentPage(
        items=[
            DocumentItem.model_validate(document_detail(session, id).model_dump()) for id in ids
        ],
        total=session.scalar(select(func.count()).select_from(documents)) or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, session: Session = Depends(get_session)) -> DocumentDetail:
    return document_detail(session, document_id)


def get_intake(request: Request) -> IntakeService:
    injected = request.app.state.services.get("intake")
    if injected is not None:
        return cast(IntakeService, injected)
    # No shared AppSettings edit: these runtime paths belong to this lot.
    return IntakeService(
        MaildirInbox(Path(os.getenv("WP_INTAKE_MAILDIR", "runtime/inbox"))),
        DocumentIntake(Path(os.getenv("WP_INTAKE_DOCUMENTS", "runtime/intake/documents"))),
    )


@router.post("/intake/poll")
async def poll(
    intake: IntakeService = Depends(get_intake),
    session: Session = Depends(get_session),
    _operator: Operator = Depends(require_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict[str, object]:
    try:
        return await intake.poll(session, orchestrator=orchestrator)
    except Exception:
        session.rollback()
        raise


@router.post(
    "/documents/upload",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload(
    request: Request,
    intake: IntakeService = Depends(get_intake),
    session: Session = Depends(get_session),
    _operator: Operator = Depends(require_session),
) -> dict[str, object]:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data;"):
        raise HTTPException(status_code=415, detail="multipart/form-data requis")
    if "\r" in content_type or "\n" in content_type or len(content_type) > 1024:
        raise HTTPException(status_code=400, detail="En-tête multipart invalide")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_DOCUMENT_BYTES + 65536:
            raise HTTPException(status_code=413, detail="Document supérieur à 10 Mo")
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart() or message.defects:
        raise HTTPException(status_code=400, detail="Corps multipart invalide")
    parts = list(message.iter_parts())
    if len(parts) != 1 or parts[0].get_param("name", header="content-disposition") != "file":
        raise HTTPException(status_code=400, detail="Un seul champ file requis")
    part = parts[0]
    if part.is_multipart() or part.defects:
        raise HTTPException(status_code=400, detail="Fichier multipart invalide")
    content = part.get_payload(decode=True)
    if not isinstance(content, bytes):
        raise HTTPException(status_code=400, detail="Fichier absent")
    try:
        result = await intake.documents.ingest_async(session, part.get_filename() or "", content)
        session.commit()
        return result
    except InvalidDocument as exc:
        session.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
