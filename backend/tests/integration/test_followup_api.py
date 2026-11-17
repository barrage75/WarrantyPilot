from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from app.api.main import create_app
from app.api.routers.followup import _reminder_state
from app.contracts.enums import (
    CaseStatus,
    Channel,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    PurchaseGuardState,
    RealityBadge,
)
from app.contracts.models import utc_now
from app.core.journal import append_event
from app.core.tables import (
    action_results,
    actions,
    cases,
    equipment,
    events,
    incidents,
    people,
    purchase_requests,
)
from app.followup.clock import utc_now as followup_now
from app.followup.reminders import ReminderOutbox, ReminderPlanner, ReminderScheduler
from tests.auth_helpers import SAMY_ID, login


class StaticFollowUp:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = results

    def check(self, _case) -> list[dict[str, object]]:
        return list(self.results)


def _reset(client: TestClient) -> None:
    login(client, person_id=SAMY_ID)
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200


def _seed_case(session_factory, status: CaseStatus) -> UUID:
    case_id = uuid4()
    incident_id = uuid4()
    now = utc_now()
    with session_factory.begin() as session:
        person_id = session.execute(
            select(people.c.id).where(people.c.name == "Paul Martin")
        ).scalar_one()
        equipment_id = session.execute(
            select(equipment.c.id)
            .where(equipment.c.assigned_to == person_id, equipment.c.model == "Evolve2 65")
            .limit(1)
        ).scalar_one()
        session.execute(
            insert(incidents).values(
                id=str(incident_id),
                kind=IncidentKind.FAILURE.value,
                reporter_id=person_id,
                equipment_id=equipment_id,
                description="Défaillance de test.",
                reported_via=IncidentReportedVia.CHAT.value,
                created_at=now.isoformat(),
            )
        )
        session.execute(
            insert(cases).values(
                id=str(case_id),
                incident_id=str(incident_id),
                equipment_id=equipment_id,
                status=status.value,
                verdict_id=None,
                policy_id=None,
                channel=Channel.EMAIL_RESELLER.value,
                badge=RealityBadge.REPRODUCTION.value,
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
            )
        )
        append_event(
            session,
            EventType.CASE_CREATED,
            case_id=str(case_id),
            payload={"incident_id": str(incident_id), "equipment_id": equipment_id},
        )
    return case_id


