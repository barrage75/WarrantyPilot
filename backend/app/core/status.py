from collections.abc import Sequence
from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from app.contracts.enums import ActionResultStatus, CaseStatus
from app.contracts.models import ActionResult


class InvalidTransition(ValueError):
    pass


TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.PREPARED: frozenset(
        {
            CaseStatus.AWAITING_VALIDATION,
            CaseStatus.SENDING,
            CaseStatus.FAILED,
            CaseStatus.CANCELLED,
        }
    ),
    CaseStatus.AWAITING_VALIDATION: frozenset(
        {CaseStatus.SENDING, CaseStatus.FAILED, CaseStatus.CANCELLED}
    ),
    CaseStatus.SENDING: frozenset({CaseStatus.SENT, CaseStatus.FAILED}),
    CaseStatus.SENT: frozenset({CaseStatus.TRACKED, CaseStatus.RESOLVED}),
    CaseStatus.FAILED: frozenset(
        {CaseStatus.SENDING, CaseStatus.MANUAL_TAKEOVER, CaseStatus.CANCELLED}
    ),
    CaseStatus.MANUAL_TAKEOVER: frozenset({CaseStatus.SENT, CaseStatus.CANCELLED}),
    CaseStatus.TRACKED: frozenset({CaseStatus.RESOLVED, CaseStatus.FAILED}),
    CaseStatus.RESOLVED: frozenset(),
    CaseStatus.CANCELLED: frozenset(),
}


def transition(
    current: CaseStatus,
    target: CaseStatus,
    *,
    action_result: ActionResult | None = None,
    attempts: int = 0,
    actor: str | None = None,
) -> CaseStatus:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(f"transition {current.value} -> {target.value} is forbidden")
    if target == CaseStatus.SENT and (
        current not in {CaseStatus.SENDING, CaseStatus.MANUAL_TAKEOVER}
        or action_result is None
        or action_result.status != ActionResultStatus.SUCCESS
        or not (action_result.proof and action_result.proof.strip())
    ):
        raise InvalidTransition("sent requires a successful ActionResult with proof")
    if (
        current == CaseStatus.MANUAL_TAKEOVER
        and target == CaseStatus.SENT
        and (actor is None or not actor.startswith("human:") or not actor.removeprefix("human:"))
    ):
        raise InvalidTransition("manual takeover requires proof from a human actor")
    if current == CaseStatus.FAILED and target == CaseStatus.SENDING and attempts >= 2:
        raise InvalidTransition("failed cases may be retried at most twice")
    return target


def recover_interrupted_sends(
    session_factory: sessionmaker[Session] | None = None,
) -> int:
    """Recover interrupted sends, transferring exhausted retries to a human."""
    from sqlalchemy import select, update

    from app.contracts.enums import EventType
    from app.core.db import SessionLocal
    from app.core.journal import append_event
    from app.core.tables import case_steps, cases

    factory = session_factory or SessionLocal
    with factory.begin() as session:
        pending = cast(
            Sequence[str],
            session.execute(select(cases.c.id).where(cases.c.status == CaseStatus.SENDING.value))
            .scalars()
            .all(),
        )
        for case_id in pending:
            attempt = session.execute(
                select(case_steps.c.attempt)
                .where(
                    case_steps.c.case_id == case_id,
                    case_steps.c.step_name == "execute",
                )
                .limit(1)
            ).scalar_one_or_none()
            failed_status = transition(CaseStatus.SENDING, CaseStatus.FAILED)
            session.execute(
                update(cases).where(cases.c.id == case_id).values(status=failed_status.value)
            )
            session.execute(
                update(case_steps)
                .where(
                    case_steps.c.case_id == case_id,
                    case_steps.c.step_name == "execute",
                    case_steps.c.status == "running",
                )
                .values(
                    status="failed",
                    output={"unknown_outcome": True},
                )
            )
            append_event(
                session,
                EventType.ACTION_FAILED,
                case_id=case_id,
                payload={"reason": "process_restarted_during_sending"},
            )
            append_event(
                session,
                EventType.STATUS_CHANGED,
                case_id=case_id,
                payload={"from": CaseStatus.SENDING.value, "to": CaseStatus.FAILED.value},
            )
            if attempt is not None and int(attempt) >= 2:
                takeover_status = transition(failed_status, CaseStatus.MANUAL_TAKEOVER)
                session.execute(
                    update(cases).where(cases.c.id == case_id).values(status=takeover_status.value)
                )
                append_event(
                    session,
                    EventType.STATUS_CHANGED,
                    case_id=case_id,
                    payload={
                        "from": failed_status.value,
                        "to": takeover_status.value,
                        "reason": "retry_limit_reached",
                    },
                )
        return len(pending)
