from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase

from app.contracts.enums import CaseStatus, EventType

_case_statuses = ", ".join(f"'{status.value}'" for status in CaseStatus)
_event_types = ", ".join(f"'{event_type.value}'" for event_type in EventType)


class Base(DeclarativeBase):
    metadata = MetaData()


people = Table(
    "people",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("name", Text, nullable=False),
    Column("email", Text),
    Column("role", Text),
)

equipment = Table(
    "equipment",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("brand", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("serial", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("assigned_to", String(36), ForeignKey("people.id")),
    Column("purchase_price", Numeric(12, 2)),
    Column("currency", String(3), nullable=False),
    Column("in_loan_stock", Boolean, nullable=False),
    Column("purchase_date", Date),
    Column("delivery_date", Date),
    Column("ship_date", Date),
)

documents = Table(
    "documents",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("kind", String(64), nullable=False),
    Column("filename", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("mime", Text, nullable=False),
    Column("source", String(64), nullable=False),
    Column("untrusted", Boolean, nullable=False, default=True),
    CheckConstraint("untrusted = 1", name="ck_documents_untrusted"),
)

facts = Table(
    "facts",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("equipment_id", String(36), ForeignKey("equipment.id")),
    Column("document_id", String(36), ForeignKey("documents.id"), nullable=False),
    Column("field", Text, nullable=False),
    Column("value", JSON, nullable=False),
    Column("provenance", JSON, nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False),
    Column("source", String(64), nullable=False),
)

rules = Table(
    "rules",
    Base.metadata,
    Column("id", String(255), primary_key=True),
    Column("version", String(64), primary_key=True),
    Column("source_url", Text, nullable=False),
    Column("consulted_on", Date, nullable=False),
    Column("applies_to", JSON, nullable=False),
    Column("right_type", String(64), nullable=False),
    Column("duration_months", Integer, nullable=False),
    Column("start_event", String(64), nullable=False),
    Column("proof_required", JSON, nullable=False),
    Column("exclusions", JSON, nullable=False),
    Column("contact_delay_days", Integer),
    Column("contact_delay_start", String(32), nullable=False),
    Column("channel", String(64), nullable=False),
    Column("requires_certificate", Boolean, nullable=False),
)

rights = Table(
    "rights",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("equipment_id", String(36), ForeignKey("equipment.id"), nullable=False),
    Column("right_type", String(64), nullable=False),
    Column("rule_id", String(255), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("evidence", JSON, nullable=False),
)

incidents = Table(
    "incidents",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("kind", String(64), nullable=False),
    Column("reporter_id", String(36), ForeignKey("people.id"), nullable=False),
    Column("equipment_id", String(36), ForeignKey("equipment.id")),
    Column("description", Text, nullable=False),
    Column("reported_via", String(64), nullable=False),
    Column("created_at", String(40), nullable=False),
)

verdicts = Table(
    "verdicts",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("value", String(64), nullable=False),
    Column("channel", String(64)),
    Column("target_url", Text),
    Column("rule_id", String(255)),
    Column("rule_version", String(64)),
    Column("checks", JSON, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("missing", JSON, nullable=False),
    Column("possible_exclusions", JSON, nullable=False),
    Column("explanation_fr", Text, nullable=False),
    Column("explanation_en", Text, nullable=False),
)

policy_decisions = Table(
    "policy_decisions",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("outcome", String(64), nullable=False),
    Column("reasons", JSON, nullable=False),
    Column("conditions", JSON, nullable=False),
)

cases = Table(
    "cases",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("incident_id", String(36), ForeignKey("incidents.id"), nullable=False),
    Column("equipment_id", String(36), ForeignKey("equipment.id")),
    Column("status", String(64), nullable=False),
    Column("verdict_id", String(36), ForeignKey("verdicts.id")),
    Column("policy_id", String(36), ForeignKey("policy_decisions.id")),
    Column("channel", String(64), nullable=False),
    Column("badge", String(64), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    CheckConstraint(f"status IN ({_case_statuses})", name="ck_cases_status"),
)

actions = Table(
    "actions",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("case_id", String(36), ForeignKey("cases.id"), nullable=False),
    Column("channel", String(64), nullable=False),
    Column("kind", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("badge", String(64), nullable=False),
    Column("requires_data_checklist", Boolean, nullable=False),
    UniqueConstraint("idempotency_key", name="uq_actions_idempotency_key"),
)

action_results = Table(
    "action_results",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("action_id", String(36), ForeignKey("actions.id"), nullable=False),
    Column("status", String(64), nullable=False),
    Column("proof", Text),
    Column("error", Text),
    Column("badge", String(64), nullable=False),
    CheckConstraint(
        "status IN ('success', 'failure') AND "
        "(status != 'success' OR (proof IS NOT NULL AND length(trim(proof)) > 0))",
        name="ck_action_results_success_proof",
    ),
)

data_checklists = Table(
    "data_checklists",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("case_id", String(36), ForeignKey("cases.id"), nullable=False, unique=True),
    Column("steps", JSON, nullable=False),
)

purchase_requests = Table(
    "purchase_requests",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("requester_id", String(36), ForeignKey("people.id"), nullable=False),
    Column("equipment_id", String(36), ForeignKey("equipment.id"), nullable=False),
    Column("item_description", Text, nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("state", String(64), nullable=False),
    Column("decision_reason", Text),
)

settings = Table(
    "settings",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("auto_send_threshold_eur", Numeric(12, 2), nullable=False),
    Column("agent_paused", Boolean, nullable=False),
    Column("feature_flags", JSON, nullable=False),
    Column("email_allowlist", JSON, nullable=False),
    Column("browser_allowed_origins", JSON, nullable=False),
)

events = Table(
    "events",
    Base.metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("id", String(36), nullable=False, unique=True),
    Column("at", String(40), nullable=False),
    Column("actor", Text, nullable=False),
    Column("type", String(64), nullable=False),
    Column("case_id", String(36), ForeignKey("cases.id")),
    Column("payload", JSON, nullable=False),
    Column("prev_hash", String(64), nullable=False),
    Column("hash", String(64), nullable=False),
    CheckConstraint(f"type IN ({_event_types})", name="ck_events_type"),
)

case_steps = Table(
    "case_steps",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("case_id", String(36), ForeignKey("cases.id"), nullable=False),
    Column("step_name", String(64), nullable=False),
    Column("order", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("attempt", Integer, nullable=False, default=0),
    Column("output", JSON),
    Column("updated_at", String(40), nullable=False),
    CheckConstraint(
        "status IN ('pending', 'running', 'done', 'failed')",
        name="ck_case_steps_status",
    ),
    UniqueConstraint("case_id", "step_name", name="uq_case_steps_case_step"),
)
