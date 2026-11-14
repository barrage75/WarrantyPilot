import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_orchestrator, get_session
from app.contracts.enums import CaseStatus, ChecklistStepName, EventType
from app.contracts.models import (
    Case,
    ChecklistStep,
    DataChecklist,
    Event,
    PolicyDecision,
    Verdict,
    utc_now,
)
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.status import InvalidTransition, transition
from app.core.tables import cases, data_checklists, events, people, policy_decisions, verdicts

router = APIRouter()


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID


class RejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID
    reason: str


class ChecklistStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID


def _case_from_row(session: Session, row: Any) -> Case:
    verdict = None
    if row["verdict_id"]:
        value = (
            session.execute(select(verdicts).where(verdicts.c.id == row["verdict_id"]))
            .mappings()
            .first()
        )
        if value is not None:
            verdict = Verdict(
                id=UUID(value["id"]),
                value=value["value"],
                rule_id=value["rule_id"],
                rule_version=value["rule_version"],
                checks=value["checks"],
                evidence=value["evidence"],
                missing=value["missing"],
                possible_exclusions=value["possible_exclusions"],
                explanation_fr=value["explanation_fr"],
                explanation_en=value["explanation_en"],
            )
    policy = None
    if row["policy_id"]:
        value = (
            session.execute(
                select(policy_decisions).where(policy_decisions.c.id == row["policy_id"])
            )
            .mappings()
            .first()
        )
        if value is not None:
            policy = PolicyDecision(
                id=UUID(value["id"]),
                outcome=value["outcome"],
                reasons=value["reasons"],
                conditions=value["conditions"],
            )
    return Case(
        id=UUID(row["id"]),
        incident_id=UUID(row["incident_id"]),
        equipment_id=UUID(row["equipment_id"]) if row["equipment_id"] else None,
        status=row["status"],
        verdict=verdict,
        policy=policy,
        channel=row["channel"],
        badge=row["badge"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _load_case(session: Session, case_id: UUID) -> Case:
    row = session.execute(select(cases).where(cases.c.id == str(case_id))).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_from_row(session, row)


@router.get("/cases", response_model=list[Case])
def list_cases(session: Session = Depends(get_session)) -> list[Case]:
    rows = session.execute(select(cases).order_by(cases.c.created_at.desc())).mappings().all()
    return [_case_from_row(session, row) for row in rows]


@router.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: UUID, session: Session = Depends(get_session)) -> Case:
    return _load_case(session, case_id)


@router.get("/cases/{case_id}/events", response_model=list[Event])
def get_case_events(case_id: UUID, session: Session = Depends(get_session)) -> list[Event]:
    _load_case(session, case_id)
    rows = (
        session.execute(
            select(events).where(events.c.case_id == str(case_id)).order_by(events.c.seq)
        )
        .mappings()
        .all()
    )
    return [
        Event(
            seq=row["seq"],
            id=UUID(row["id"]),
            at=datetime.fromisoformat(row["at"]),
            actor=row["actor"],
            type=row["type"],
            case_id=UUID(row["case_id"]),
            payload=row["payload"],
            prev_hash=row["prev_hash"],
            hash=row["hash"],
        )
        for row in rows
    ]


@router.get("/cases/{case_id}/stream")
async def stream_case_events(
    case_id: UUID,
    request: Request,
    after: int = 0,
    session: Session = Depends(get_session),
) -> EventSourceResponse:
    _load_case(session, case_id)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        cursor = after
        while not await request.is_disconnected():
            with request.app.state.session_factory() as current:
                rows = (
                    current.execute(
                        select(events)
                        .where(events.c.case_id == str(case_id), events.c.seq > cursor)
                        .order_by(events.c.seq)
                    )
                    .mappings()
                    .all()
                )
            for row in rows:
                cursor = int(row["seq"])
                yield {
                    "id": str(cursor),
                    "event": str(row["type"]),
                    "data": json.dumps(
                        {
                            "seq": cursor,
                            "at": row["at"],
                            "actor": row["actor"],
                            "type": row["type"],
                            "payload": row["payload"],
                            "hash": row["hash"],
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_stream())


@router.post("/cases/{case_id}/validate", response_model=Case)
async def validate_case(
    case_id: UUID,
    request_body: ValidationRequest,
    session: Session = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> Case:
    case = _load_case(session, case_id)
    if case.status != CaseStatus.AWAITING_VALIDATION:
        raise HTTPException(status_code=409, detail="Case is not awaiting validation")
    append_event(
        session,
        EventType.VALIDATED,
        actor=f"human:{request_body.person_id}",
        case_id=str(case_id),
        payload={"approved": True},
    )
    session.commit()
    return await orchestrator.run(case_id)


@router.post("/cases/{case_id}/reject", response_model=Case)
def reject_case(
    case_id: UUID,
    request_body: RejectionRequest,
    session: Session = Depends(get_session),
) -> Case:
    case = _load_case(session, case_id)
    if case.status != CaseStatus.AWAITING_VALIDATION:
        raise HTTPException(status_code=409, detail="Case is not awaiting validation")
    try:
        new_status = transition(case.status, CaseStatus.CANCELLED)
    except InvalidTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.execute(
        update(cases)
        .where(cases.c.id == str(case_id))
        .values(status=new_status.value, updated_at=utc_now().isoformat())
    )
    append_event(
        session,
        EventType.REJECTED,
        actor=f"human:{request_body.person_id}",
        case_id=str(case_id),
        payload={"reason": request_body.reason},
    )
    append_event(
        session,
        EventType.STATUS_CHANGED,
        case_id=str(case_id),
        payload={"from": case.status.value, "to": new_status.value},
    )
    session.commit()
    return case.model_copy(update={"status": new_status, "updated_at": utc_now()})


@router.get("/cases/{case_id}/checklist", response_model=DataChecklist)
def get_checklist(case_id: UUID, session: Session = Depends(get_session)) -> DataChecklist:
    _load_case(session, case_id)
    row = (
        session.execute(select(data_checklists).where(data_checklists.c.case_id == str(case_id)))
        .mappings()
        .first()
    )
    if row is None:
        return DataChecklist(case_id=case_id)
    return DataChecklist(id=UUID(row["id"]), case_id=case_id, steps=row["steps"])


@router.post(
    "/cases/{case_id}/checklist/{step_name}",
    response_model=DataChecklist,
)
async def complete_checklist_step(
    case_id: UUID,
    step_name: ChecklistStepName,
    request_body: ChecklistStepUpdate,
    session: Session = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> DataChecklist:
    case = _load_case(session, case_id)
    human_exists = session.execute(
        select(people.c.id).where(people.c.id == str(request_body.person_id))
    ).first()
    if human_exists is None:
        raise HTTPException(status_code=404, detail="Human approver not found")
    row = (
        session.execute(select(data_checklists).where(data_checklists.c.case_id == str(case_id)))
        .mappings()
        .first()
    )
    checklist = (
        DataChecklist(id=UUID(row["id"]), case_id=case_id, steps=row["steps"])
        if row is not None
        else DataChecklist(case_id=case_id)
    )
    step = ChecklistStep(
        done=True,
        by_person_id=request_body.person_id,
        at=utc_now(),
    )
    checklist.steps[step_name] = step
    if row is None:
        session.execute(
            data_checklists.insert().values(
                id=str(checklist.id),
                case_id=str(case_id),
                steps=checklist.model_dump(mode="json")["steps"],
            )
        )
    else:
        session.execute(
            data_checklists.update()
            .where(data_checklists.c.case_id == str(case_id))
            .values(steps=checklist.model_dump(mode="json")["steps"])
        )
    append_event(
        session,
        EventType.CHECKLIST_STEP_DONE,
        actor=f"human:{request_body.person_id}",
        case_id=str(case_id),
        payload={"step": step_name.value, "by_person_id": str(request_body.person_id)},
    )
    session.commit()
    if checklist.complete() and case.status in {
        CaseStatus.PREPARED,
        CaseStatus.AWAITING_VALIDATION,
    }:
        await orchestrator.run(case_id)
    return checklist
