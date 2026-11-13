from uuid import uuid4

from app.contracts.enums import ActionResultStatus, Channel, RealityBadge
from app.contracts.interfaces import ActionAdapter, DocumentExtractor, FollowUpChecker, RulesEngine
from app.contracts.models import Action, Case, Document, Equipment, Fact, Incident, Verdict


async def assert_action_adapter_contract(adapter: ActionAdapter) -> None:
    assert isinstance(adapter.channel, Channel)
    assert isinstance(adapter.badge, RealityBadge)
    action = Action(
        case_id=uuid4(),
        channel=adapter.channel,
        kind="contract_test",
        idempotency_key=f"contract:{uuid4()}",
        badge=adapter.badge,
    )
    result = await adapter.execute(action)
    assert result.action_id == action.id
    if result.status == ActionResultStatus.SUCCESS:
        assert result.proof and result.proof.strip()
    else:
        assert result.error


def assert_extractor_contract(
    extractor: DocumentExtractor,
    document: Document,
    content: bytes,
) -> list[Fact]:
    facts = extractor.extract(document, content)
    assert all(fact.document_id == document.id for fact in facts)
    assert all(fact.provenance.document_id == document.id for fact in facts)
    assert all(0 <= fact.confidence <= 1 for fact in facts)
    return facts


def assert_rules_engine_contract(
    rules_engine: RulesEngine,
    equipment: Equipment,
    incident: Incident,
) -> Verdict:
    verdict = rules_engine.evaluate(equipment, [], incident, [], [])
    assert verdict.checks
    assert all(check.name and check.detail for check in verdict.checks)
    return verdict


def assert_follow_up_contract(checker: FollowUpChecker, case: Case) -> None:
    assert all(isinstance(payload, dict) for payload in checker.check(case))
