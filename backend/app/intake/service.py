import hashlib
import logging
from email.message import EmailMessage
from email.utils import getaddresses
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.contracts.enums import DocumentSource, EventType
from app.core.journal import append_event
from app.core.tables import events, people
from app.intake.chat_bridge import create_failure
from app.intake.classifier import Classifier
from app.intake.documents import DocumentIntake, InvalidDocument, inspect_document_async
from app.intake.transports import Inbox

logger = logging.getLogger(__name__)


class IntakeService:
    def __init__(
        self,
        inbox: Inbox,
        documents: DocumentIntake,
        classifier: Classifier | None = None,
    ) -> None:
        self.inbox = inbox
        self.documents = documents
        self.classifier = classifier or Classifier()

    async def poll(self, session: Session) -> dict[str, object]:
        results: list[dict[str, object]] = []
        # The repository's SQLite engine starts BEGIN IMMEDIATE on first use.
        # Receipt and all domain changes commit together, serializing other pollers.
        session.connection()
        for message in self.inbox.fetch_replies():
            raw = message.as_bytes()
            ids = message.get_all("Message-ID", [])
            message_id = str(ids[0]).strip() if len(ids) == 1 else ""
            # Missing/ambiguous headers still get a durable receipt by content digest.
            identity = message_id if message_id else "sha256:" + hashlib.sha256(raw).hexdigest()
            previous = session.execute(
                select(events.c.id).where(
                    events.c.actor == "system",
                    or_(
                        events.c.type == EventType.INTAKE_MESSAGE_RECEIVED.value,
                        and_(
                            events.c.type == EventType.FOLLOWUP_RECEIVED.value,
                            events.c.payload["component"].as_string() == "intake",
                        ),
                    ),
                    events.c.payload["intake_message_id"].as_string() == identity,
                )
            ).first()
            if previous is not None:
                results.append({"message_id": identity, "state": "duplicate"})
                continue
            result = (
                {"state": "ignored", "reason": "invalid_message_id"}
                if not message_id
                else await self._process(session, message)
            )
            append_event(
                session,
                EventType.INTAKE_MESSAGE_RECEIVED,
                actor="system",
                case_id=str(result["case_id"]) if result.get("case_id") else None,
                payload={
                    "intake_message_id": identity,
                    "untrusted": True,
                    **result,
                },
            )
            if result.get("state") in {"ignored", "quarantined"}:
                logger.info("intake %s reason=%s", result["state"], result.get("reason", ""))
            results.append({"message_id": identity, **result})
        session.commit()
        return {"messages": results}

    async def _process(self, session: Session, message: EmailMessage) -> dict[str, object]:
        bodies: list[str] = [str(message.get("Subject", ""))]
        attachments: list[tuple[str, bytes, tuple[str, str, bool]]] = []
        rejected: list[str] = []
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = part.get_filename()
            if filename is not None or part.get_content_disposition() == "attachment":
                content = part.get_payload(decode=True)
                payload = content if isinstance(content, bytes) else b""
                try:
                    inspection = await inspect_document_async(filename or "", payload)
                except InvalidDocument:
                    rejected.append("invalid_attachment")
                else:
                    attachments.append((filename or "", payload, inspection))
            elif part.get_content_maintype() == "text":
                content = part.get_content()
                if isinstance(content, str):
                    # Scan every text alternative, including HTML, before classification.
                    bodies.append(content)
        text = "\n".join(bodies)
        classification = self.classifier.classify(text, has_invoice=bool(attachments))
        if classification.suspicious:
            return {"state": "quarantined", "reason": "suspicious_body"}
        if classification.kind == "invoice":
            documents = []
            for name, content, inspection in attachments:
                documents.append(
                    await self.documents.ingest_async(
                        session,
                        name,
                        content,
                        source=DocumentSource.GMAIL,
                        inspection=inspection,
                    )
                )
            return {"state": "invoice", "documents": documents, "rejected": rejected}
        if classification.kind != "failure":
            return {"state": "ignored", "reason": "other", "rejected": rejected}
        addresses = getaddresses([str(header) for header in message.get_all("From", [])])
        if len(addresses) != 1:
            return {"state": "ignored", "reason": "unknown_sender"}
        sender = addresses[0][1].casefold()
        if sender.rpartition("@")[2] != "appelia.example":
            return {"state": "ignored", "reason": "unknown_sender"}
        matches = session.execute(
            select(people.c.id).where(func.lower(people.c.email) == sender)
        ).all()
        if len(matches) != 1:
            return {"state": "ignored", "reason": "unknown_sender"}
        result = await create_failure(session, UUID(matches[0].id), text, self.inbox)
        return {"state": "failure", **result}
