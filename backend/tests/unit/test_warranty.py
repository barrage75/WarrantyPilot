from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.contracts.enums import IncidentKind, IncidentReportedVia, PurchaseGuardState, VerdictValue
from app.contracts.models import Equipment, Incident, Verdict
from app.core.tables import purchase_requests
from app.core.warranty import evaluate_equipment, inventory_verdict, savings_totals
from app.rules import DEFAULT_RULES_DIR, DeterministicRulesEngine, load_rules
from tests.integration.helpers import create_case


def test_empty_inventory_totals(session_factory):
    with session_factory() as session:
        assert savings_totals(session, DeterministicRulesEngine(date(2026, 11, 14)), []) == {
            "covered_equipment_eur": 0,
            "possible_savings_eur": 0,
            "realized_savings_eur": 0,
        }


@pytest.mark.parametrize("state", list(PurchaseGuardState))
def test_savings_totals_purchase_states(session_factory, state):
    case, person_id = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            purchase_requests.insert().values(
                id=str(uuid4()),
                requester_id=str(person_id),
                equipment_id=str(case.equipment_id),
                item_description="Replacement",
                amount=12,
                state=state.value,
            )
        )
    with session_factory() as session:
        totals = savings_totals(session, DeterministicRulesEngine(date(2026, 11, 14)), [])
    assert totals["realized_savings_eur"] == (
        12 if state == PurchaseGuardState.SAVING_REALIZED else 0
    )
    assert totals["possible_savings_eur"] == (
        0 if state in {PurchaseGuardState.SAVING_REALIZED, PurchaseGuardState.PURCHASE_KEPT} else 12
    )


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
