from uuid import UUID

from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from app.contracts.enums import CaseStatus, EventType, IncidentReportedVia, VerdictValue
from app.contracts.models import Verdict, utc_now
from app.core.journal import append_event
from app.core.tables import cases, verdicts
from app.intake.reporting import report_failure
from app.intake.transports import Inbox


async def create_failure(
    session: Session, reporter_id: UUID, text: str, inbox: Inbox
) -> dict[str, object]:
    report = report_failure(
        session,
        reporter_id,
        text[:4000],
        reported_via=IncidentReportedVia.EMAIL,
        create_unidentified=True,
        badge=inbox.badge,
    )
    case_id = report.case_id
    verdict = Verdict(
        value=VerdictValue.TO_VERIFY,
        missing=report.questions or ["Évaluer les preuves de garantie avant toute action"],
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
        actor="system",
        case_id=case_id,
        payload={"value": "to_verify", "reported_via": "email", "questions": report.questions},
    )
    return {"case_id": case_id, "verdict": "to_verify", "questions": report.questions}
