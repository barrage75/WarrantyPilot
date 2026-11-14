from decimal import Decimal
from uuid import uuid4

import pytest

from app.contracts.enums import PolicyOutcome, VerdictValue
from app.contracts.models import Case, Equipment, Settings, Verdict
from app.core.policy import decide


def make_inputs() -> tuple[Case, Verdict, Equipment, Settings]:
    equipment_id = uuid4()
    case = Case(incident_id=uuid4(), equipment_id=equipment_id)
    verdict = Verdict(
        value=VerdictValue.COVERED,
        explanation_fr="Couvert",
        explanation_en="Covered",
    )
    equipment = Equipment(
        id=equipment_id,
        brand="Jabra",
        model="Evolve2 65",
        serial="TEST-001",
        category="headset",
        purchase_price=Decimal("100"),
    )
    settings = Settings(auto_send_threshold_eur=Decimal("200"))
    return case, verdict, equipment, settings


def test_auto_send_requires_all_six_conditions() -> None:
    case, verdict, equipment, settings = make_inputs()
    result = decide(
        case,
        verdict,
        equipment,
        "warranty_claim_email",
        settings,
        checklist_complete=True,
        equipment_unambiguous=True,
    )
    assert result.outcome == PolicyOutcome.AUTO_SEND
    assert len(result.conditions) == 6
    assert all(result.conditions.values())


@pytest.mark.parametrize(
    ("override", "action_kind"),
    [
        ({"settings": Settings(auto_send_threshold_eur=Decimal("0"))}, "warranty_claim_email"),
        (
            {
                "verdict": Verdict(
                    value=VerdictValue.LIKELY_COVERED,
                    explanation_fr="Probable",
                    explanation_en="Likely",
                )
            },
            "warranty_claim_email",
        ),
        ({"equipment_unambiguous": False}, "warranty_claim_email"),
        (
            {
                "verdict": Verdict(
                    value=VerdictValue.COVERED,
                    possible_exclusions=["choc"],
                    explanation_fr="Couvert sous réserve",
                    explanation_en="Covered subject to review",
                )
            },
            "warranty_claim_email",
        ),
        ({"suspicious_signal": True}, "warranty_claim_email"),
        ({}, "purchase_order"),
    ],
)
def test_each_false_condition_prevents_auto_send(
    override: dict[str, object], action_kind: str
) -> None:
    case, verdict, equipment, settings = make_inputs()
    selected_settings = override.get("settings", settings)
    selected_verdict = override.get("verdict", verdict)
    result = decide(
        case,
        selected_verdict,  # type: ignore[arg-type]
        equipment,
        action_kind,
        selected_settings,  # type: ignore[arg-type]
        equipment_unambiguous=override.get("equipment_unambiguous", True),  # type: ignore[arg-type]
        suspicious_signal=bool(override.get("suspicious_signal", False)),
    )
    assert result.outcome != PolicyOutcome.AUTO_SEND
    assert len(result.conditions) == 6


def test_pause_and_incomplete_data_checklist_are_blocking() -> None:
    case, verdict, equipment, settings = make_inputs()
    paused = decide(
        case,
        verdict,
        equipment,
        "warranty_claim_email",
        settings.model_copy(update={"agent_paused": True}),
    )
    checklist = decide(
        case,
        verdict,
        equipment,
        "warranty_claim_email",
        settings,
        requires_data_checklist=True,
        checklist_complete=False,
    )
    assert paused.outcome == PolicyOutcome.BLOCKED
    assert "agent_paused" in paused.reasons
    assert checklist.outcome == PolicyOutcome.BLOCKED
    assert "data_checklist_incomplete" in checklist.reasons


def test_zero_threshold_always_requires_validation() -> None:
    case, verdict, equipment, settings = make_inputs()
    equipment = equipment.model_copy(update={"purchase_price": Decimal("0")})
    result = decide(
        case,
        verdict,
        equipment,
        "warranty_claim_email",
        settings.model_copy(update={"auto_send_threshold_eur": Decimal("0")}),
    )
    assert result.conditions["under_threshold"] is False
    assert result.outcome == PolicyOutcome.NEEDS_VALIDATION


@pytest.mark.parametrize("action_kind", ["portal_claim", "api_claim", "manual_claim"])
def test_non_email_channels_are_not_low_commitment(action_kind: str) -> None:
    case, verdict, equipment, settings = make_inputs()
    result = decide(case, verdict, equipment, action_kind, settings)
    assert result.conditions["low_commitment_action"] is False
    assert result.outcome != PolicyOutcome.AUTO_SEND


def test_browser_claim_can_be_validated_without_completing_a_data_checklist() -> None:
    case, verdict, equipment, settings = make_inputs()
    result = decide(
        case,
        verdict,
        equipment,
        "portal_claim",
        settings,
        checklist_complete=False,
        requires_data_checklist=False,
    )
    assert result.outcome == PolicyOutcome.NEEDS_VALIDATION
    assert result.conditions["low_commitment_action"] is False


def test_lessor_email_is_low_commitment() -> None:
    case, verdict, equipment, settings = make_inputs()
    result = decide(case, verdict, equipment, "lessor_request", settings)
    assert result.conditions["low_commitment_action"] is True


def test_not_covered_is_blocked() -> None:
    case, verdict, equipment, settings = make_inputs()
    verdict = verdict.model_copy(update={"value": VerdictValue.NOT_COVERED})
    result = decide(case, verdict, equipment, "warranty_claim_email", settings)
    assert result.outcome == PolicyOutcome.BLOCKED
    assert "verdict_not_covered" in result.reasons
