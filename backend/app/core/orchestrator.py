from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.actions.browser.settings import BrowserSettings
from app.contracts.enums import (
    ActionResultStatus,
    CaseStatus,
    Channel,
    EventType,
    FactField,
    PolicyOutcome,
    PurchaseGuardState,
)
from app.contracts.interfaces import (
    ActionAdapter,
    DocumentExtractor,
    FollowUpChecker,
    RulesEngine,
)
from app.contracts.models import (
    Action,
    ActionResult,
    BrowserPortalClaim,
    BrowserPortalPayload,
    Case,
    Equipment,
    Fact,
    Incident,
    PolicyDecision,
    Provenance,
    Right,
    Rule,
    Settings,
    Verdict,
    utc_now,
)
from app.core.journal import append_event
from app.core.policy import decide
from app.core.security import SecurityViolation, assert_email_allowed, assert_url_allowed
from app.core.settings import AppSettings
from app.core.status import transition
from app.core.tables import (
    action_results,
    actions,
    case_steps,
    cases,
    data_checklists,
    documents,
    equipment_documents,
    equipment_suppliers,
    events,
    incidents,
    people,
    policy_decisions,
    purchase_requests,
    rights,
    suppliers,
    verdicts,
)
from app.core.tables import (
    equipment as equipment_table,
)
from app.core.tables import (
    facts as facts_table,
)
from app.core.tables import (
    settings as settings_table,
)


