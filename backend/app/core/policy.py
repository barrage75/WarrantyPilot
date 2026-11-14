from decimal import Decimal

from app.contracts.enums import PolicyOutcome, VerdictValue
from app.contracts.models import Case, Equipment, PolicyDecision, Settings, Verdict


def decide(
    case: Case,
    verdict: Verdict,
    equipment: Equipment | None,
    action_kind: str,
    settings: Settings,
    *,
    checklist_complete: bool = True,
    requires_data_checklist: bool = False,
    suspicious_signal: bool = False,
    equipment_unambiguous: bool | None = None,
) -> PolicyDecision:
    under_threshold = (
        equipment is not None
        and equipment.purchase_price is not None
        and settings.auto_send_threshold_eur > 0
        and equipment.purchase_price <= Decimal(str(settings.auto_send_threshold_eur))
    )
    conditions = {
        "under_threshold": under_threshold,
        "verdict_covered": verdict.value == VerdictValue.COVERED,
        "equipment_unambiguous": (
            equipment is not None if equipment_unambiguous is None else equipment_unambiguous
        ),
        "no_possible_exclusion": not verdict.possible_exclusions,
        "no_suspicious_signal": not suspicious_signal,
        "low_commitment_action": action_kind
        in {"request_information", "warranty_claim_email", "repair_request"},
    }
    reasons: list[str] = []
    if settings.agent_paused:
        reasons.append("agent_paused")
    if requires_data_checklist and not checklist_complete:
        reasons.append("data_checklist_incomplete")
    if verdict.value == VerdictValue.NOT_COVERED:
        reasons.append("verdict_not_covered")
    if reasons:
        outcome = PolicyOutcome.BLOCKED
    elif all(conditions.values()):
        outcome = PolicyOutcome.AUTO_SEND
    else:
        outcome = PolicyOutcome.NEEDS_VALIDATION
        reasons.extend(name for name, passed in conditions.items() if not passed)
    return PolicyDecision(outcome=outcome, reasons=reasons, conditions=conditions)
