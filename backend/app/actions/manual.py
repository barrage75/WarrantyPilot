from app.contracts.enums import ActionResultStatus, Channel, RealityBadge
from app.contracts.models import Action, ActionResult


class ManualAdapter:
    channel = Channel.MANUAL
    badge = RealityBadge.REPRODUCTION

    async def execute(self, action: Action) -> ActionResult:
        return ActionResult(
            action_id=action.id,
            status=ActionResultStatus.SUCCESS,
            proof="prise en main humaine requise",
            badge=self.badge,
        )
