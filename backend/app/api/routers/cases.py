import asyncio
import json
import re
from collections.abc import AsyncIterator, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.actions.browser.settings import BrowserSettings
from app.api.dependencies import actor_for, get_orchestrator, get_session, require_session
from app.contracts.enums import (
    ActionResultStatus,
    CaseStatus,
    Channel,
    ChecklistStepName,
    EventType,
    PurchaseGuardState,
)
from app.contracts.models import (
    Action,
    ActionResult,
    Case,
    ChecklistStep,
    DataChecklist,
    Equipment,
    Event,
    Person,
    PolicyDecision,
    Verdict,
    utc_now,
)
from app.core.auth import Operator
from app.core.checklist_rules import ChecklistRuleError, ensure_step_allowed
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.status import InvalidTransition, transition
from app.core.tables import (
    action_results,
    actions,
    cases,
    data_checklists,
    equipment,
    events,
    people,
    policy_decisions,
    purchase_requests,
    verdicts,
)

router = APIRouter()
_SCREENSHOT_NAME = re.compile(r"^[A-Za-z0-9_.-]+\.png$")


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID | None = None


class RejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=1000)


class ChecklistStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID | None = None


class ManualTakeoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID | None = None


class ManualProofType(StrEnum):
    CASE_NUMBER = "case_number"
    EMAIL_MESSAGE_ID = "email_message_id"
    PORTAL_SCREENSHOT = "portal_screenshot"
    CARRIER_TRACKING = "carrier_tracking"


_PROOF_REFERENCE_PATTERNS: dict[ManualProofType, re.Pattern[str]] = {
    ManualProofType.CASE_NUMBER: re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{3,63}$"),
    ManualProofType.EMAIL_MESSAGE_ID: re.compile(r"^<?[^<>@\s]{1,128}@[^<>@\s]{1,128}>?$"),
    ManualProofType.PORTAL_SCREENSHOT: re.compile(r"^[A-Za-z0-9_.-]{1,96}\.png$"),
    ManualProofType.CARRIER_TRACKING: re.compile(r"^[A-Za-z0-9-]{8,40}$"),
}


class ManualProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    person_id: UUID | None = None
    proof_type: ManualProofType
    reference: str = Field(min_length=4, max_length=128)
    proof_date: date
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_reference(self) -> "ManualProofRequest":
        if not _PROOF_REFERENCE_PATTERNS[self.proof_type].fullmatch(self.reference):
            raise ValueError(f"reference is not a valid {self.proof_type.value}")
        if self.proof_date > date.today() + timedelta(days=1):
            raise ValueError("proof_date cannot be in the future")
        if self.proof_date < date(2000, 1, 1):
            raise ValueError("proof_date is too old")
        return self

    def summary(self) -> str:
        return f"{self.proof_type.value}:{self.reference} ({self.proof_date.isoformat()})"


class CaseResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID | None = None
    note: str = Field(min_length=1)

    @field_validator("note")
    @classmethod
    def note_must_not_be_blank(cls, value: str) -> str:
        note = value.strip()
        if not note:
            raise ValueError("Note must not be blank")
        return note


class CaseActionHistory(BaseModel):
    action: Action
    results: list[ActionResult]


def _equipment_from_row(row: Any) -> Equipment:
    return Equipment(
        id=UUID(row["id"]),
        brand=row["brand"],
        model=row["model"],
        serial=row["serial"],
        category=row["category"],
        assigned_to=UUID(row["assigned_to"]) if row["assigned_to"] else None,
        purchase_price=Decimal(row["purchase_price"])
        if row["purchase_price"] is not None
        else None,
        currency=row["currency"],
        in_loan_stock=row["in_loan_stock"],
        purchase_date=row["purchase_date"],
        invoice_number=row["invoice_number"],
        delivery_date=row["delivery_date"],
        ship_date=row["ship_date"],
    )


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
                channel=value["channel"],
                target_url=value["target_url"],
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


@router.get("/people", response_model=list[Person])
def list_people(session: Session = Depends(get_session)) -> list[Person]:
    rows = session.execute(select(people).order_by(people.c.name)).mappings().all()
    return [
        Person(
            id=UUID(row["id"]),
            name=row["name"],
            email=row["email"],
            role=row["role"],
        )
        for row in rows
    ]


