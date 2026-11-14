from collections.abc import Iterable
from decimal import Decimal

from app.contracts.enums import FactField, FactSource, PolicyOutcome, VerdictValue
from app.contracts.models import Case, Equipment, Fact, PolicyDecision, Settings, Verdict

PURCHASE_PROOF_FIELDS = frozenset(
    {FactField.PURCHASE_DATE.value, FactField.INVOICE_DATE.value, FactField.DELIVERY_DATE.value}
)


def purchase_proof_is_llm_only(facts: Iterable[Fact]) -> bool:
    sources = [fact.source for fact in facts if str(fact.field) in PURCHASE_PROOF_FIELDS]
    return bool(sources) and all(source == FactSource.LLM for source in sources)


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
    purchase_proof_llm_only: bool = False,
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
        "low_commitment_action": action_kind in {"warranty_claim_email", "lessor_request"},
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
    elif all(conditions.values()) and not purchase_proof_llm_only:
        outcome = PolicyOutcome.AUTO_SEND
    elif all(conditions.values()):
        outcome = PolicyOutcome.NEEDS_VALIDATION
        reasons.append("purchase_proof_llm_only")
    else:
        outcome = PolicyOutcome.NEEDS_VALIDATION
        reasons.extend(name for name, passed in conditions.items() if not passed)
        if purchase_proof_llm_only:
            reasons.append("purchase_proof_llm_only")
    return PolicyDecision(outcome=outcome, reasons=reasons, conditions=conditions)
