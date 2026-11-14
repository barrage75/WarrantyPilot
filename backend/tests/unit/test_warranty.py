from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.contracts.enums import IncidentKind, IncidentReportedVia, VerdictValue
from app.contracts.models import Equipment, Incident, Verdict
from app.core.warranty import evaluate_equipment, inventory_verdict, savings_totals
from app.rules import DEFAULT_RULES_DIR, DeterministicRulesEngine, load_rules


def test_empty_inventory_totals(session_factory):
    with session_factory() as session:
        assert savings_totals(session, DeterministicRulesEngine(date(2026, 11, 14)), []) == {
            "covered_equipment_eur": 0,
            "possible_savings_eur": 0,
            "realized_savings_eur": 0,
        }


def test_missing_facts_do_not_invent_dates():
    item = Equipment(brand="Jabra", model="Evolve2 65", serial="TEST", category="headset")
    verdict, dates = inventory_verdict(
        DeterministicRulesEngine(date(2026, 11, 14)), item, [], load_rules(DEFAULT_RULES_DIR), []
    )
    assert verdict.value == VerdictValue.TO_VERIFY
    assert dates == {}


def test_shared_helper_supports_injected_engine_and_propagates_errors():
    item = Equipment(brand="Test", model="Test", serial="TEST", category="headset")
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=uuid4(),
        description="test",
        reported_via=IncidentReportedVia.CHAT,
    )
    engine = Mock()
    engine.evaluate.return_value = Verdict(
        value=VerdictValue.TO_VERIFY, explanation_fr="", explanation_en=""
    )
    assert evaluate_equipment(engine, item, [], incident, [], []).value == VerdictValue.TO_VERIFY
    engine.evaluate.assert_called_once_with(item, [], incident, [], [])
    engine.evaluate.side_effect = ValueError("bad input")
    with pytest.raises(ValueError, match="bad input"):
        evaluate_equipment(engine, item, [], incident, [], [])