@router.get("/equipment", response_model=list[Equipment])
def list_equipment(session: Session = Depends(get_session)) -> list[Equipment]:
    rows = session.execute(select(equipment).order_by(equipment.c.serial)).mappings().all()
    return [_equipment_from_row(row) for row in rows]


@router.get("/equipment/{equipment_id}", response_model=Equipment)
def get_equipment(
    equipment_id: UUID,
    session: Session = Depends(get_session),
) -> Equipment:
    row = (
        session.execute(select(equipment).where(equipment.c.id == str(equipment_id)))
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return _equipment_from_row(row)


@router.get("/cases", response_model=list[Case])
def list_cases(session: Session = Depends(get_session)) -> list[Case]:
    rows = session.execute(select(cases).order_by(cases.c.created_at.desc())).mappings().all()
    return [_case_from_row(session, row) for row in rows]


@router.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: UUID, session: Session = Depends(get_session)) -> Case:
    return _load_case(session, case_id)


@router.get("/cases/{case_id}/events", response_model=list[Event])
def get_case_events(
    case_id: UUID,
    after: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[Event]:
    _load_case(session, case_id)
    rows = (
        session.execute(
            select(events)
            .where(events.c.case_id == str(case_id), events.c.seq > after)
            .order_by(events.c.seq)
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
    session.rollback()

    def load_events(cursor: int) -> Any:
        with request.app.state.session_factory() as current:
            return (
                current.execute(
                    select(events)
                    .where(events.c.case_id == str(case_id), events.c.seq > cursor)
                    .order_by(events.c.seq)
                )
                .mappings()
                .all()
            )

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        cursor = after
        while not await request.is_disconnected():
            rows = await asyncio.to_thread(load_events, cursor)
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


@router.get("/cases/{case_id}/actions", response_model=list[CaseActionHistory])
def get_case_actions(
    case_id: UUID,
    session: Session = Depends(get_session),
) -> list[CaseActionHistory]:
    _load_case(session, case_id)
    action_rows = (
        session.execute(
            select(actions)
            .where(actions.c.case_id == str(case_id))
            .order_by(actions.c.idempotency_key)
        )
        .mappings()
        .all()
    )
    if not action_rows:
        return []
    action_ids = [row["id"] for row in action_rows]
    result_rows = (
        session.execute(
            select(action_results)
            .where(action_results.c.action_id.in_(action_ids))
            .order_by(action_results.c.id)
        )
        .mappings()
        .all()
    )
    results_by_action: dict[str, list[ActionResult]] = {}
    for row in result_rows:
        results_by_action.setdefault(row["action_id"], []).append(
            ActionResult(
                id=UUID(row["id"]),
                action_id=UUID(row["action_id"]),
                status=row["status"],
                proof=row["proof"],
                error=row["error"],
                badge=row["badge"],
            )
        )
    return [
        CaseActionHistory(
            action=Action(
                id=UUID(row["id"]),
                case_id=UUID(row["case_id"]),
                channel=row["channel"],
                kind=row["kind"],
                idempotency_key=row["idempotency_key"],
                payload=row["payload"],
                badge=row["badge"],
                requires_data_checklist=row["requires_data_checklist"],
            ),
            results=results_by_action.get(row["id"], []),
        )
        for row in action_rows
    ]


@router.get(
    "/cases/{case_id}/screenshots/{name}",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_case_screenshot(
    case_id: UUID,
    name: str,
    action_id: UUID,
    session: Session = Depends(get_session),
) -> FileResponse:
    _load_case(session, case_id)
    if _SCREENSHOT_NAME.fullmatch(name) is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    action_row = (
        session.execute(
            select(actions.c.id).where(
                actions.c.id == str(action_id),
                actions.c.case_id == str(case_id),
            )
        )
        .mappings()
        .first()
    )
    if action_row is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    step_payloads: Sequence[Any] = (
        session.execute(
            select(events.c.payload).where(
                events.c.case_id == str(case_id),
                events.c.type == EventType.ACTION_STEP.value,
            )
        )
        .scalars()
        .all()
    )
    if not any(
        isinstance(payload, dict)
        and payload.get("screenshot_action_id", payload.get("action_id")) == str(action_id)
        and payload.get("screenshot_name") == name
        for payload in step_payloads
    ):
        raise HTTPException(status_code=404, detail="Screenshot not found")

    screenshot_root = BrowserSettings.from_env().screenshot_dir.resolve()
    action_screenshot_dir = (screenshot_root / str(action_id)).resolve()
    try:
        screenshot_path = (action_screenshot_dir / name).resolve(strict=True)
    except OSError as error:
        raise HTTPException(status_code=404, detail="Screenshot not found") from error
    if (
        not action_screenshot_dir.is_relative_to(screenshot_root)
        or not screenshot_path.is_relative_to(action_screenshot_dir)
        or not screenshot_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(screenshot_path, media_type="image/png")


@router.post("/cases/{case_id}/validate", response_model=Case)
async def validate_case(
    case_id: UUID,
    request_body: ValidationRequest,
    session: Session = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    operator: Operator = Depends(require_session),
) -> Case:
    actor = actor_for(operator, request_body.person_id)
    case = _load_case(session, case_id)
    if case.status != CaseStatus.AWAITING_VALIDATION:
        raise HTTPException(status_code=409, detail="Case is not awaiting validation")
    append_event(
        session,
        EventType.VALIDATED,
        actor=actor,
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
    operator: Operator = Depends(require_session),
) -> Case:
    actor = actor_for(operator, request_body.person_id)
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
        actor=actor,
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


@router.post("/cases/{case_id}/manual-takeover", response_model=Case)
def request_manual_takeover(
    case_id: UUID,
    request_body: ManualTakeoverRequest,
    session: Session = Depends(get_session),
    operator: Operator = Depends(require_session),
) -> Case:
    actor = actor_for(operator, request_body.person_id)
    case = _load_case(session, case_id)
    if case.status != CaseStatus.FAILED:
        raise HTTPException(status_code=409, detail="Case is not failed")
    try:
        new_status = transition(case.status, CaseStatus.MANUAL_TAKEOVER)
    except InvalidTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    updated_at = utc_now()
    session.execute(
        update(cases)
        .where(cases.c.id == str(case_id))
        .values(status=new_status.value, updated_at=updated_at.isoformat())
    )
    append_event(
        session,
        EventType.STATUS_CHANGED,
        actor=actor,
        case_id=str(case_id),
        payload={"from": case.status.value, "to": new_status.value},
    )
    session.commit()
    return case.model_copy(update={"status": new_status, "updated_at": updated_at})


@router.post("/cases/{case_id}/manual-proof", response_model=Case)
def submit_manual_proof(
    case_id: UUID,
    request_body: ManualProofRequest,
    session: Session = Depends(get_session),
    operator: Operator = Depends(require_session),
) -> Case:
    actor = actor_for(operator, request_body.person_id)
    case = _load_case(session, case_id)
    if case.status != CaseStatus.MANUAL_TAKEOVER:
        raise HTTPException(status_code=409, detail="Case is not awaiting manual proof")
    proof = request_body.summary()
    action = Action(
        case_id=case_id,
        channel=Channel.MANUAL,
        kind="manual_claim",
        idempotency_key=f"case:{case_id}:manual-proof:{uuid4()}",
        payload={
            "proof": proof,
            "proof_type": request_body.proof_type.value,
            "reference": request_body.reference,
            "proof_date": request_body.proof_date.isoformat(),
            "note": request_body.note,
        },
        badge=case.badge,
    )
    result = ActionResult(
        action_id=action.id,
        status=ActionResultStatus.SUCCESS,
        proof=proof,
        badge=case.badge,
    )
    try:
        new_status = transition(
            case.status,
            CaseStatus.SENT,
            action_result=result,
            actor=actor,
        )
    except InvalidTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    updated_at = utc_now()
    session.execute(
        insert(actions).values(
            id=str(action.id),
            case_id=str(action.case_id),
            channel=action.channel.value,
            kind=action.kind,
            idempotency_key=action.idempotency_key,
            payload=action.payload,
            badge=action.badge.value,
            requires_data_checklist=action.requires_data_checklist,
        )
    )
    session.execute(
        insert(action_results).values(
            id=str(result.id),
            action_id=str(result.action_id),
            status=result.status.value,
            proof=result.proof,
            error=result.error,
            badge=result.badge.value,
        )
    )
    session.execute(
        update(cases)
        .where(cases.c.id == str(case_id))
        .values(status=new_status.value, updated_at=updated_at.isoformat())
    )
    append_event(
        session,
        EventType.ACTION_SUCCEEDED,
        actor=actor,
        case_id=str(case_id),
        payload={"action_id": str(action.id), "proof": result.proof, "manual": True},
    )
    append_event(
        session,
        EventType.STATUS_CHANGED,
        actor=actor,
        case_id=str(case_id),
        payload={"from": case.status.value, "to": new_status.value},
    )
    session.commit()
    return case.model_copy(update={"status": new_status, "updated_at": updated_at})


@router.post("/cases/{case_id}/resolve", response_model=Case)
def resolve_case(
    case_id: UUID,
    request_body: CaseResolveRequest,
    session: Session = Depends(get_session),
    operator: Operator = Depends(require_session),
) -> Case:
    actor = actor_for(operator, request_body.person_id)
    case = _load_case(session, case_id)
    if case.status not in {CaseStatus.SENT, CaseStatus.TRACKED}:
        raise HTTPException(status_code=409, detail="Case is not sent or tracked")
    try:
        new_status = transition(case.status, CaseStatus.RESOLVED)
    except InvalidTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    updated_at = utc_now()
    session.execute(
        update(cases)
        .where(cases.c.id == str(case_id))
        .values(status=new_status.value, updated_at=updated_at.isoformat())
    )
    append_event(
        session,
        EventType.STATUS_CHANGED,
        actor=actor,
        case_id=str(case_id),
        payload={
            "from": case.status.value,
            "to": new_status.value,
            "note": request_body.note,
        },
    )
    purchase_rows = session.execute(
        select(
            purchase_requests.c.id,
            purchase_requests.c.amount,
            purchase_requests.c.cancelled_at,
        ).where(purchase_requests.c.case_id == str(case_id))
    ).mappings()
    for row in purchase_rows:
        values: dict[str, Any] = {"resolved_at": updated_at.isoformat()}
        if row["cancelled_at"]:
            values["state"] = PurchaseGuardState.SAVING_REALIZED.value
        session.execute(
            update(purchase_requests).where(purchase_requests.c.id == row["id"]).values(**values)
        )
        if row["cancelled_at"]:
            append_event(
                session,
                EventType.PURCHASE_GUARD_SAVING_REALIZED,
                actor=actor,
                case_id=str(case_id),
                payload={
                    "purchase_request_id": row["id"],
                    "amount_eur": float(row["amount"]),
                },
            )
    session.commit()
    return case.model_copy(update={"status": new_status, "updated_at": updated_at})


@router.get("/cases/{case_id}/checklist", response_model=DataChecklist)
def get_checklist(case_id: UUID, session: Session = Depends(get_session)) -> DataChecklist:
    _load_case(session, case_id)
    row = (
        session.execute(select(data_checklists).where(data_checklists.c.case_id == str(case_id)))
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
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
    operator: Operator = Depends(require_session),
) -> DataChecklist:
    actor = actor_for(operator, request_body.person_id)
    case = _load_case(session, case_id)
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
    try:
        changed = ensure_step_allowed(checklist, step_name, operator)
    except ChecklistRuleError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    if changed:
        step = ChecklistStep(
            done=True,
            by_person_id=UUID(operator.person_id),
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
            actor=actor,
            case_id=str(case_id),
            payload={
                "step": step_name.value,
                "by_person_id": operator.person_id,
                "role": operator.role,
            },
        )
    session.commit()
    if checklist.complete() and case.status in {
        CaseStatus.PREPARED,
        CaseStatus.AWAITING_VALIDATION,
    }:
        await orchestrator.run(case_id)
    return checklist
