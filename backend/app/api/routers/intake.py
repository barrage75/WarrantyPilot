"""Local intake endpoints; bounded multipart parsing uses Python's MIME parser."""

import os
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.intake.documents import MAX_DOCUMENT_BYTES, DocumentIntake, InvalidDocument
from app.intake.service import IntakeService
from app.intake.transports import MaildirInbox

router = APIRouter(tags=["intake"])


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
    intake: IntakeService = Depends(get_intake), session: Session = Depends(get_session)
) -> dict[str, object]:
    try:
        return await intake.poll(session)
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
        result = intake.documents.ingest(session, part.get_filename() or "", content)
        session.commit()
        return result
    except InvalidDocument as exc:
        session.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