def test_followup_tick_tracks_accepted_email_once_and_ignores_errors(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(
        app_settings=app_settings,
        app_engine=db_engine,
        session_factory=session_factory,
    )
    with TestClient(application) as client:
        _reset(client)
        case_id = _seed_case(session_factory, CaseStatus.SENT)
        application.state.services["follow_up"] = StaticFollowUp(
            [{"message_id": "<reply-1@example.test>", "outcome": "accepted"}]
        )

        first = client.post("/api/followup/tick")
        second = client.post("/api/followup/tick")
        assert first.status_code == second.status_code == 200
        with session_factory() as session:
            case_status = session.execute(
                select(cases.c.status).where(cases.c.id == str(case_id))
            ).scalar_one()
            replies = (
                session.execute(
                    select(events.c.payload).where(
                        events.c.case_id == str(case_id),
                        events.c.type == EventType.FOLLOWUP_RECEIVED.value,
                    )
                )
                .scalars()
                .all()
            )
        assert case_status == CaseStatus.TRACKED.value
        assert len(replies) == 1
        assert replies[0]["message_id"] == "<reply-1@example.test>"

        application.state.services["follow_up"] = StaticFollowUp(
            [{"kind": "followup_error", "code": "mailbox_unavailable"}]
        )
        error_tick = client.post("/api/followup/tick")
        assert error_tick.status_code == 200
        with session_factory() as session:
            case_status = session.execute(
                select(cases.c.status).where(cases.c.id == str(case_id))
            ).scalar_one()
        assert case_status == CaseStatus.TRACKED.value


def test_followup_tick_drafts_reminder_and_reset_clears_outbox(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(
        app_settings=app_settings,
        app_engine=db_engine,
        session_factory=session_factory,
    )
    with TestClient(application) as client:
        _reset(client)
        case_id = _seed_case(session_factory, CaseStatus.SENT)
        action_id = uuid4()
        result_id = uuid4()
        with session_factory.begin() as session:
            session.execute(
                insert(actions).values(
                    id=str(action_id),
                    case_id=str(case_id),
                    channel=Channel.EMAIL_RESELLER.value,
                    kind="warranty_claim_email",
                    idempotency_key=f"case:{case_id}:email_reseller:reseller@example.test",
                    payload={},
                    badge=RealityBadge.REPRODUCTION.value,
                    requires_data_checklist=False,
                )
            )
            session.execute(
                insert(action_results).values(
                    id=str(result_id),
                    action_id=str(action_id),
                    status="success",
                    proof="message-id: initial",
                    error=None,
                    badge=RealityBadge.REPRODUCTION.value,
                )
            )
            append_event(
                session,
                EventType.ACTION_SUCCEEDED,
                case_id=str(case_id),
                payload={"action_id": str(action_id), "proof": "message-id: initial"},
            )
        application.state.services["follow_up"] = StaticFollowUp([])
        application.state.reminder_scheduler = ReminderScheduler(
            ReminderPlanner(
                after_days=1,
                clock=lambda: followup_now() + timedelta(days=2),
            ),
            ReminderOutbox(app_settings.followup_outbox_path),
        )

        first = client.post("/api/followup/tick")
        second = client.post("/api/followup/tick")
        assert first.status_code == second.status_code == 200
        drafts = application.state.reminder_outbox.pending(case_id)
        assert len(drafts) == 1
        assert drafts[0]["kind"] == "reminder_drafted"
        assert drafts[0]["executed"] is False
        with session_factory() as session:
            reminder_events = (
                session.execute(
                    select(events.c.payload).where(
                        events.c.case_id == str(case_id),
                        events.c.type == EventType.REMINDER_DRAFTED.value,
                    )
                )
                .scalars()
                .all()
            )
        assert len(reminder_events) == 1

        _reset(client)
        assert application.state.reminder_outbox.pending(case_id) == []


def test_human_case_resolution_requires_person_and_note_and_realizes_cancelled_saving(
    db_engine, session_factory, app_settings
) -> None:
    application = create_app(
        app_settings=app_settings,
        app_engine=db_engine,
        session_factory=session_factory,
    )
    with TestClient(application) as client:
        _reset(client)
        case_id = _seed_case(session_factory, CaseStatus.TRACKED)
        prepared_case_id = _seed_case(session_factory, CaseStatus.PREPARED)
        people_response = client.get("/api/people")
        operator = next(
            person
            for person in people_response.json()
            if person["role"] == "responsable informatique"
        )
        with session_factory.begin() as session:
            purchase_id = session.execute(select(purchase_requests.c.id)).scalar_one()
            session.execute(
                update(purchase_requests)
                .where(purchase_requests.c.id == purchase_id)
                .values(
                    case_id=str(case_id),
                    state=PurchaseGuardState.PURCHASE_SUSPENDED.value,
                )
            )

        unknown_person = client.post(
            f"/api/cases/{case_id}/resolve",
            json={"person_id": str(uuid4()), "note": "Résolu"},
        )
        missing_case = client.post(
            f"/api/cases/{uuid4()}/resolve",
            json={"person_id": operator["id"], "note": "Résolu"},
        )
        conflict = client.post(
            f"/api/cases/{prepared_case_id}/resolve",
            json={"person_id": operator["id"], "note": "Résolu"},
        )
        blank_note = client.post(
            f"/api/cases/{case_id}/resolve",
            json={"person_id": operator["id"], "note": "  "},
        )
        assert unknown_person.status_code == 403
        assert missing_case.status_code == 404
        assert conflict.status_code == 409
        assert blank_note.status_code == 422

        cancelled = client.post(
            f"/api/purchase-requests/{purchase_id}/confirm-cancellation",
            json={"person_id": operator["id"]},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == PurchaseGuardState.CANCELLED.value
        resolved = client.post(
            f"/api/cases/{case_id}/resolve",
            json={
                "person_id": operator["id"],
                "note": "Remplacement reçu.",
            },
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["status"] == CaseStatus.RESOLVED.value

        with session_factory() as session:
            status_event = (
                session.execute(
                    select(events)
                    .where(
                        events.c.case_id == str(case_id),
                        events.c.type == EventType.STATUS_CHANGED.value,
                    )
                    .order_by(events.c.seq.desc())
                )
                .mappings()
                .first()
            )
            purchase_state = session.execute(
                select(purchase_requests.c.state).where(purchase_requests.c.id == purchase_id)
            ).scalar_one()
        assert status_event is not None
        assert status_event["actor"] == f"human:{operator['id']}"
        assert status_event["payload"]["note"] == "Remplacement reçu."
        assert purchase_state == PurchaseGuardState.SAVING_REALIZED.value


def _seed_sent_portal_case(session_factory) -> UUID:
    case_id = _seed_case(session_factory, CaseStatus.SENT)
    action_id = uuid4()
    with session_factory.begin() as session:
        session.execute(
            insert(actions).values(
                id=str(action_id),
                case_id=str(case_id),
                channel=Channel.BROWSER_PORTAL.value,
                kind="dell_portal_submission",
                idempotency_key=f"case:{case_id}:browser_portal:dell",
                payload={},
                badge=RealityBadge.REPRODUCTION.value,
                requires_data_checklist=False,
            )
        )
        session.execute(
            insert(action_results).values(
                id=str(uuid4()),
                action_id=str(action_id),
                status="success",
                proof="case_number: 1234567890",
                error=None,
                badge=RealityBadge.REPRODUCTION.value,
            )
        )
        append_event(
            session,
            EventType.ACTION_SUCCEEDED,
            case_id=str(case_id),
            payload={"action_id": str(action_id), "proof": "case_number: 1234567890"},
        )
    return case_id


def _portal_reading(case_id: UUID, portal_status: str, status: str = "tracked"):
    return {
        "kind": "portal_status",
        "case_id": str(case_id),
        "status": status,
        "proof": {
            "url": "http://127.0.0.1:8100/support/status/1234567890",
            "case_number": "1234567890",
            "portal_status": portal_status,
            "observed_at": followup_now().isoformat(),
        },
        "reality": "reproduction",
        "untrusted": True,
    }


def _portal_app(db_engine, session_factory, app_settings):
    return create_app(
        app_settings=app_settings,
        app_engine=db_engine,
        session_factory=session_factory,
    )


def _install_due_scheduler(application, app_settings) -> None:
    application.state.reminder_scheduler = ReminderScheduler(
        ReminderPlanner(after_days=1, clock=lambda: followup_now() + timedelta(days=2)),
        ReminderOutbox(app_settings.followup_outbox_path),
    )


def test_followup_repeated_received_portal_status_does_not_stop_reminders(
    db_engine, session_factory, app_settings
) -> None:
    application = _portal_app(db_engine, session_factory, app_settings)
    with TestClient(application) as client:
        _reset(client)
        _install_due_scheduler(application, app_settings)
        case_id = _seed_sent_portal_case(session_factory)
        application.state.services["follow_up"] = StaticFollowUp(
            [_portal_reading(case_id, "received")]
        )
        for _ in range(3):
            assert client.post("/api/followup/tick").status_code == 200
        state = _reminder_state(application, case_id)
        assert state is not None and state.last_response_at is None
        drafts = application.state.reminder_outbox.pending(case_id)
        assert [draft["kind"] for draft in drafts] == ["reminder_drafted"]
        with session_factory() as session:
            assert (
                session.execute(
                    select(cases.c.status).where(cases.c.id == str(case_id))
                ).scalar_one()
                == CaseStatus.TRACKED.value
            )


def test_followup_portal_status_change_counts_as_response_once(
    db_engine, session_factory, app_settings
) -> None:
    application = _portal_app(db_engine, session_factory, app_settings)
    with TestClient(application) as client:
        _reset(client)
        _install_due_scheduler(application, app_settings)
        case_id = _seed_sent_portal_case(session_factory)
        with session_factory.begin() as session:
            append_event(
                session,
                EventType.FOLLOWUP_RECEIVED,
                case_id=str(case_id),
                payload=_portal_reading(case_id, "received"),
            )
        state = _reminder_state(application, case_id)
        assert state is not None and state.last_response_at is None

        application.state.services["follow_up"] = StaticFollowUp(
            [_portal_reading(case_id, "in_progress")]
        )
        for _ in range(3):
            assert client.post("/api/followup/tick").status_code == 200
        state = _reminder_state(application, case_id)
        assert state is not None and state.last_response_at is not None
        assert application.state.reminder_outbox.pending(case_id) == []
        with session_factory() as session:
            readings = (
                session.execute(
                    select(events.c.payload).where(
                        events.c.case_id == str(case_id),
                        events.c.type == EventType.FOLLOWUP_RECEIVED.value,
                    )
                )
                .scalars()
                .all()
            )
        assert [r["proof"]["portal_status"] for r in readings] == ["received", "in_progress"]


def test_followup_email_reply_still_counts_as_response(
    db_engine, session_factory, app_settings
) -> None:
    application = _portal_app(db_engine, session_factory, app_settings)
    with TestClient(application) as client:
        _reset(client)
        case_id = _seed_sent_portal_case(session_factory)
        with session_factory.begin() as session:
            append_event(
                session,
                EventType.FOLLOWUP_RECEIVED,
                case_id=str(case_id),
                payload={"kind": "email_reply", "message_id": "<r@example.test>"},
            )
        state = _reminder_state(application, case_id)
        assert state is not None and state.last_response_at is not None
