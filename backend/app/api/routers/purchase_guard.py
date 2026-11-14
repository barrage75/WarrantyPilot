from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import _require_person, get_orchestrator, get_session
from app.contracts.enums import (
    CaseStatus,
    Channel,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    PurchaseGuardState,
    RealityBadge,
    VerdictValue,
)
from app.contracts.models import utc_now
from app.core.checklists import ensure_data_checklist
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.tables import cases, equipment, incidents, purchase_requests, rights

router = APIRouter(prefix="/purchase-requests", tags=["purchase guard"])


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.title() for part in rest)


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class PurchaseRecommendation(APIModel):
    id: str
    company: str
    equipment: str
    amount_eur: float
    state: PurchaseGuardState
    reason: str | None = None
    cancelled_at: datetime | None = None
    resolved_at: datetime | None = None
    verdict: VerdictValue
    explanation_fr: str
    explanation_en: str
    case_id: str | None = None


class PurchaseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: Literal["suspend", "keep"]
    reason: str | None = None

    @model_validator(mode="after")
    def require_reason_to_keep(self) -> PurchaseDecision:
        if self.choice == "keep" and not (self.reason or "").strip():
            raise ValueError("a reason is required to keep the purchase")
        return self


class HumanActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID


def _row(session: Session, purchase_id: UUID):
    row = (
        session.execute(
            select(
                purchase_requests,
                equipment.c.brand,
                equipment.c.model,
                rights.c.end_date,
            )
            .join(equipment, equipment.c.id == purchase_requests.c.equipment_id)
            .outerjoin(rights, rights.c.equipment_id == equipment.c.id)
            .where(purchase_requests.c.id == str(purchase_id))
            .order_by(rights.c.end_date.desc())
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return row


def _serialize(row, today) -> PurchaseRecommendation:
    covered = row["end_date"] is not None and row["end_date"] >= today
    verdict = VerdictValue.COVERED if covered else VerdictValue.TO_VERIFY
    explanation_fr = (
        "L'équipement existant possède un droit de garantie encore actif."
        if covered
        else "La couverture de l'équipement existant doit être vérifiée."
    )
    explanation_en = (
        "The existing equipment has an active warranty right."
        if covered
        else "The existing equipment's coverage needs verification."
    )
    return PurchaseRecommendation(
        id=row["id"],
        company="Appelia",
        equipment=f"{row['brand']} {row['model']}",
        amount_eur=float(row["amount"]),
        state=row["state"],
        reason=row["decision_reason"] or explanation_fr,
        cancelled_at=row["cancelled_at"],
        resolved_at=row["resolved_at"],
        verdict=verdict,
        explanation_fr=explanation_fr,
        explanation_en=explanation_en,
        case_id=row["case_id"],
    )


def _ensure_linked_case(session: Session, row) -> UUID:
    if row["case_id"]:
        return UUID(row["case_id"])
    existing_case_id = session.execute(
        select(cases.c.id)
        .join(incidents, incidents.c.id == cases.c.incident_id)
        .where(
            cases.c.equipment_id == row["equipment_id"],
            incidents.c.kind == IncidentKind.FAILURE.value,
            cases.c.status.in_(
                [
                    CaseStatus.AWAITING_VALIDATION.value,
                    CaseStatus.SENDING.value,
                    CaseStatus.SENT.value,
                    CaseStatus.TRACKED.value,
                    CaseStatus.MANUAL_TAKEOVER.value,
                ]
            ),
        )
        .order_by(cases.c.updated_at.desc(), cases.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if existing_case_id is not None:
        ensure_data_checklist(session, existing_case_id, row["equipment_id"])
        session.execute(
            update(purchase_requests)
            .where(purchase_requests.c.id == row["id"])
            .values(case_id=existing_case_id)
        )
        return UUID(existing_case_id)
    incident_id = uuid4()
    case_id = uuid4()
    created_at = utc_now()
    session.execute(
        insert(incidents).values(
            id=str(incident_id),
            kind=IncidentKind.PURCHASE_REQUEST.value,
            reporter_id=row["requester_id"],
            equipment_id=row["equipment_id"],
            description=(
                f"L'équipement actuel {row['item_description']} présente une panne; "
                "demande de prise en charge avant achat neuf."
            ),
            reported_via=IncidentReportedVia.PURCHASE_FORM.value,
            created_at=created_at.isoformat(),
        )
    )
    session.execute(
        insert(cases).values(
            id=str(case_id),
            incident_id=str(incident_id),
            equipment_id=row["equipment_id"],
            status=CaseStatus.PREPARED.value,
            channel=Channel.MANUAL.value,
            verdict_id=None,
            policy_id=None,
            badge=RealityBadge.SIMULATED.value,
            created_at=created_at.isoformat(),
            updated_at=created_at.isoformat(),
        )
    )
    ensure_data_checklist(session, case_id, row["equipment_id"])
    session.execute(
        update(purchase_requests)
        .where(purchase_requests.c.id == row["id"])
        .values(case_id=str(case_id))
    )
    append_event(
        session,
        EventType.CASE_CREATED,
        case_id=str(case_id),
        payload={
            "incident_id": str(incident_id),
            "equipment_id": row["equipment_id"],
            "purchase_request_id": row["id"],
        },
    )
    return case_id


@router.get("", response_model=list[PurchaseRecommendation])
def list_recommendations(
    request: Request,
    session: Session = Depends(get_session),
) -> list[PurchaseRecommendation]:
    today = request.app.state.app_settings.demo_today
    ids = session.execute(select(purchase_requests.c.id)).scalars().all()
    return [_serialize(_row(session, UUID(purchase_id)), today) for purchase_id in ids]


@router.post("/{purchase_id}/decision", response_model=PurchaseRecommendation)
async def decide(
    purchase_id: UUID,
    body: PurchaseDecision,
    request: Request,
    session: Session = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> PurchaseRecommendation:
    row = _row(session, purchase_id)
    if row["state"] not in {
        PurchaseGuardState.RECOMMENDATION.value,
        PurchaseGuardState.AWAITING_DECISION.value,
    }:
        raise HTTPException(status_code=409, detail="Purchase request is not awaiting a decision")
    now = utc_now().isoformat()
    if body.choice == "keep":
        session.execute(
            update(purchase_requests)
            .where(purchase_requests.c.id == str(purchase_id))
            .values(
                state=PurchaseGuardState.PURCHASE_KEPT.value,
                decision_reason=(body.reason or "").strip(),
            )
        )
        append_event(
            session,
            EventType.PURCHASE_GUARD_KEPT,
            actor="human:purchase-guard",
            payload={"purchase_request_id": str(purchase_id), "reason": body.reason},
        )
    else:
        case_id = _ensure_linked_case(session, row)
        session.execute(
            update(purchase_requests)
            .where(purchase_requests.c.id == str(purchase_id))
            .values(
                state=PurchaseGuardState.PURCHASE_SUSPENDED.value,
                decision_reason=(body.reason or "Achat suspendu pour demande de garantie").strip(),
            )
        )
        append_event(
            session,
            EventType.PURCHASE_GUARD_SUSPENDED,
            actor="human:purchase-guard",
            case_id=str(case_id),
            payload={"purchase_request_id": str(purchase_id)},
        )
        session.commit()
        await orchestrator.run(case_id)
        row = _row(session, purchase_id)
    append_event(
        session,
        EventType.PURCHASE_GUARD_DECISION,
        actor="human:purchase-guard",
        payload={"purchase_request_id": str(purchase_id), "choice": body.choice, "at": now},
    )
    session.commit()
    return _serialize(_row(session, purchase_id), request.app.state.app_settings.demo_today)


@router.post(
    "/{purchase_id}/confirm-cancellation",
    response_model=PurchaseRecommendation,
)
def confirm_cancellation(
    purchase_id: UUID,
    body: HumanActionRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> PurchaseRecommendation:
    row = _row(session, purchase_id)
    _require_person(session, body.person_id)
    if row["state"] != PurchaseGuardState.PURCHASE_SUSPENDED.value:
        raise HTTPException(status_code=409, detail="Purchase is not suspended")
    now = utc_now()
    state = PurchaseGuardState.CANCELLED
    resolved_at = row["resolved_at"]
    if row["case_id"]:
        case_status = session.execute(
            select(cases.c.status).where(cases.c.id == row["case_id"])
        ).scalar_one_or_none()
        if case_status == CaseStatus.RESOLVED.value:
            state = PurchaseGuardState.SAVING_REALIZED
            resolved_at = now.isoformat()
    session.execute(
        update(purchase_requests)
        .where(purchase_requests.c.id == str(purchase_id))
        .values(
            state=state.value,
            cancelled_at=now.isoformat(),
            resolved_at=resolved_at,
        )
    )
    append_event(
        session,
        EventType.PURCHASE_GUARD_CANCELLED,
        actor=f"human:{body.person_id}",
        payload={"purchase_request_id": str(purchase_id), "at": now.isoformat()},
    )
    if state == PurchaseGuardState.SAVING_REALIZED:
        append_event(
            session,
            EventType.PURCHASE_GUARD_SAVING_REALIZED,
            actor="agent",
            payload={"purchase_request_id": str(purchase_id), "amount_eur": float(row["amount"])},
        )
    session.commit()
    return _serialize(_row(session, purchase_id), request.app.state.app_settings.demo_today)


@router.post("/{purchase_id}/resolve-case", response_model=PurchaseRecommendation)
async def resolve_case(
    purchase_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> PurchaseRecommendation:
    row = _row(session, purchase_id)
    if not row["case_id"]:
        raise HTTPException(status_code=409, detail="No warranty case is linked")
    session.commit()
    case = await orchestrator.run(UUID(row["case_id"]))
    if case.status == CaseStatus.RESOLVED:
        now = utc_now().isoformat()
        state = PurchaseGuardState.SAVING_REALIZED.value if row["cancelled_at"] else row["state"]
        session.execute(
            update(purchase_requests)
            .where(purchase_requests.c.id == str(purchase_id))
            .values(state=state, resolved_at=now)
        )
        if state == PurchaseGuardState.SAVING_REALIZED.value:
            append_event(
                session,
                EventType.PURCHASE_GUARD_SAVING_REALIZED,
                actor="agent",
                payload={
                    "purchase_request_id": str(purchase_id),
                    "amount_eur": float(row["amount"]),
                },
            )
        session.commit()
    return _serialize(_row(session, purchase_id), request.app.state.app_settings.demo_today)
