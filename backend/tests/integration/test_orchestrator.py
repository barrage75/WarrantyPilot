from sqlalchemy import select, update

from app.contracts.enums import CaseStatus, Channel, EventType, RealityBadge, VerdictValue
from app.contracts.models import Verdict
from app.core.journal import append_event, verify
from app.core.orchestrator import Orchestrator
from app.core.status import recover_interrupted_sends
from app.core.tables import (
    action_results,
    actions,
    case_steps,
    cases,
    data_checklists,
    equipment,
    events,
)
from app.testing.fakes import (
    CrashingActionAdapter,
    FailingActionAdapter,
    FakeBrowserAdapter,
    FakeEmailAdapter,
    FakeExtractor,
    FakeRulesEngine,
)
from tests.integration.helpers import create_case


def make_orchestrator(factory, app_settings, adapter=None, rules_engine=None):
    return Orchestrator(
        session_factory=factory,
        extractor=FakeExtractor(),
        rules_engine=rules_engine or FakeRulesEngine(),
        action_adapters={adapter.channel: adapter} if adapter is not None else {},
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


async def test_case_runs_from_prepared_through_tracked(session_factory, app_settings) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["warranty@revendeur-test.example"],
    )
    adapter = FakeEmailAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, adapter)

    pending = await orchestrator.run(case.id)
    assert pending.status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)
    tracked = await orchestrator.run(case.id)

    assert tracked.status == CaseStatus.TRACKED
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
    assert persisted_status == CaseStatus.TRACKED.value
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


async def test_case_badge_changes_only_after_action_execution(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["warranty@revendeur-test.example"],
    )
    adapter = FakeEmailAdapter()
    adapter.badge = RealityBadge.REPRODUCTION
    orchestrator = make_orchestrator(session_factory, app_settings, adapter)

    pending = await orchestrator.run(case.id)
    assert pending.status == CaseStatus.AWAITING_VALIDATION
    assert pending.badge == RealityBadge.SIMULATED
    with session_factory() as session:
        initial_badge = session.execute(
            select(cases.c.badge).where(cases.c.id == str(case.id))
        ).scalar_one()
    assert initial_badge == RealityBadge.SIMULATED.value

    approve(session_factory, case.id, person_id)
    tracked = await orchestrator.run(case.id)

    assert tracked.status == CaseStatus.TRACKED
    assert tracked.badge == RealityBadge.REPRODUCTION
    with session_factory() as session:
        persisted_badge = session.execute(
            select(cases.c.badge).where(cases.c.id == str(case.id))
        ).scalar_one()
    assert persisted_badge == RealityBadge.REPRODUCTION.value


async def test_computer_case_gets_data_checklist_from_orchestrator(
    session_factory, app_settings
) -> None:
    case, _ = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(equipment)
            .where(equipment.c.id == str(case.equipment_id))
            .values(category="computer")
        )

    orchestrator = make_orchestrator(
        session_factory,
        app_settings,
        FakeEmailAdapter(),
    )
    await orchestrator.run(case.id)

    with session_factory() as session:
        steps = session.execute(
            select(data_checklists.c.steps).where(data_checklists.c.case_id == str(case.id))
        ).scalar_one()
    assert len(steps) == 7
    assert all(not step["done"] for step in steps.values())


async def test_failure_can_retry_once_with_a_stable_idempotency_key(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["warranty@revendeur-test.example"],
    )
    failing = FailingActionAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, failing)
    assert (await orchestrator.run(case.id)).status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)
    assert (await orchestrator.run(case.id)).status == CaseStatus.FAILED

    retry = FakeEmailAdapter()
    orchestrator.action_adapters[retry.channel] = retry
    assert (await orchestrator.run(case.id)).status == CaseStatus.TRACKED
    assert len(failing.calls) == 1
    assert len(retry.calls) == 1
    assert failing.calls[0] == retry.calls[0]
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
    assert sorted(results) == ["failure", "success"]


