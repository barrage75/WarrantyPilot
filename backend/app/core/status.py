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
    CaseStatus.FAILED: frozenset({CaseStatus.SENDING, CaseStatus.CANCELLED}),
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
) -> CaseStatus:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(f"transition {current.value} -> {target.value} is forbidden")
    if target == CaseStatus.SENT and (
        current != CaseStatus.SENDING
        or action_result is None
        or action_result.status != ActionResultStatus.SUCCESS
        or not (action_result.proof and action_result.proof.strip())
    ):
        raise InvalidTransition("sent requires a successful ActionResult with proof")
    if current == CaseStatus.FAILED and target == CaseStatus.SENDING and attempts >= 2:
        raise InvalidTransition("failed cases may be retried at most twice")
    return target


def recover_interrupted_sends(
    session_factory: sessionmaker[Session] | None = None,
) -> int:
    """Return the number of cases that must be marked failed on process restart."""
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
            session.execute(
                update(cases).where(cases.c.id == case_id).values(status=CaseStatus.FAILED.value)
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
        return len(pending)
