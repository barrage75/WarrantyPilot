from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request
from sqlalchemy import select, update

from app.api.routers.cases import _case_from_row
from app.contracts.enums import (
    ActionResultStatus,
    CaseStatus,
    Channel,
    EventType,
    PurchaseGuardState,
)
from app.contracts.models import Case, utc_now
from app.core.journal import append_event
from app.core.status import InvalidTransition, transition
from app.core.tables import action_results, actions, cases, events, purchase_requests
from app.followup.reminders import ReminderScheduler, ReminderState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/followup", tags=["follow-up"])

_ACTIVE_STATUSES = (CaseStatus.SENT.value, CaseStatus.TRACKED.value)
_ACTION_CHANNELS = {
    Channel.EMAIL_RESELLER.value,
    Channel.EMAIL_MANUFACTURER_SUPPORT.value,
    Channel.EMAIL_LESSOR.value,
    Channel.BROWSER_PORTAL.value,
}

# A freshly submitted Dell case reads "received"; only a later change is a reply.
_PORTAL_BASELINE_STATUS = "received"


def _event_key(payload: dict[str, Any]) -> tuple[str, ...] | None:
    message_id = payload.get("message_id")
    if isinstance(message_id, str) and message_id:
        return ("message_id", message_id)
    proof = payload.get("proof")
    proof = proof if isinstance(proof, dict) else {}
    case_number = payload.get("case_number") or proof.get("case_number")
    status = payload.get("portal_status") or proof.get("portal_status") or payload.get("status")
    if isinstance(case_number, str) and case_number and isinstance(status, str) and status:
        return ("portal_status", case_number, status)
    idempotency_key = payload.get("idempotency_key")
    if isinstance(idempotency_key, str) and idempotency_key:
        return ("idempotency_key", idempotency_key)
    if payload.get("kind") == "followup_error":
        return (
            "followup_error",
            str(payload.get("code", "")),
            str(payload.get("error_type", "")),
        )
    return None


def _already_recorded(
    session: Any, case_id: UUID, event_type: EventType, payload: dict[str, Any]
) -> bool:
    key = _event_key(payload)
    if key is None:
        return False
    prior_payloads = session.execute(
        select(events.c.payload).where(
            events.c.case_id == str(case_id),
            events.c.type == event_type.value,
        )
    ).scalars()
    return any(isinstance(prior, dict) and _event_key(prior) == key for prior in prior_payloads)


def _target_status(payload: dict[str, Any]) -> CaseStatus | None:
    kind = payload.get("kind")
    if kind == "followup_error":
        return None
    if kind == "manual_takeover_recommended":
        return CaseStatus.MANUAL_TAKEOVER
    if payload.get("outcome") == "accepted":
        return CaseStatus.TRACKED
    status = payload.get("status")
    if status in {CaseStatus.TRACKED.value, CaseStatus.RESOLVED.value}:
        return CaseStatus(status)
    return None


def _realize_linked_purchases(session: Any, case_id: UUID, actor: str) -> None:
    rows = session.execute(
        select(
            purchase_requests.c.id,
            purchase_requests.c.amount,
            purchase_requests.c.cancelled_at,
        ).where(purchase_requests.c.case_id == str(case_id))
    ).mappings()
    for row in rows:
        values: dict[str, Any] = {"resolved_at": utc_now().isoformat()}
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