class Orchestrator:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        extractor: DocumentExtractor,
        rules_engine: RulesEngine,
        action_adapters: Mapping[Channel, ActionAdapter],
        follow_up: FollowUpChecker,
        app_settings: AppSettings,
        rules: list[Rule] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.extractor = extractor
        self.rules_engine = rules_engine
        self.action_adapters = action_adapters
        self.follow_up = follow_up
        self.app_settings = app_settings
        self.rules = rules if rules is not None else []

    async def run(self, case_id: UUID) -> Case:
        with self.session_factory() as session, session.begin():
            case_row = (
                session.execute(select(cases).where(cases.c.id == str(case_id))).mappings().first()
            )
            if case_row is None:
                raise KeyError(f"case not found: {case_id}")
            case = self._case_from_row(session, case_row)
            if case.status in {
                CaseStatus.TRACKED,
                CaseStatus.RESOLVED,
                CaseStatus.MANUAL_TAKEOVER,
            }:
                return case
            prior_success = (
                session.execute(
                    select(action_results)
                    .join(actions, action_results.c.action_id == actions.c.id)
                    .where(
                        actions.c.case_id == str(case_id),
                        action_results.c.status == ActionResultStatus.SUCCESS.value,
                    )
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if prior_success is not None:
                success_result = ActionResult(
                    id=UUID(prior_success["id"]),
                    action_id=UUID(prior_success["action_id"]),
                    status=prior_success["status"],
                    proof=prior_success["proof"],
                    error=prior_success["error"],
                    badge=prior_success["badge"],
                )
                current_status = case.status
                if current_status not in {CaseStatus.SENDING, CaseStatus.SENT}:
                    transition(current_status, CaseStatus.SENDING, attempts=0)
                    self._set_status(session, case, CaseStatus.SENDING)
                    append_event(
                        session,
                        EventType.STATUS_CHANGED,
                        case_id=str(case_id),
                        payload={
                            "from": current_status.value,
                            "to": CaseStatus.SENDING.value,
                            "recovered": True,
                        },
                    )
                sent_status = (
                    CaseStatus.SENT
                    if current_status == CaseStatus.SENT
                    else transition(
                        CaseStatus.SENDING,
                        CaseStatus.SENT,
                        action_result=success_result,
                    )
                )
                if current_status != CaseStatus.SENT:
                    self._set_status(session, case, sent_status)
                    append_event(
                        session,
                        EventType.ACTION_SUCCEEDED,
                        case_id=str(case_id),
                        payload={
                            "action_id": str(success_result.action_id),
                            "proof": success_result.proof,
                            "recovered": True,
                        },
                    )
                    append_event(
                        session,
                        EventType.STATUS_CHANGED,
                        case_id=str(case_id),
                        payload={"from": CaseStatus.SENDING.value, "to": sent_status.value},
                    )
                final_status = self._complete_tracking(session, case, sent_status)
                return case.model_copy(update={"status": final_status})
            if case.status == CaseStatus.SENT:
                raise ValueError("sent cases must have a successful ActionResult")

            validation_exists = (
                session.execute(
                    select(events.c.seq)
                    .where(
                        and_(
                            events.c.case_id == str(case_id),
                            events.c.type == EventType.VALIDATED.value,
                        )
                    )
                    .limit(1)
                ).first()
                is not None
            )

            equipment_model = self._load_equipment(session, case.equipment_id)
            incident_model = self._load_incident(session, case.incident_id)
            if equipment_model is None:
                raise ValueError("orchestration requires an identified equipment")
            case_facts = self._load_facts(session, equipment_model.id, incident_model.id)
            case_rights = self._load_rights(session, equipment_model.id)
            self._record_step(
                session,
                case.id,
                "identify",
                1,
                "done",
                {"equipment_id": str(equipment_model.id)},
            )
            self._record_step(
                session,
                case.id,
                "find_proof",
                2,
                "done",
                {
                    "facts_found": len(case_facts),
                    "documents_checked": len(
                        {fact.document_id for fact in case_facts if fact.document_id}
                    ),
                },
            )
            append_event(
                session,
                EventType.FACT_EXTRACTED,
                case_id=str(case_id),
                payload={
                    "facts": [
                        {"field": fact.field, "source": fact.source.value} for fact in case_facts
                    ],
                    "source": "ingestion registry",
                },
            )

            if case.verdict is None:
                verdict = self.rules_engine.evaluate(
                    equipment_model,
                    case_facts,
                    incident_model,
                    self.rules,
                    case_rights,
                )
                self._record_step(
                    session,
                    case.id,
                    "evaluate",
                    3,
                    "done",
                    {"verdict_id": str(verdict.id)},
                )
                self._store_verdict(session, verdict)
                session.execute(
                    update(cases)
                    .where(cases.c.id == str(case_id))
                    .values(verdict_id=str(verdict.id))
                )
                append_event(
                    session,
                    EventType.VERDICT_COMPUTED,
                    case_id=str(case_id),
                    payload={"verdict": verdict.model_dump(mode="json")},
                )
            else:
                verdict = case.verdict

            checklist_row = session.execute(
                select(data_checklists.c.steps).where(data_checklists.c.case_id == str(case_id))
            ).first()
            requires_checklist = equipment_model.category.casefold() in {
                "computer",
                "laptop",
                "notebook",
            }
            checklist_complete = (
                _checklist_is_complete(checklist_row.steps) if checklist_row is not None else False
            )
            policy_settings = self._load_policy_settings(session)
            suspicious_signal = any(
                fact.field in {FactField.SECURITY_SUSPICIOUS.value, "suspicious"}
                and bool(fact.value)
                for fact in case_facts
            )
            policy = decide(
                case,
                verdict,
                equipment_model,
                _action_kind_for_channel(verdict.channel or case.channel),
                policy_settings,
                checklist_complete=checklist_complete,
                requires_data_checklist=requires_checklist,
                suspicious_signal=suspicious_signal,
            )
            self._record_step(
                session,
                case.id,
                "decide",
                4,
                "done",
                {"outcome": policy.outcome.value},
            )
            self._store_policy(session, policy)
            session.execute(
                update(cases).where(cases.c.id == str(case_id)).values(policy_id=str(policy.id))
            )
            append_event(
                session,
                EventType.POLICY_DECIDED,
                case_id=str(case_id),
                payload={"policy": policy.model_dump(mode="json")},
            )
            case = case.model_copy(update={"verdict": verdict, "policy": policy})

            if policy.outcome == PolicyOutcome.BLOCKED:
                if requires_checklist:
                    self._record_step(
                        session,
                        case.id,
                        "data_checklist",
                        6,
                        "pending",
                        {"complete": checklist_complete},
                    )
                return case
            if policy.outcome == PolicyOutcome.NEEDS_VALIDATION and not validation_exists:
                if case.status != CaseStatus.AWAITING_VALIDATION:
                    new_status = transition(case.status, CaseStatus.AWAITING_VALIDATION)
                    self._set_status(session, case, new_status)
                    self._record_step(
                        session,
                        case.id,
                        "await_validation",
                        5,
                        "pending",
                        {"reasons": policy.reasons},
                    )
                    append_event(
                        session,
                        EventType.VALIDATION_REQUESTED,
                        case_id=str(case_id),
                        payload={"reasons": policy.reasons},
                    )
                return case.model_copy(update={"status": CaseStatus.AWAITING_VALIDATION})

            if case.status == CaseStatus.AWAITING_VALIDATION and not validation_exists:
                return case
            if validation_exists:
                self._record_step(
                    session,
                    case.id,
                    "await_validation",
                    5,
                    "done",
                    {"validated": True},
                )

            paused = self._load_policy_settings(session).agent_paused
            if paused:
                return case
            action, adapter, attempt, prior_running = self._prepare_action(session, case)
            if prior_running:
                return case.model_copy(update={"status": CaseStatus.FAILED})

            if action.requires_data_checklist:
                checklist_row = session.execute(
                    select(data_checklists.c.steps).where(data_checklists.c.case_id == str(case_id))
                ).first()
                if checklist_row is None or not _checklist_is_complete(checklist_row.steps):
                    self._record_step(
                        session,
                        case.id,
                        "data_checklist",
                        6,
                        "pending",
                        {"complete": False},
                    )
                    return case
                self._record_step(
                    session,
                    case.id,
                    "data_checklist",
                    6,
                    "done",
                    {"complete": True},
                )

            sending_status = transition(
                case.status,
                CaseStatus.SENDING,
                attempts=attempt - 1,
            )
            self._set_status(session, case, sending_status)
            self._record_step(
                session,
                case.id,
                "execute",
                7,
                "running",
                {"idempotency_key": action.idempotency_key},
                attempt=attempt,
            )
            existing_action = session.execute(
                select(actions.c.id).where(actions.c.id == str(action.id))
            ).first()
            if existing_action is None:
                session.execute(
                    insert(actions).values(
                        id=str(action.id),
                        case_id=str(case_id),
                        channel=action.channel.value,
                        kind=action.kind,
                        idempotency_key=action.idempotency_key,
                        payload=action.payload,
                        badge=action.badge.value,
                        requires_data_checklist=action.requires_data_checklist,
                    )
                )
            append_event(
                session,
                EventType.ACTION_STARTED,
                case_id=str(case_id),
                payload={"action_id": str(action.id), "idempotency_key": action.idempotency_key},
            )
            append_event(
                session,
                EventType.STATUS_CHANGED,
                case_id=str(case_id),
                payload={"from": case.status.value, "to": CaseStatus.SENDING.value},
            )

        if adapter is None:
            return self._finish_action(
                action,
                case,
                ActionResult(
                    action_id=action.id,
                    status=ActionResultStatus.FAILURE,
                    error="no_adapter_for_channel",
                    badge=action.badge,
                ),
            )

        try:
            self._assert_action_allowed(action)
        except SecurityViolation as error:
            return self._finish_action(
                action,
                case,
                ActionResult(
                    action_id=action.id,
                    status=ActionResultStatus.FAILURE,
                    error=str(error),
                    badge=action.badge,
                ),
            )
        action_result = await adapter.execute(action)
        if action_result.action_id != action.id:
            action_result = ActionResult(
                action_id=action.id,
                status=ActionResultStatus.FAILURE,
                error="adapter returned a result for a different action",
                badge=action.badge,
            )
        return self._finish_action(action, case, action_result)

    def _prepare_action(
        self, session: Session, case: Case
    ) -> tuple[Action, ActionAdapter | None, int, bool]:
        step_rows = session.execute(
            select(case_steps.c.status, case_steps.c.attempt, case_steps.c.output)
            .where(
                and_(
                    case_steps.c.case_id == str(case.id),
                    case_steps.c.step_name == "execute",
                )
            )
            .order_by(case_steps.c.attempt.desc())
        ).all()
        latest_attempt = int(step_rows[0].attempt) if step_rows else 0
        prior_running = bool(
            step_rows
            and (
                step_rows[0].status == "running"
                or (
                    isinstance(step_rows[0].output, dict)
                    and step_rows[0].output.get("unknown_outcome") is True
                )
            )
        )
        attempt = latest_attempt + 1
        incident_row = session.execute(
            select(incidents.c.reporter_id, incidents.c.description).where(
                incidents.c.id == str(case.incident_id)
            )
        ).first()
        person_row = None
        if incident_row is not None:
            person_row = session.execute(
                select(people.c.name, people.c.email).where(people.c.id == incident_row.reporter_id)
            ).first()
        equipment_row = session.execute(
            select(
                equipment_table.c.brand,
                equipment_table.c.model,
                equipment_table.c.serial,
                equipment_table.c.category,
                equipment_table.c.purchase_date,
                equipment_table.c.invoice_number,
            ).where(equipment_table.c.id == str(case.equipment_id))
        ).first()
        category = str(equipment_row.category).casefold() if equipment_row is not None else ""
        channel = (case.verdict.channel if case.verdict is not None else None) or case.channel
        adapter = self.action_adapters.get(channel)
        recipient: str | None = None
        if channel == Channel.EMAIL_RESELLER:
            supplier_row = session.execute(
                select(suppliers.c.email)
                .join(
                    equipment_suppliers,
                    equipment_suppliers.c.supplier_id == suppliers.c.id,
                )
                .where(equipment_suppliers.c.equipment_id == str(case.equipment_id))
            ).first()
            recipient = (
                str(supplier_row.email)
                if supplier_row is not None
                else "warranty@revendeur-test.example"
            )
        elif channel == Channel.EMAIL_MANUFACTURER_SUPPORT:
            brand = str(equipment_row.brand).casefold() if equipment_row is not None else "jabra"
            recipient = f"support@{brand}.example"
        elif channel == Channel.EMAIL_LESSOR:
            recipient = "support@locaprint-test.example"

        if channel == Channel.BROWSER_PORTAL:
            target = str(equipment_row.serial) if equipment_row is not None else "unknown"
        elif recipient is not None:
            target = recipient
        else:
            target = str(case.equipment_id or case.id)
        idempotency_key = f"case:{case.id}:{channel.value}:{target}"
        payload: dict[str, Any] = {
            "case_id": str(case.id),
            "incident_id": str(case.incident_id),
        }
        if recipient is not None:
            payload["to"] = recipient
        if channel.value.startswith("email"):
            document_ids: set[str] = set(
                session.execute(
                    select(equipment_documents.c.document_id).where(
                        equipment_documents.c.equipment_id == str(case.equipment_id)
                    )
                )
                .scalars()
                .all()
            )
            linked_rights = session.execute(
                select(rights.c.rule_id, rights.c.evidence).where(
                    rights.c.equipment_id == str(case.equipment_id)
                )
            ).all()
            contract_reference = ""
            for right in linked_rights:
                contract_reference = contract_reference or str(right.rule_id)
                if isinstance(right.evidence, list):
                    document_ids.update(
                        str(proof["document_id"])
                        for proof in right.evidence
                        if isinstance(proof, dict) and proof.get("document_id")
                    )
            document_rows = (
                session.execute(
                    select(
                        documents.c.id,
                        documents.c.kind,
                        documents.c.filename,
                        documents.c.sha256,
                    )
                    .where(documents.c.id.in_(document_ids))
                    .order_by(documents.c.filename)
                )
                .mappings()
                .all()
                if document_ids
                else []
            )
            if not contract_reference:
                contract_reference = next(
                    (
                        str(document["filename"])
                        for document in document_rows
                        if document["kind"] == "contract"
                    ),
                    "",
                )
            invoice_number = (
                str(equipment_row.invoice_number)
                if equipment_row is not None and equipment_row.invoice_number
                else ""
            )
            if not invoice_number:
                invoice_number_fact = session.execute(
                    select(facts_table.c.value)
                    .where(
                        facts_table.c.equipment_id == str(case.equipment_id),
                        facts_table.c.field == "invoice_number",
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if invoice_number_fact is not None:
                    invoice_number = str(invoice_number_fact)
            payload.update(
                {
                    "language": "fr",
                    "equipment_label": (
                        f"{equipment_row.brand} {equipment_row.model}"
                        if equipment_row is not None
                        else "Équipement"
                    ),
                    "serial_number": str(equipment_row.serial) if equipment_row is not None else "",
                    "purchase_date": (
                        equipment_row.purchase_date.isoformat()
                        if equipment_row is not None and equipment_row.purchase_date
                        else ""
                    ),
                    "invoice_number": invoice_number,
                    "issue_description": (
                        str(incident_row.description) if incident_row is not None else ""
                    ),
                    "company_name": "Appelia SAS",
                    "purchase_country": "France",
                    "contract_reference": contract_reference,
                    "documents": [
                        {
                            "id": str(document["id"]),
                            "kind": str(document["kind"]),
                            "filename": str(document["filename"]),
                            "sha256": str(document["sha256"]),
                        }
                        for document in document_rows
                    ],
                }
            )
        if channel == Channel.BROWSER_PORTAL:
            browser_settings = BrowserSettings.from_env()
            target_url = (
                case.verdict.target_url
                if case.verdict is not None and case.verdict.target_url
                else browser_settings.portal_url
            )
            payload["url"] = target_url
            if equipment_row is not None and incident_row is not None and person_row is not None:
                full_name = str(person_row.name).strip().split(maxsplit=1)
                first_name = full_name[0] if full_name else "Démo"
                last_name = full_name[1] if len(full_name) > 1 else "Appelia"
                person_email = str(person_row.email or "")
                contact_email = (
                    person_email
                    if person_email.rsplit("@", 1)[-1].casefold().endswith(".example")
                    else f"contact-{incident_row.reporter_id}@appelia.example"
                )
                incident_description = str(incident_row.description).strip()
                problem_description = (
                    incident_description
                    if len(incident_description) >= 20
                    else (
                        f"Incident matériel {equipment_row.brand} {equipment_row.model} : "
                        f"{incident_description}"
                    )
                )[:2000]
                category_text = problem_description.casefold()
                problem_category: Literal[
                    "Ne démarre pas",
                    "Écran",
                    "Clavier/pavé tactile",
                    "Batterie/alimentation",
                    "Disque/stockage",
                    "Carte mère/autre matériel",
                    "Logiciel",
                ]
                if "démarr" in category_text or "allum" in category_text:
                    problem_category = "Ne démarre pas"
                elif "écran" in category_text or "affichage" in category_text:
                    problem_category = "Écran"
                elif "clavier" in category_text or "pavé tactile" in category_text:
                    problem_category = "Clavier/pavé tactile"
                elif "batterie" in category_text or "charge" in category_text:
                    problem_category = "Batterie/alimentation"
                elif "disque" in category_text or "stockage" in category_text:
                    problem_category = "Disque/stockage"
                elif "logiciel" in category_text:
                    problem_category = "Logiciel"
                else:
                    problem_category = "Carte mère/autre matériel"
                portal_claim = BrowserPortalClaim(
                    service_tag=str(equipment_row.serial),
                    problem_category=problem_category,
                    problem_description=problem_description,
                    contact_first_name=first_name,
                    contact_last_name=last_name,
                    contact_email=contact_email,
                    contact_phone="0102030405",
                    company_name="Appelia SAS",
                    address_line1="1 rue de l'Exemple",
                    postal_code="75000",
                    city="Paris",
                    availability_date=self.app_settings.demo_today + timedelta(days=1),
                    availability_slot="Matin 8h–12h",
                )
                payload.update(
                    BrowserPortalPayload(
                        url=target_url,
                        portal_claim=portal_claim,
                    ).model_dump(mode="json")
                )
        action = Action(
            case_id=case.id,
            channel=channel,
            kind=_action_kind_for_channel(channel),
            idempotency_key=idempotency_key,
            payload=payload,
            badge=adapter.badge if adapter is not None else case.badge,
            requires_data_checklist=category in {"computer", "laptop", "notebook"},
        )
        prior_action = (
            session.execute(select(actions).where(actions.c.idempotency_key == idempotency_key))
            .mappings()
            .first()
        )
        if prior_action is not None:
            action = Action(
                id=UUID(prior_action["id"]),
                case_id=UUID(prior_action["case_id"]),
                channel=prior_action["channel"],
                kind=prior_action["kind"],
                idempotency_key=prior_action["idempotency_key"],
                payload=prior_action["payload"],
                badge=prior_action["badge"],
                requires_data_checklist=prior_action["requires_data_checklist"],
            )
        return action, adapter, attempt, prior_running

    def _assert_action_allowed(self, action: Action) -> None:
        active_settings = self._settings_for_action()
        if active_settings.agent_paused:
            raise SecurityViolation("agent is paused")
        if action.channel.value.startswith("email"):
            recipient = action.payload.get("to")
            if recipient is None:
                raise SecurityViolation("email action has no recipient")
            assert_email_allowed(str(recipient), active_settings)
        target_url = action.payload.get("url")
        if action.channel == Channel.BROWSER_PORTAL and not target_url:
            raise SecurityViolation("browser action has no target URL")
        if target_url is not None:
            assert_url_allowed(str(target_url), active_settings)

    def _settings_for_action(self) -> Settings:
        with self.session_factory() as session:
            return self._load_policy_settings(session)

    def _finish_action(self, action: Action, case: Case, result: ActionResult) -> Case:
        with self.session_factory() as session, session.begin():
            session.execute(
                insert(action_results).values(
                    id=str(result.id),
                    action_id=str(result.action_id),
                    status=result.status.value,
                    proof=result.proof,
                    error=result.error,
                    badge=result.badge.value,
                )
            )
            latest_step = session.execute(
                select(case_steps.c.id, case_steps.c.attempt)
                .where(
                    and_(
                        case_steps.c.case_id == str(case.id),
                        case_steps.c.step_name == "execute",
                    )
                )
                .order_by(case_steps.c.attempt.desc())
                .limit(1)
            ).first()
            if latest_step is not None:
                session.execute(
                    update(case_steps)
                    .where(case_steps.c.id == latest_step.id)
                    .values(
                        status="done" if result.status == ActionResultStatus.SUCCESS else "failed",
                        output=result.model_dump(mode="json"),
                        updated_at=datetime.now(UTC).isoformat(),
                    )
                )
            if action.channel == Channel.MANUAL:
                takeover = transition(CaseStatus.SENDING, CaseStatus.MANUAL_TAKEOVER)
                self._set_status(session, case, takeover)
                append_event(
                    session,
                    EventType.STATUS_CHANGED,
                    case_id=str(case.id),
                    payload={
                        "from": CaseStatus.SENDING.value,
                        "to": takeover.value,
                        "reason": "prise en main humaine requise",
                    },
                )
                return case.model_copy(update={"status": takeover})
            if result.status == ActionResultStatus.SUCCESS:
                current = CaseStatus.SENDING
                sent = transition(current, CaseStatus.SENT, action_result=result)
                self._set_status(session, case, sent)
                append_event(
                    session,
                    EventType.ACTION_SUCCEEDED,
                    case_id=str(case.id),
                    payload={"action_id": str(action.id), "proof": result.proof},
                )
                append_event(
                    session,
                    EventType.STATUS_CHANGED,
                    case_id=str(case.id),
                    payload={"from": current.value, "to": sent.value},
                )
                final_status = self._complete_tracking(session, case, sent)
                return case.model_copy(update={"status": final_status})

            failed = transition(CaseStatus.SENDING, CaseStatus.FAILED)
            self._set_status(session, case, failed)
            append_event(
                session,
                EventType.ACTION_FAILED,
                case_id=str(case.id),
                payload={"action_id": str(action.id), "error": result.error},
            )
            append_event(
                session,
                EventType.STATUS_CHANGED,
                case_id=str(case.id),
                payload={"from": CaseStatus.SENDING.value, "to": failed.value},
            )
            if latest_step is not None and int(latest_step.attempt) >= 2:
                takeover = transition(failed, CaseStatus.MANUAL_TAKEOVER)
                self._set_status(session, case, takeover)
                append_event(
                    session,
                    EventType.STATUS_CHANGED,
                    case_id=str(case.id),
                    payload={
                        "from": failed.value,
                        "to": takeover.value,
                        "reason": "retry_limit_reached",
                    },
                )
                return case.model_copy(update={"status": takeover})
            return case.model_copy(update={"status": failed})

    def _complete_tracking(
        self,
        session: Session,
        case: Case,
        sent_status: CaseStatus,
    ) -> CaseStatus:
        tracked_status = transition(sent_status, CaseStatus.TRACKED)
        self._set_status(session, case, tracked_status)
        self._record_step(
            session,
            case.id,
            "track",
            8,
            "done",
            {"status": tracked_status.value},
        )
        append_event(
            session,
            EventType.STATUS_CHANGED,
            case_id=str(case.id),
            payload={"from": sent_status.value, "to": tracked_status.value},
        )
        follow_up_payloads = self.follow_up.check(
            case.model_copy(update={"status": tracked_status})
        )
        for payload in follow_up_payloads:
            append_event(
                session,
                EventType.FOLLOWUP_RECEIVED,
                case_id=str(case.id),
                payload=payload,
            )
        if any(payload.get("status") == "resolved" for payload in follow_up_payloads):
            resolved_status = transition(tracked_status, CaseStatus.RESOLVED)
            self._set_status(session, case, resolved_status)
            linked_purchases = (
                session.execute(
                    select(purchase_requests).where(purchase_requests.c.case_id == str(case.id))
                )
                .mappings()
                .all()
            )
            for purchase in linked_purchases:
                values: dict[str, Any] = {
                    "resolved_at": utc_now().isoformat(),
                }
                if purchase["cancelled_at"]:
                    values["state"] = PurchaseGuardState.SAVING_REALIZED.value
                session.execute(
                    update(purchase_requests)
                    .where(purchase_requests.c.id == purchase["id"])
                    .values(**values)
                )
                if purchase["cancelled_at"]:
                    append_event(
                        session,
                        EventType.PURCHASE_GUARD_SAVING_REALIZED,
                        actor="agent",
                        case_id=str(case.id),
                        payload={
                            "purchase_request_id": purchase["id"],
                            "amount_eur": float(purchase["amount"]),
                        },
                    )
            append_event(
                session,
                EventType.STATUS_CHANGED,
                case_id=str(case.id),
                payload={"from": tracked_status.value, "to": resolved_status.value},
            )
            return resolved_status
        return tracked_status

    def _record_step(
        self,
        session: Session,
        case_id: UUID,
        step_name: str,
        order: int,
        status: str,
        output: dict[str, Any],
        attempt: int = 1,
    ) -> None:
        existing = session.execute(
            select(case_steps.c.id).where(
                and_(case_steps.c.case_id == str(case_id), case_steps.c.step_name == step_name)
            )
        ).first()
        values = {
            "status": status,
            "order": order,
            "attempt": attempt,
            "output": output,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if existing is None:
            session.execute(
                insert(case_steps).values(
                    id=str(uuid4()),
                    case_id=str(case_id),
                    step_name=step_name,
                    **values,
                )
            )
        else:
            session.execute(
                update(case_steps).where(case_steps.c.id == existing.id).values(**values)
            )

    def _case_from_row(self, session: Session, row: Any) -> Case:
        verdict = None
        if row["verdict_id"]:
            verdict_row = (
                session.execute(select(verdicts).where(verdicts.c.id == row["verdict_id"]))
                .mappings()
                .first()
            )
            if verdict_row is not None:
                verdict = Verdict(
                    id=UUID(verdict_row["id"]),
                    value=verdict_row["value"],
                    rule_id=verdict_row["rule_id"],
                    rule_version=verdict_row["rule_version"],
                    checks=verdict_row["checks"],
                    evidence=verdict_row["evidence"],
                    channel=verdict_row["channel"],
                    target_url=verdict_row["target_url"],
                    missing=verdict_row["missing"],
                    possible_exclusions=verdict_row["possible_exclusions"],
                    explanation_fr=verdict_row["explanation_fr"],
                    explanation_en=verdict_row["explanation_en"],
                )
        policy = None
        if row["policy_id"]:
            policy_row = (
                session.execute(
                    select(policy_decisions).where(policy_decisions.c.id == row["policy_id"])
                )
                .mappings()
                .first()
            )
            if policy_row is not None:
                policy = PolicyDecision(
                    id=UUID(policy_row["id"]),
                    outcome=policy_row["outcome"],
                    reasons=policy_row["reasons"],
                    conditions=policy_row["conditions"],
                )
        return Case(
            id=UUID(row["id"]),
            incident_id=UUID(row["incident_id"]),
            equipment_id=UUID(row["equipment_id"]) if row["equipment_id"] else None,
            status=row["status"],
            verdict=verdict,
            policy=policy,
            channel=row["channel"],
            badge=row["badge"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _load_equipment(self, session: Session, equipment_id: UUID | None) -> Equipment | None:
        if equipment_id is None:
            return None
        row = (
            session.execute(
                select(equipment_table).where(equipment_table.c.id == str(equipment_id))
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return Equipment(
            id=UUID(row["id"]),
            brand=row["brand"],
            model=row["model"],
            serial=row["serial"],
            category=row["category"],
            assigned_to=UUID(row["assigned_to"]) if row["assigned_to"] else None,
            purchase_price=Decimal(row["purchase_price"])
            if row["purchase_price"] is not None
            else None,
            currency=row["currency"],
            in_loan_stock=row["in_loan_stock"],
            purchase_date=row["purchase_date"],
            delivery_date=row["delivery_date"],
            ship_date=row["ship_date"],
        )

    def _load_incident(self, session: Session, incident_id: UUID) -> Incident:
        row = (
            session.execute(select(incidents).where(incidents.c.id == str(incident_id)))
            .mappings()
            .one()
        )
        return Incident(
            id=UUID(row["id"]),
            kind=row["kind"],
            reporter_id=UUID(row["reporter_id"]),
            equipment_id=UUID(row["equipment_id"]) if row["equipment_id"] else None,
            description=row["description"],
            reported_via=row["reported_via"],
            created_at=row["created_at"],
        )

    def _load_facts(
        self,
        session: Session,
        equipment_id: UUID,
        incident_id: UUID,
    ) -> list[Fact]:
        rows = (
            session.execute(
                select(facts_table).where(
                    or_(
                        facts_table.c.equipment_id == str(equipment_id),
                        facts_table.c.incident_id == str(incident_id),
                    )
                )
            )
            .mappings()
            .all()
        )
        return [
            Fact(
                id=UUID(row["id"]),
                equipment_id=UUID(row["equipment_id"]) if row["equipment_id"] else None,
                document_id=UUID(row["document_id"]) if row["document_id"] else None,
                incident_id=UUID(row["incident_id"]) if row["incident_id"] else None,
                field=row["field"],
                value=row["value"],
                provenance=Provenance.model_validate(row["provenance"]),
                confidence=float(row["confidence"]),
                source=row["source"],
            )
            for row in rows
        ]

    def _load_rights(self, session: Session, equipment_id: UUID) -> list[Right]:
        rows = (
            session.execute(select(rights).where(rights.c.equipment_id == str(equipment_id)))
            .mappings()
            .all()
        )
        return [
            Right(
                id=UUID(row["id"]),
                equipment_id=UUID(row["equipment_id"]),
                right_type=row["right_type"],
                rule_id=row["rule_id"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                evidence=[Provenance.model_validate(item) for item in row["evidence"]],
            )
            for row in rows
        ]

    def _load_policy_settings(self, session: Session) -> Settings:
        row = session.execute(select(settings_table).limit(1)).mappings().first()
        if row is None:
            return Settings(auto_send_threshold_eur=Decimal("0"))
        return Settings(
            id=UUID(row["id"]),
            auto_send_threshold_eur=Decimal(row["auto_send_threshold_eur"]),
            agent_paused=row["agent_paused"],
            feature_flags=row["feature_flags"],
            email_allowlist=row["email_allowlist"],
            browser_allowed_origins=row["browser_allowed_origins"],
        )

    def _store_verdict(self, session: Session, verdict: Verdict) -> None:
        session.execute(
            insert(verdicts).values(
                id=str(verdict.id),
                value=verdict.value.value,
                rule_id=verdict.rule_id,
                rule_version=verdict.rule_version,
                checks=[check.model_dump(mode="json") for check in verdict.checks],
                evidence=[item.model_dump(mode="json") for item in verdict.evidence],
                missing=verdict.missing,
                possible_exclusions=verdict.possible_exclusions,
                explanation_fr=verdict.explanation_fr,
                explanation_en=verdict.explanation_en,
                channel=verdict.channel.value if verdict.channel is not None else None,
                target_url=verdict.target_url,
            )
        )

    def _store_policy(self, session: Session, policy: PolicyDecision) -> None:
        session.execute(
            insert(policy_decisions).values(
                id=str(policy.id),
                outcome=policy.outcome.value,
                reasons=policy.reasons,
                conditions=policy.conditions,
            )
        )

    def _set_status(self, session: Session, case: Case, status: CaseStatus) -> None:
        session.execute(
            update(cases)
            .where(cases.c.id == str(case.id))
            .values(status=status.value, updated_at=datetime.now(UTC).isoformat())
        )


def _checklist_is_complete(value: Any) -> bool:
    try:
        from app.contracts.models import DataChecklist

        return DataChecklist.model_validate(
            {"case_id": "00000000-0000-0000-0000-000000000000", "steps": value}
        ).complete()
    except (TypeError, ValueError):
        return False


def _action_kind_for_channel(channel: Channel) -> str:
    if channel == Channel.EMAIL_LESSOR:
        return "lessor_request"
    if channel == Channel.BROWSER_PORTAL:
        return "portal_claim"
    if channel == Channel.API:
        return "api_claim"
    if channel == Channel.MANUAL:
        return "manual_claim"
    if channel.value.startswith("email_"):
        return "warranty_claim_email"
    raise ValueError(f"unsupported action channel: {channel.value}")
