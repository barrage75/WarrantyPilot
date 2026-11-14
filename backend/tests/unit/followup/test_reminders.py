from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.contracts.enums import CaseStatus, Channel
from app.contracts.models import Case
from app.followup import ReminderOutbox, ReminderPlanner, ReminderScheduler, ReminderState
from app.followup.clock import FollowUpClock

SENT = datetime(2026, 11, 1, 12, tzinfo=UTC)


def case():
    return Case(incident_id=uuid4(), channel=Channel.EMAIL_RESELLER, status=CaseStatus.SENT)


def test_zero_one_two_reminders_then_manual(tmp_path):
    now = SENT
    dossier = case()
    planner = ReminderPlanner(clock=lambda: now)
    outbox = ReminderOutbox(tmp_path / "outbox.sqlite3")
    scheduler = ReminderScheduler(planner, outbox)
    state = ReminderState(sent_at=SENT)
    assert scheduler.run(dossier, state) == []
    for ordinal in (1, 2):
        now += timedelta(days=7)
        result = scheduler.run(dossier, state)[0]
        assert result["kind"] == "reminder_drafted"
        assert result["reminder_number"] == ordinal
        assert result["executed"] is False
        assert scheduler.run(dossier, state) == []
        assert outbox.pending(dossier.id)[0] == result
        # Seule la preuve d'un envoi réel fait avancer l'état, pas la création du brouillon.
        state = ReminderState(SENT, (*state.reminder_sent_at, now))
        outbox.acknowledge(result["idempotency_key"])
        assert outbox.pending(dossier.id) == []
    now += timedelta(days=7)
    manual = scheduler.run(dossier, state)[0]
    assert manual["kind"] == "manual_takeover_recommended"
    assert manual["recommended_status"] == "manual_takeover"
    assert manual["reminder_number"] is None
    now += timedelta(days=365)
    assert scheduler.run(dossier, state) == []
    assert len(outbox.pending(dossier.id)) == 1
    assert dossier.status == CaseStatus.SENT


def test_restart_and_concurrent_runs_are_idempotent(tmp_path):
    path = tmp_path / "outbox.sqlite3"
    dossier, state = case(), ReminderState(SENT)
    planner = ReminderPlanner(clock=lambda: SENT + timedelta(days=7))
    first = ReminderScheduler(planner, ReminderOutbox(path)).run(dossier, state)
    restarted = ReminderScheduler(planner, ReminderOutbox(path))
    assert restarted.run(dossier, state) == []
    assert restarted.outbox.pending(dossier.id) == first
    fresh = case()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: restarted.run(fresh, state), range(12)))
    assert sum(bool(result) for result in results) == 1


def test_pending_drafts_are_hidden_after_response_or_resolution(tmp_path):
    dossier, state = case(), ReminderState(SENT)
    scheduler = ReminderScheduler(
        ReminderPlanner(clock=lambda: SENT + timedelta(days=7)),
        ReminderOutbox(tmp_path / "outbox.sqlite3"),
    )
    queued = scheduler.run(dossier, state)
    assert scheduler.pending(dossier, state) == queued
    for status in [CaseStatus.RESOLVED, CaseStatus.CANCELLED]:
        assert scheduler.pending(dossier.model_copy(update={"status": status}), state) == []
    replied = ReminderState(SENT, last_response_at=SENT + timedelta(days=1))
    assert scheduler.pending(dossier, replied) == []


@pytest.mark.parametrize("status", list(CaseStatus))
def test_only_sent_or_tracked_can_be_reminded(status):
    dossier = case().model_copy(update={"status": status})
    planner = ReminderPlanner(clock=lambda: SENT + timedelta(days=100))
    result = planner.plan(dossier, ReminderState(SENT))
    assert (result is not None) == (status in {CaseStatus.SENT, CaseStatus.TRACKED})


@pytest.mark.parametrize("channel", [Channel.MANUAL, Channel.API])
def test_manual_and_unsupported_channels_do_not_get_reminders(channel):
    dossier = case().model_copy(update={"channel": channel})
    assert ReminderPlanner(demo_today=date(2027, 1, 1)).plan(dossier, ReminderState(SENT)) is None


def test_reply_stops_reminders_and_clock_is_exact():
    dossier = case()
    planner = ReminderPlanner(after_days=3, clock=lambda: SENT + timedelta(days=3))
    assert (
        planner.plan(dossier, ReminderState(SENT))["due_at"]
        == (SENT + timedelta(days=3)).isoformat()
    )
    assert planner.plan(dossier, ReminderState(SENT, last_response_at=SENT)) is None
    before = ReminderPlanner(clock=lambda: SENT + timedelta(days=7, microseconds=-1))
    assert before.plan(dossier, ReminderState(SENT)) is None
    demo = ReminderPlanner(demo_today=date(2026, 11, 9))
    assert demo.plan(dossier, ReminderState(SENT))["planned_at"] == "2026-11-09T00:00:00+00:00"
    assert demo.plan(dossier, ReminderState(SENT)) == demo.plan(dossier, ReminderState(SENT))


@pytest.mark.parametrize("days", [0, -1, True, 1.5])
def test_invalid_interval_is_rejected(days):
    with pytest.raises(ValueError):
        ReminderPlanner(after_days=days)


def test_bad_clock_and_history_are_rejected():
    with pytest.raises(ValueError):
        FollowUpClock(lambda: datetime(2026, 1, 1)).now()
    with pytest.raises(ValueError):
        ReminderState(SENT, (SENT - timedelta(days=1),))
    with pytest.raises(ValueError):
        ReminderState(SENT, (SENT, SENT))
