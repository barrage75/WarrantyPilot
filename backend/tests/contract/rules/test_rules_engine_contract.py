from app.contracts.interfaces import RulesEngine
from app.rules import DEMO_REFERENCE_DATE, DeterministicRulesEngine
from tests.contract.helpers import assert_rules_engine_contract
from tests.unit.rules.test_engine_cases import equipment, incident


def test_rules_engine_contract() -> None:
    engine: RulesEngine = DeterministicRulesEngine(DEMO_REFERENCE_DATE)
    result = assert_rules_engine_contract(engine, equipment(), incident())
    assert result.value == "to_verify"
