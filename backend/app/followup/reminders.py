import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from app.contracts.enums import Channel
from app.contracts.models import Case
from app.followup.clock import Clock, FollowUpClock, checked_utc, utc_now
from app.followup.composite import effective_channel
from app.followup.portal import ACTIVE_STATUSES


@dataclass(frozen=True)
class ReminderState:
    sent_at: datetime
    reminder_sent_at: tuple[datetime, ...] = ()
    last_response_at: datetime | None = None

    def __post_init__(self) -> None:
        checked_utc(self.sent_at)
        for value in self.reminder_sent_at:
            checked_utc(value)
        if tuple(sorted(set(self.reminder_sent_at))) != self.reminder_sent_at:
            raise ValueError("Les envois de relance doivent être uniques et chronologiques")
        if self.reminder_sent_at and self.reminder_sent_at[0] < self.sent_at:
            raise ValueError("Une relance ne peut pas précéder l'envoi initial")
        if self.last_response_at is not None:
            checked_utc(self.last_response_at)


class ReminderPlanner:
    def __init__(
        self, *, after_days: int = 7, clock: Clock = utc_now, demo_today: date | None = None
    ) -> None:
        if isinstance(after_days, bool) or not isinstance(after_days, int) or after_days < 1:
            raise ValueError("Le délai de relance doit être un entier positif")
        self.after_days = after_days
        self.clock = FollowUpClock(clock, demo_today)

    def plan(self, case: Case, state: ReminderState) -> dict[str, Any] | None:
        if case.status not in ACTIVE_STATUSES or effective_channel(case) not in {
            Channel.EMAIL_RESELLER,
            Channel.EMAIL_MANUFACTURER_SUPPORT,
            Channel.EMAIL_LESSOR,
            Channel.BROWSER_PORTAL,
        }:
            return None
        last_contact = state.reminder_sent_at[-1] if state.reminder_sent_at else state.sent_at
        if state.last_response_at is not None and state.last_response_at >= state.sent_at:
            return None
        now = self.clock.now()
        due_at = checked_utc(last_contact) + timedelta(days=self.after_days)
        if now < due_at:
            return None
        count = len(state.reminder_sent_at)
        kind = "manual_takeover_recommended" if count >= 2 else "reminder_drafted"
        ordinal = min(count + 1, 3)
        return {
            "kind": kind,
            "case_id": str(case.id),
            "channel": effective_channel(case).value,
            "idempotency_key": f"case:{case.id}:followup:{ordinal}",
            "reminder_number": count + 1 if count < 2 else None,
            "due_at": due_at.isoformat(),
            "planned_at": now.isoformat(),
            "recommended_status": "manual_takeover" if count >= 2 else None,
            "executed": False,
        }


class ReminderOutbox:
    """Durable drafts, not delivery receipts; pending entries survive a consumer crash."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS followup_outbox ("
                "key TEXT PRIMARY KEY, case_id TEXT NOT NULL, payload TEXT NOT NULL, "
                "acknowledged INTEGER NOT NULL DEFAULT 0)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def enqueue(self, payload: dict[str, Any]) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO followup_outbox (key,case_id,payload) VALUES (?,?,?)",
                (payload["idempotency_key"], payload["case_id"], json.dumps(payload)),
            )
            return cursor.rowcount == 1

    def pending(self, case_id: UUID) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload FROM followup_outbox WHERE case_id=? AND acknowledged=0 "
                "ORDER BY rowid",
                (str(case_id),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def acknowledge(self, key: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE followup_outbox SET acknowledged=1 WHERE key=?", (key,))


class ReminderScheduler:
    def __init__(self, planner: ReminderPlanner, outbox: ReminderOutbox) -> None:
        self.planner, self.outbox = planner, outbox

    def run(self, case: Case, state: ReminderState) -> list[dict[str, Any]]:
        payload = self.planner.plan(case, state)
        if payload is not None and self.outbox.enqueue(payload):
            return [payload]
        return []

    def pending(self, case: Case, state: ReminderState) -> list[dict[str, Any]]:
        """Recheck eligibility before exposing an unacknowledged draft to a consumer."""
        eligible = self.planner.plan(case, state)
        if eligible is None:
            return []
        return [
            item
            for item in self.outbox.pending(case.id)
            if item["idempotency_key"] == eligible["idempotency_key"]
        ]