async def test_exhausted_retries_escalate_to_manual_takeover(session_factory, app_settings) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["warranty@revendeur-test.example"],
    )
    adapter = FailingActionAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, adapter)
    assert (await orchestrator.run(case.id)).status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)

    assert (await orchestrator.run(case.id)).status == CaseStatus.FAILED
    assert (await orchestrator.run(case.id)).status == CaseStatus.MANUAL_TAKEOVER
    assert len(adapter.calls) == 2


async def test_interrupted_send_is_failed_and_not_replayed(session_factory, app_settings) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["warranty@revendeur-test.example"],
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
    adapter = FakeEmailAdapter()
    result = await make_orchestrator(session_factory, app_settings, adapter).run(case.id)
    assert result.status == CaseStatus.PREPARED
    assert adapter.calls == []


async def test_email_outside_allowlist_is_refused_before_adapter(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(
        session_factory,
        email="blocked@example.test",
        allowlist=["other@revendeur-test.example"],
    )
    adapter = FakeEmailAdapter()
    orchestrator = make_orchestrator(session_factory, app_settings, adapter)
    await orchestrator.run(case.id)
    approve(session_factory, case.id, person_id)
    result = await orchestrator.run(case.id)
    assert result.status == CaseStatus.FAILED
    assert adapter.calls == []
    with session_factory() as session:
        result_status = session.execute(select(action_results.c.status)).scalar_one()
    assert result_status == "failure"


async def test_missing_channel_adapter_records_failure_without_raising(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(session_factory)
    verdict = Verdict(
        value=VerdictValue.COVERED,
        channel=Channel.API,
        explanation_fr="Couvert",
        explanation_en="Covered",
    )
    orchestrator = make_orchestrator(
        session_factory,
        app_settings,
        rules_engine=FakeRulesEngine(verdict),
    )
    assert (await orchestrator.run(case.id)).status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)

    result = await orchestrator.run(case.id)

    assert result.status == CaseStatus.FAILED
    with session_factory() as session:
        action = session.execute(select(actions)).mappings().one()
        action_result = session.execute(select(action_results)).mappings().one()
    assert action["channel"] == Channel.API.value
    assert action["kind"] == "api_claim"
    assert action_result["status"] == "failure"
    assert action_result["error"] == "no_adapter_for_channel"


async def test_browser_adapter_uses_verdict_channel_and_url(session_factory, app_settings) -> None:
    case, person_id = create_case(session_factory)
    verdict = Verdict(
        value=VerdictValue.COVERED,
        channel=Channel.BROWSER_PORTAL,
        target_url="http://localhost:8100/claim",
        explanation_fr="Couvert",
        explanation_en="Covered",
    )
    adapter = FakeBrowserAdapter()
    orchestrator = make_orchestrator(
        session_factory,
        app_settings,
        adapter,
        FakeRulesEngine(verdict),
    )
    assert (await orchestrator.run(case.id)).status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)

    result = await orchestrator.run(case.id)

    assert result.status == CaseStatus.TRACKED
    with session_factory() as session:
        action = session.execute(select(actions)).mappings().one()
    assert action["channel"] == Channel.BROWSER_PORTAL.value
    assert action["kind"] == "portal_claim"
    assert action["payload"]["url"] == "http://localhost:8100/claim"


async def test_case_channel_is_used_when_verdict_channel_is_missing(
    session_factory, app_settings
) -> None:
    case, person_id = create_case(
        session_factory,
        email="allowed@example.test",
        allowlist=["warranty@revendeur-test.example"],
    )
    verdict = Verdict(
        value=VerdictValue.COVERED,
        explanation_fr="Couvert",
        explanation_en="Covered",
    )
    adapter = FakeEmailAdapter()
    orchestrator = make_orchestrator(
        session_factory,
        app_settings,
        adapter,
        FakeRulesEngine(verdict),
    )
    assert (await orchestrator.run(case.id)).status == CaseStatus.AWAITING_VALIDATION
    approve(session_factory, case.id, person_id)

    result = await orchestrator.run(case.id)

    assert result.status == CaseStatus.TRACKED
    with session_factory() as session:
        action = session.execute(select(actions)).mappings().one()
    assert action["channel"] == case.channel.value
