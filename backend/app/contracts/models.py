from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.enums import (
    ActionResultStatus,
    CaseStatus,
    Channel,
    ChecklistStepName,
    ContactDelayStart,
    DocumentKind,
    DocumentSource,
    EventType,
    FactSource,
    IncidentKind,
    IncidentReportedVia,
    PolicyOutcome,
    PurchaseGuardState,
    RealityBadge,
    RightType,
    RuleStartEvent,
    VerdictValue,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must use UTC")
    return value.astimezone(UTC)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Person(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    email: str | None = None
    role: str | None = None


class Equipment(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    brand: str
    model: str
    serial: str
    category: str
    assigned_to: UUID | None = None
    purchase_price: Decimal | None = None
    currency: str = "EUR"
    in_loan_stock: bool = False
    purchase_date: date | None = None
    delivery_date: date | None = None
    ship_date: date | None = None


class Document(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    kind: DocumentKind
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mime: str
    source: DocumentSource
    untrusted: bool = True

    @field_validator("untrusted", mode="before")
    @classmethod
    def always_untrusted(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("documents must always be treated as untrusted")
        return True


class Provenance(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID | None = None
    page: int | None = Field(default=None, ge=1)
    excerpt: str
    char_span: tuple[int, int] | None = None

    @field_validator("char_span")
    @classmethod
    def valid_char_span(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is not None and (value[0] < 0 or value[1] < value[0]):
            raise ValueError("char_span must be a non-negative increasing range")
        return value


class Fact(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    equipment_id: UUID | None = None
    document_id: UUID | None = None
    incident_id: UUID | None = None
    field: str
    value: Any
    provenance: Provenance
    confidence: float = Field(ge=0, le=1)
    source: FactSource


class RuleAppliesTo(ContractModel):
    brand: str
    model_glob: str
    condition: Literal["new", "refurbished"] = "new"


class Rule(ContractModel):
    id: str
    version: str
    source_url: str
    consulted_on: date
    applies_to: RuleAppliesTo
    right_type: RightType
    duration_months: int = Field(ge=0)
    duration_days: int | None = Field(default=None, ge=1)
    start_event: RuleStartEvent
    proof_required: list[str]
    exclusions: list[str]
    contact_delay_days: int | None = Field(default=None, ge=0)
    contact_delay_start: ContactDelayStart = ContactDelayStart.UNSPECIFIED
    channel: Channel
    requires_certificate: bool


class Right(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    equipment_id: UUID
    right_type: RightType
    rule_id: str
    start_date: date
    end_date: date
    evidence: list[Provenance] = Field(default_factory=list)


class Incident(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    kind: IncidentKind
    reporter_id: UUID
    equipment_id: UUID | None = None
    description: str
    reported_via: IncidentReportedVia
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def incident_timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class RuleCheck(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    passed: bool | None
    detail: str


class Verdict(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    value: VerdictValue
    channel: Channel | None = None
    target_url: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    checks: list[RuleCheck] = Field(default_factory=list)
    evidence: list[Provenance] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    possible_exclusions: list[str] = Field(default_factory=list)
    explanation_fr: str
    explanation_en: str


POLICY_CONDITION_NAMES = frozenset(
    {
        "under_threshold",
        "verdict_covered",
        "equipment_unambiguous",
        "no_possible_exclusion",
        "no_suspicious_signal",
        "low_commitment_action",
    }
)


class PolicyDecision(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    outcome: PolicyOutcome
    reasons: list[str] = Field(default_factory=list)
    conditions: dict[str, bool]

    @field_validator("conditions")
    @classmethod
    def require_all_policy_conditions(cls, value: dict[str, bool]) -> dict[str, bool]:
        if set(value) != POLICY_CONDITION_NAMES:
            missing = sorted(POLICY_CONDITION_NAMES - set(value))
            extra = sorted(set(value) - POLICY_CONDITION_NAMES)
            raise ValueError(f"conditions mismatch; missing={missing}, extra={extra}")
        return value


class Action(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    channel: Channel
    kind: str
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    badge: RealityBadge
    requires_data_checklist: bool = False


class ActionResult(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    status: ActionResultStatus
    proof: str | None = None
    error: str | None = None
    badge: RealityBadge

    @model_validator(mode="after")
    def successful_action_requires_proof(self) -> ActionResult:
        if self.status == ActionResultStatus.SUCCESS and not (self.proof and self.proof.strip()):
            raise ValueError("successful action results require a non-empty proof")
        return self


class ChecklistStep(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    done: bool = False
    by_person_id: UUID | None = None
    at: datetime | None = None

    @field_validator("at")
    @classmethod
    def checklist_timestamp_is_utc(cls, value: datetime | None) -> datetime | None:
        return require_utc(value) if value is not None else None

    @model_validator(mode="after")
    def completed_step_has_timestamp(self) -> ChecklistStep:
        if self.done and self.at is None:
            raise ValueError("a completed checklist step requires a timestamp")
        return self


class DataChecklist(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    steps: dict[ChecklistStepName, ChecklistStep] = Field(
        default_factory=lambda: {name: ChecklistStep() for name in ChecklistStepName}
    )

    @field_validator("steps")
    @classmethod
    def require_seven_steps(
        cls, value: dict[ChecklistStepName, ChecklistStep]
    ) -> dict[ChecklistStepName, ChecklistStep]:
        if set(value) != set(ChecklistStepName):
            raise ValueError("the data checklist must contain exactly the seven defined steps")
        return value

    def complete(self) -> bool:
        human_steps = {
            ChecklistStepName.BACKUP_VERIFIED,
            ChecklistStepName.DISK_ENCRYPTION,
            ChecklistStepName.DISK_HANDLING,
            ChecklistStepName.ACCOUNTS_AND_MDM,
            ChecklistStepName.RETURN_INSPECTION,
        }
        return all(
            step.done
            and step.at is not None
            and (name not in human_steps or step.by_person_id is not None)
            for name, step in self.steps.items()
        )


class PurchaseRequest(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    requester_id: UUID
    equipment_id: UUID
    item_description: str
    amount: Decimal = Field(ge=0)
    state: PurchaseGuardState = PurchaseGuardState.RECOMMENDATION
    decision_reason: str | None = None


class Case(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    equipment_id: UUID | None = None
    status: CaseStatus = CaseStatus.PREPARED
    verdict: Verdict | None = None
    policy: PolicyDecision | None = None
    channel: Channel = Channel.MANUAL
    badge: RealityBadge = RealityBadge.SIMULATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", "updated_at")
    @classmethod
    def case_timestamps_are_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class Event(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    seq: int = Field(ge=1)
    at: datetime = Field(default_factory=utc_now)
    actor: str
    type: EventType
    case_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = "0" * 64
    hash: str = ""

    @field_validator("at")
    @classmethod
    def event_timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @field_validator("actor")
    @classmethod
    def valid_actor(cls, value: str) -> str:
        if value not in {"agent", "system"} and not value.startswith("human:"):
            raise ValueError("actor must be agent, system, or human:<id>")
        if value.startswith("human:") and not value.removeprefix("human:"):
            raise ValueError("human actors require an identifier")
        return value


class Settings(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    auto_send_threshold_eur: Decimal = Decimal("0")
    agent_paused: bool = False
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    email_allowlist: list[str] = Field(default_factory=list)
    browser_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:*", "http://127.0.0.1:*"]
    )
