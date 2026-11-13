from typing import Any, Protocol

from app.contracts.enums import Channel, RealityBadge
from app.contracts.models import (
    Action,
    ActionResult,
    Case,
    Document,
    Equipment,
    Fact,
    Incident,
    Right,
    Rule,
    Verdict,
)


class DocumentExtractor(Protocol):
    def extract(self, document: Document, content: bytes) -> list[Fact]: ...


class RulesEngine(Protocol):
    def evaluate(
        self,
        equipment: Equipment,
        facts: list[Fact],
        incident: Incident,
        rules: list[Rule],
        rights: list[Right],
    ) -> Verdict: ...


class ActionAdapter(Protocol):
    channel: Channel
    badge: RealityBadge

    async def execute(self, action: Action) -> ActionResult: ...


class FollowUpChecker(Protocol):
    def check(self, case: Case) -> list[dict[str, Any]]: ...
