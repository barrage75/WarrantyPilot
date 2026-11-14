from app.contracts.enums import ChecklistStepName
from app.contracts.models import DataChecklist
from app.core.auth import AccessRole, Operator

STEP_ORDER: tuple[ChecklistStepName, ...] = tuple(ChecklistStepName)
REQUIRED_ROLE: dict[ChecklistStepName, AccessRole] = {
    ChecklistStepName.REPAIR_TYPE: "operator",
    ChecklistStepName.BACKUP_VERIFIED: "operator",
    ChecklistStepName.DISK_ENCRYPTION: "admin",
    ChecklistStepName.DISK_HANDLING: "admin",
    ChecklistStepName.ACCOUNTS_AND_MDM: "admin",
    ChecklistStepName.SHIPPING_LABEL: "admin",
    ChecklistStepName.RETURN_INSPECTION: "operator",
}


class ChecklistRuleError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def ensure_step_allowed(
    checklist: DataChecklist,
    step_name: ChecklistStepName,
    operator: Operator,
) -> bool:
    """Return False when the step is already done (idempotent no-op)."""
    if REQUIRED_ROLE[step_name] == "admin" and not operator.is_admin:
        raise ChecklistRuleError(403, f"Step {step_name.value} requires the admin role")
    if checklist.steps[step_name].done:
        return False
    for previous in STEP_ORDER[: STEP_ORDER.index(step_name)]:
        if not checklist.steps[previous].done:
            raise ChecklistRuleError(409, f"Step {previous.value} must be completed first")
    return True
