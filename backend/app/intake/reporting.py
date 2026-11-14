from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.contracts.enums import (
    CaseStatus,
    Channel,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    RealityBadge,
)
from app.contracts.models import utc_now
from app.core.checklists import ensure_data_checklist
from app.core.journal import append_event
from app.core.tables import cases, equipment, incidents


@dataclass(frozen=True)
class FailureReport:
    case_id: str | None
    incident_id: str | None
    equipment_id: str | None
    equipment_label: str | None
    questions: list[str]


def _equipment_category(text: str) -> str | None:
    folded = text.casefold()
    terms = (
        (("casque", "écouteur", "micro"), "headset"),
        (("ordinateur", "portable", "latitude", "pc"), "laptop"),
        (("écran", "moniteur"), "monitor"),
        (("imprimante", "laserjet"), "printer"),
    )
    for words, category in terms:
        if any(word in folded for word in words):
            return category
    return None


def report_failure(
    session: Session,
    reporter_id: UUID,
    text: str,
    *,
    reported_via: IncidentReportedVia,
    create_unidentified: bool = False,
    badge: RealityBadge = RealityBadge.SIMULATED,
) -> FailureReport:
    if reported_via not in {IncidentReportedVia.CHAT, IncidentReportedVia.EMAIL}:
        raise ValueError("Unsupported reporting channel")
    rows = (
        session.execute(
            select(
                equipment.c.id,
                equipment.c.brand,
                equipment.c.model,
                equipment.c.serial,
                equipment.c.category,
            )
            .where(equipment.c.assigned_to == str(reporter_id))
            .order_by(equipment.c.model, equipment.c.serial)
        )
        .mappings()
        .all()
    )
    category = _equipment_category(text)
    folded_text = text.casefold()
    explicit = [
        row
        for row in rows
        if str(row["serial"]).casefold() in folded_text
        or str(row["model"]).casefold() in folded_text
    ]
    candidates = explicit or [
        row for row in rows if category is None or row["category"] == category
    ]
    questions: list[str] = []
    identified = None
    incident_id: UUID | None = None
    case_id: str | None = None
    if len(candidates) != 1:
        if not candidates:
            questions = ["Quel équipement est concerné ?"]
        else:
            labels = ", ".join(f"{row['brand']} {row['model']}" for row in candidates)
            questions = [f"Quel équipement est concerné parmi {labels} ?"]
    if len(candidates) == 1 or create_unidentified:
        identified = candidates[0] if len(candidates) == 1 else None
        incident_id = uuid4()
        case_uuid = uuid4()
        created_at = utc_now()
        session.execute(
            insert(incidents).values(
                id=str(incident_id),
                kind=IncidentKind.FAILURE.value,
                reporter_id=str(reporter_id),
                equipment_id=identified["id"] if identified is not None else None,
                description=text.strip(),
                reported_via=reported_via.value,
                created_at=created_at.isoformat(),
            )
        )
        session.execute(
            insert(cases).values(
                id=str(case_uuid),
                incident_id=str(incident_id),
                equipment_id=identified["id"] if identified is not None else None,
                status=CaseStatus.PREPARED.value,
                channel=Channel.MANUAL.value,
                verdict_id=None,
                policy_id=None,
                badge=badge.value,
                created_at=created_at.isoformat(),
                updated_at=created_at.isoformat(),
            )
        )
        append_event(
            session,
            EventType.CASE_CREATED,
            case_id=str(case_uuid),
            payload={
                "incident_id": str(incident_id),
                "equipment_id": identified["id"] if identified is not None else None,
                "reported_via": reported_via.value,
            },
        )
        case_id = str(case_uuid)
        ensure_data_checklist(
            session, case_id, identified["id"] if identified is not None else None
        )

    equipment_label = (
        f"{identified['brand']} {identified['model']}" if identified is not None else None
    )
    return FailureReport(
        case_id=case_id,
        incident_id=str(incident_id) if incident_id is not None else None,
        equipment_id=str(identified["id"]) if identified is not None else None,
        equipment_label=equipment_label,
        questions=questions,
    )
