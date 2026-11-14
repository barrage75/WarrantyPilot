from sqlalchemy import select

from app.contracts.enums import CaseStatus, EventType
from app.core.journal import append_event, verify
from app.core.orchestrator import Orchestrator
from app.core.status import recover_interrupted_sends
from app.core.tables import action_results, actions, case_steps, cases, events
from app.testing.fakes import (
    CrashingActionAdapter,
    FailingActionAdapter,
    FakeActionAdapter,
    FakeExtractor,
    FakeFollowUp,
    FakeRulesEngine,
)
from tests.integration.helpers import create_case


def make_orchestrator(factory, app_settings, adapter):
    return Orchestrator(
        session_factory=factory,
        extractor=FakeExtractor(),
        rules_engine=FakeRulesEngine(),
        action_adapter=adapter,
        follow_up=FakeFollowUp(),
        app_settings=app_settings,
    )


def approve(factory, case_id, person_id):
    with factory.begin() as session:
        append_event(
            session,
            EventType.VALIDATED,
            actor=f"human:{person_id}",
            case_id=str(case_id),
            payload={"approved": True},
        )


async def test_case_runs_from_prepared_through_resolved(session_factory, app_settings) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["allowed@example.test"],
    )
    adapter = FakeActionAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, adapter)

    pending = await orchestrator.run(case.id)
    assert pending.status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)
    resolved = await orchestrator.run(case.id)

    assert resolved.status == CaseStatus.RESOLVED
    assert len(adapter.calls) == 1
    with session_factory() as session:
        persisted_status = session.execute(
            select(cases.c.status).where(cases.c.id == str(case.id))
        ).scalar_one()
        step_names = (
            session.execute(
                select(case_steps.c.step_name)
                .where(case_steps.c.case_id == str(case.id))
                .order_by(case_steps.c.order)
            )
            .scalars()
            .all()
        )
        event_types = (
            session.execute(select(events.c.type).where(events.c.case_id == str(case.id)))
            .scalars()
            .all()
        )
        journal_status = verify(session, app_settings)
    assert persisted_status == CaseStatus.RESOLVED.value
    assert {
        "identify",
        "find_proof",
        "evaluate",
        "decide",
        "await_validation",
        "execute",
        "track",
    } <= set(step_names)
    assert EventType.ACTION_SUCCEEDED.value in event_types
    assert journal_status["ok"] is True


async def test_failure_can_retry_once_with_a_new_idempotency_key(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["allowed@example.test"],
    )
    failing = FailingActionAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, failing)
    assert (await orchestrator.run(case.id)).status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)
    assert (await orchestrator.run(case.id)).status == CaseStatus.FAILED

    retry = FakeActionAdapter()
    orchestrator.action_adapter = retry
    assert (await orchestrator.run(case.id)).status == CaseStatus.RESOLVED
    assert len(failing.calls) == 1
    assert len(retry.calls) == 1
    assert failing.calls[0] != retry.calls[0]
    with session_factory() as session:
        results = (
            session.execute(
                select(action_results.c.status)
                .join(actions, action_results.c.action_id == actions.c.id)
                .order_by(actions.c.idempotency_key)
            )
            .scalars()
            .all()
        )
    assert results == ["failure", "success"]


async def test_interrupted_send_is_failed_and_not_replayed(session_factory, app_settings) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["allowed@example.test"],
    )
    crashing = CrashingActionAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, crashing)
    await orchestrator.run(case.id)
    approve(session_factory, case.id, person_id)
    try:
        await orchestrator.run(case.id)
    except RuntimeError as error:
        assert "simulated adapter process crash" in str(error)
    else:
        raise AssertionError("the crash fake should raise")

    assert recover_interrupted_sends(session_factory) == 1
    result = await orchestrator.run(case.id)
    assert result.status == CaseStatus.FAILED
    assert len(crashing.calls) == 1
    with session_factory() as session:
        state = session.execute(
            select(cases.c.status).where(cases.c.id == str(case.id))
        ).scalar_one()
        journal_status = verify(session, app_settings)
    assert state == CaseStatus.FAILED.value
    assert journal_status["ok"] is True


async def test_pause_prevents_adapter_execution(session_factory, app_settings) -> None:
    case, _ = create_case(session_factory, paused=True)
    adapter = FakeActionAdapter()
    result = await make_orchestrator(session_factory, app_settings, adapter).run(case.id)
    assert result.status == CaseStatus.PREPARED
    assert adapter.calls == []


async def test_email_outside_allowlist_is_refused_before_adapter(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(
        session_factory,
        email="blocked@example.test",
        allowlist=["allowed@example.test"],
    )
    adapter = FakeActionAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, adapter)
    await orchestrator.run(case.id)
    approve(session_factory, case.id, person_id)
    result = await orchestrator.run(case.id)
    assert result.status == CaseStatus.FAILED
    assert adapter.calls == []
    with session_factory() as session:
        result_status = session.execute(select(action_results.c.status)).scalar_one()
    assert result_status == "failure"