def _record_result(
    application: FastAPI,
    case_id: UUID,
    payload: dict[str, Any],
    event_type: EventType = EventType.FOLLOWUP_RECEIVED,
) -> tuple[bool, bool]:
    with application.state.session_factory.begin() as session:
        row = session.execute(select(cases).where(cases.c.id == str(case_id))).mappings().first()
        if row is None:
            return False, False
        case = _case_from_row(session, row)
        if event_type == EventType.FOLLOWUP_RECEIVED and case.status not in {
            CaseStatus.SENT,
            CaseStatus.TRACKED,
        }:
            return False, False
        if _already_recorded(session, case_id, event_type, payload):
            return False, False
        append_event(
            session,
            event_type,
            actor="system",
            case_id=str(case_id),
            payload=payload,
        )
        target = _target_status(payload)
        if target is None or target == case.status:
            return True, False
        try:
            new_status = transition(case.status, target)
        except InvalidTransition:
            return True, False
        now = utc_now()
        session.execute(
            update(cases)
            .where(cases.c.id == str(case_id))
            .values(status=new_status.value, updated_at=now.isoformat())
        )
        append_event(
            session,
            EventType.STATUS_CHANGED,
            actor="system",
            case_id=str(case_id),
            payload={"from": case.status.value, "to": new_status.value},
        )
        if new_status == CaseStatus.RESOLVED:
            _realize_linked_purchases(session, case_id, "system")
        return True, True


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _reminder_state(application: FastAPI, case_id: UUID) -> ReminderState | None:
    with application.state.session_factory() as session:
        event_rows = session.execute(
            select(events.c.type, events.c.at, events.c.payload)
            .where(events.c.case_id == str(case_id))
            .order_by(events.c.seq)
        ).all()
        successful_sends: list[datetime] = []
        reminder_sends: list[datetime] = []
        responses: list[datetime] = []
        portal_statuses: dict[str, str] = {}
        for event_type, at, payload in event_rows:
            event_time = _parse_datetime(at)
            if event_time is None or not isinstance(payload, dict):
                continue
            if event_type == EventType.ACTION_SUCCEEDED.value:
                action_id = payload.get("action_id")
                if not isinstance(action_id, str):
                    continue
                action = session.execute(
                    select(actions.c.channel, action_results.c.status)
                    .join(action_results, actions.c.id == action_results.c.action_id)
                    .where(
                        actions.c.id == action_id,
                        actions.c.case_id == str(case_id),
                        action_results.c.status == ActionResultStatus.SUCCESS.value,
                    )
                ).first()
                if action is not None and action.channel in _ACTION_CHANNELS:
                    successful_sends.append(event_time)
            elif event_type == EventType.REMINDER_DRAFTED.value:
                sent_at = _parse_datetime(payload.get("sent_at"))
                if sent_at is not None and payload.get("executed") is True:
                    reminder_sends.append(sent_at)
            elif (
                event_type == EventType.FOLLOWUP_RECEIVED.value
                and payload.get("kind") != "followup_error"
            ):
                proof = payload.get("proof")
                proof = proof if isinstance(proof, dict) else {}
                portal_status = payload.get("portal_status") or proof.get("portal_status")
                if isinstance(portal_status, str) and portal_status:
                    number = str(payload.get("case_number") or proof.get("case_number") or "")
                    previous = portal_statuses.get(number, _PORTAL_BASELINE_STATUS)
                    portal_statuses[number] = portal_status
                    if portal_status != previous:
                        responses.append(event_time)
                elif payload.get("message_id") or payload.get("case_number"):
                    responses.append(event_time)
    if not successful_sends:
        return None
    sent_at = min(successful_sends)
    return ReminderState(
        sent_at=sent_at,
        reminder_sent_at=tuple(sorted(set(reminder_sends))),
        last_response_at=max(responses) if responses else None,
    )


def _current_case(application: FastAPI, case_id: UUID) -> Case | None:
    with application.state.session_factory() as session:
        row = session.execute(select(cases).where(cases.c.id == str(case_id))).mappings().first()
        return _case_from_row(session, row) if row is not None else None


def _run_followup_tick(application: FastAPI) -> dict[str, int]:
    services = application.state.services
    checker = services["follow_up"]
    with application.state.session_factory() as session:
        rows = (
            session.execute(
                select(cases)
                .where(cases.c.status.in_(_ACTIVE_STATUSES))
                .order_by(cases.c.created_at, cases.c.id)
            )
            .mappings()
            .all()
        )
        active_cases = [_case_from_row(session, row) for row in rows]

    logged = 0
    transitions = 0
    drafted = 0
    for case in active_cases:
        try:
            updates = checker.check(case)
        except Exception as error:
            logger.exception("Follow-up check failed for case %s", case.id)
            updates = [
                {
                    "kind": "followup_error",
                    "code": "checker_error",
                    "error_type": type(error).__name__,
                }
            ]
        for result in updates:
            if not isinstance(result, dict):
                continue
            payload = dict(result)
            if not payload.get("kind") and payload.get("message_id"):
                payload["kind"] = "email_reply"
            payload.setdefault("case_id", str(case.id))
            was_logged, changed = _record_result(application, case.id, payload)
            logged += int(was_logged)
            transitions += int(changed)

        latest_case = _current_case(application, case.id)
        if latest_case is None or latest_case.status not in {
            CaseStatus.SENT,
            CaseStatus.TRACKED,
        }:
            continue
        state = _reminder_state(application, latest_case.id)
        scheduler: ReminderScheduler = application.state.reminder_scheduler
        if state is None:
            continue
        for reminder in scheduler.run(latest_case, state):
            was_logged, changed = _record_result(
                application,
                latest_case.id,
                reminder,
                EventType.REMINDER_DRAFTED,
            )
            drafted += int(was_logged and reminder.get("kind") == "reminder_drafted")
            logged += int(was_logged)
            transitions += int(changed)
        scheduler.pending(latest_case, state)

    return {
        "cases_checked": len(active_cases),
        "followups_logged": logged,
        "status_changes": transitions,
        "reminders_drafted": drafted,
    }


def run_followup_tick(application: FastAPI) -> dict[str, int]:
    lock = getattr(application.state, "followup_tick_lock", None)
    if lock is None:
        return _run_followup_tick(application)
    with lock:
        return _run_followup_tick(application)


@router.post("/tick")
def followup_tick(request: Request) -> dict[str, int]:
    return run_followup_tick(request.app)
