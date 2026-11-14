from datetime import UTC, date, datetime, time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.routers.cases import _case_from_row
from app.api.routers.followup import _reminder_state
from app.api.routers.overview import Coverage, overview
from app.core import tables

router = APIRouter(prefix="/notifications", tags=["notifications"])


class Notification(BaseModel):
    id: str
    kind: Literal[
        "warranty_expiring",
        "case_awaiting_validation",
        "reminder_due",
        "return_deadline",
        "case_failed",
    ]
    severity: Literal["info", "warning", "critical"]
    case_id: str | None
    equipment_id: str | None
    due_at: datetime | None
    params: dict[str, str | int | float | bool | None]


@router.get("", response_model=list[Notification])
def notifications(request: Request) -> list[Notification]:
    result = []
    application = request.app
    today = application.state.app_settings.demo_today
    for item in overview(request, Coverage.EXPIRING_SOON):
        if item.days_left is not None and item.days_left <= 30:
            result.append(
                Notification(
                    id=f"warranty_expiring:{item.equipment_id}",
                    kind="warranty_expiring",
                    severity="warning",
                    case_id=item.open_case_id,
                    equipment_id=item.equipment_id,
                    due_at=datetime.combine(item.warranty_end, time.min, UTC)
                    if item.warranty_end
                    else None,
                    params={"equipment_label": item.label, "days_left": item.days_left},
                )
            )
    with application.state.session_factory() as session:
        rows = session.execute(select(tables.cases).order_by(tables.cases.c.id)).mappings().all()
        case_models = [_case_from_row(session, row) for row in rows]
        deadline_events = (
            session.execute(select(tables.events).order_by(tables.events.c.seq)).mappings().all()
        )
    for case in case_models:
        case_id = str(case.id)
        equipment_id = str(case.equipment_id) if case.equipment_id else None
        if case.status.value in {"awaiting_validation", "failed", "manual_takeover"}:
            failed = case.status.value != "awaiting_validation"
            kind: Literal["case_failed", "case_awaiting_validation"] = (
                "case_failed" if failed else "case_awaiting_validation"
            )
            result.append(
                Notification(
                    id=f"{kind}:{case_id}",
                    kind=kind,
                    severity="critical" if failed else "info",
                    case_id=case_id,
                    equipment_id=equipment_id,
                    due_at=None,
                    params={"status": case.status.value},
                )
            )
        state = _reminder_state(application, UUID(case_id))
        if state is not None:
            plan = application.state.reminder_scheduler.planner.plan(case, state)
            if plan:
                result.append(
                    Notification(
                        id=f"reminder_due:{case_id}",
                        kind="reminder_due",
                        severity="warning",
                        case_id=case_id,
                        equipment_id=equipment_id,
                        due_at=plan["due_at"],
                        params={"reminder_number": plan["reminder_number"]},
                    )
                )
        latest = next(
            (
                row["payload"]
                for row in reversed(deadline_events)
                if row["case_id"] == case_id and row["payload"].get("kind") == "return_deadline"
            ),
            None,
        )
        if (
            latest
            and isinstance(latest.get("source"), str)
            and latest["source"].strip()
            and not latest.get("received_on")
            and case.status.value != "cancelled"
        ):
            try:
                due = date.fromisoformat(str(latest.get("due_on")))
            except ValueError:
                continue
            days = (due - today).days
            if days <= 7:
                result.append(
                    Notification(
                        id=f"return_deadline:{case_id}",
                        kind="return_deadline",
                        severity="critical" if days < 0 else "warning",
                        case_id=case_id,
                        equipment_id=equipment_id,
                        due_at=datetime.combine(due, time.min, UTC),
                        params={"days_left": days, "source": str(latest["source"])},
                    )
                )
    priority = {"critical": 0, "warning": 1, "info": 2}
    return sorted(
        result,
        key=lambda item: (
            priority[item.severity],
            item.due_at or datetime.max.replace(tzinfo=UTC),
            item.id,
        ),
    )
