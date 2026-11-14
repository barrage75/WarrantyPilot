"""Temporary reuse of chat pending extraction of a shared incident service.

The chat route owns equipment identification. A private request state disables
rephrasing, and a preparation-only orchestrator prevents any external action.
Its internal commit is contained by the caller's connection transaction.
"""

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.api.routers.chat import ChatMessageRequest, send_message
from app.contracts.enums import (
    CaseStatus,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    VerdictValue,
)
from app.contracts.models import Case, Incident, Verdict, utc_now
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.tables import cases, incidents, verdicts
from app.intake.transports import Inbox


class PreparationOnly(Orchestrator):
    def __init__(self, session: Session) -> None:
        self.session = session

    async def run(self, case_id: UUID) -> Case:
        row = self.session.execute(select(cases).where(cases.c.id == str(case_id))).one()
        return Case(id=case_id, incident_id=UUID(row.incident_id))


async def create_failure(
    session: Session, reporter_id: UUID, text: str, inbox: Inbox
) -> dict[str, object]:
    conversation_id = str(uuid4())
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(
                state=SimpleNamespace(chat_conversations={conversation_id: []}, services={})
            ),
        }
    )
    # rollback_only means Session.commit() in chat cannot commit the outer unit of work.
    with Session(bind=session.connection(), join_transaction_mode="rollback_only") as chat_session:
        reply = await send_message(
            conversation_id,
            ChatMessageRequest(text=text[:4000], reporter_id=reporter_id),
            request,
            chat_session,
            PreparationOnly(chat_session),
        )
    if reply.case_id is not None:
        case_id = reply.case_id
        incident_id = session.execute(
            select(cases.c.incident_id).where(cases.c.id == case_id)
        ).scalar_one()
        session.execute(
            update(incidents)
            .where(incidents.c.id == incident_id)
            .values(reported_via=IncidentReportedVia.EMAIL.value)
        )
    else:
        incident = Incident(
            reporter_id=reporter_id,
            description=text[:4000],
            reported_via=IncidentReportedVia.EMAIL,
            kind=IncidentKind.FAILURE,
        )
        case = Case(incident_id=incident.id, badge=inbox.badge)
        session.execute(insert(incidents).values(**incident.model_dump(mode="json")))
        session.execute(
            insert(cases).values(
                id=str(case.id),
                incident_id=str(incident.id),
                equipment_id=None,
                status=case.status.value,
                channel=case.channel.value,
                badge=case.badge.value,
                created_at=case.created_at.isoformat(),
                updated_at=case.updated_at.isoformat(),
            )
        )
        case_id = str(case.id)
        append_event(
            session,
            EventType.CASE_CREATED,
            actor="intake",
            case_id=case_id,
            payload={"incident_id": str(incident.id), "reported_via": "email"},
        )
    verdict = Verdict(
        value=VerdictValue.TO_VERIFY,
        missing=reply.questions or ["Évaluer les preuves de garantie avant toute action"],
        explanation_fr="Signalement reçu par e-mail, à vérifier par une personne.",
        explanation_en="Incoming email report requires human verification.",
    )
    session.execute(insert(verdicts).values(**verdict.model_dump(mode="json")))
    session.execute(
        update(cases)
        .where(cases.c.id == case_id)
        .values(
            verdict_id=str(verdict.id),
            status=CaseStatus.AWAITING_VALIDATION.value,
            badge=inbox.badge.value,
            updated_at=utc_now().isoformat(),
        )
    )
    append_event(
        session,
        EventType.VERDICT_COMPUTED,
        actor="intake",
        case_id=case_id,
        payload={"value": "to_verify", "reported_via": "email", "questions": reply.questions},
    )
    return {"case_id": case_id, "verdict": "to_verify", "questions": reply.questions}
