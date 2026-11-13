from app.contracts.enums import (
    ActionResultStatus,
    Channel,
    FactSource,
    RealityBadge,
    VerdictValue,
)
from app.contracts.models import (
    Action,
    ActionResult,
    Case,
    Document,
    Fact,
    Provenance,
    RuleCheck,
    Verdict,
)


class FakeExtractor:
    def extract(self, document: Document, content: bytes) -> list[Fact]:
        return [
            Fact(
                equipment_id=None,
                document_id=document.id,
                field="document_size",
                value=len(content),
                provenance=Provenance(
                    document_id=document.id,
                    page=1,
                    excerpt=f"{document.filename} ({len(content)} bytes)",
                    char_span=(0, len(content)),
                ),
                confidence=1,
                source=FactSource.STRUCTURED,
            )
        ]


class FakeRulesEngine:
    def __init__(self, verdict: Verdict | None = None) -> None:
        self.verdict = verdict
        self.calls = 0

    def evaluate(self, equipment, facts, incident, rules, rights) -> Verdict:
        self.calls += 1
        if self.verdict is not None:
            return self.verdict.model_copy(deep=True)
        return Verdict(
            value=VerdictValue.COVERED,
            rule_id="fake-standard-warranty",
            rule_version="1",
            checks=[RuleCheck(name="fake_rule_match", passed=True, detail="Fake rule matched.")],
            explanation_fr="Éligibilité fictive pour les tests.",
            explanation_en="Fictional eligibility for tests.",
        )


class FakeActionAdapter:
    channel = Channel.EMAIL_RESELLER
    badge = RealityBadge.SIMULATED

    def __init__(self, result: str = "success") -> None:
        if result not in {"success", "failure", "crash"}:
            raise ValueError(f"unsupported fake action result: {result}")
        self.result = result
        self.calls: list[str] = []

    async def execute(self, action: Action) -> ActionResult:
        self.calls.append(action.idempotency_key)
        if self.result == "crash":
            raise RuntimeError("simulated adapter process crash")
        if self.result == "failure":
            return ActionResult(
                action_id=action.id,
                status=ActionResultStatus.FAILURE,
                error="simulated delivery failure",
                badge=action.badge,
            )
        return ActionResult(
            action_id=action.id,
            status=ActionResultStatus.SUCCESS,
            proof=f"fake-message-{len(self.calls)}",
            badge=action.badge,
        )


class FailingActionAdapter(FakeActionAdapter):
    def __init__(self) -> None:
        super().__init__(result="failure")


class CrashingActionAdapter(FakeActionAdapter):
    def __init__(self) -> None:
        super().__init__(result="crash")


class FakeFollowUp:
    def __init__(self, events: list[dict] | None = None) -> None:
        self.events = events if events is not None else [{"status": "resolved"}]

    def check(self, case: Case) -> list[dict]:
        return [event.copy() for event in self.events]
