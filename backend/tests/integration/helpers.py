from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.enums import (
    CaseStatus,
    Channel,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    RealityBadge,
)
from app.contracts.models import Case, Equipment, Incident, Person, Settings
from app.core.journal import append_event
from app.core.settings_store import SETTINGS_ID, write_settings
from app.core.tables import cases, equipment, incidents, people


def create_case(
    factory: sessionmaker[Session],
    *,
    category: str = "headset",
    email: str = "person@example.test",
    allowlist: list[str] | None = None,
    paused: bool = False,
) -> tuple[Case, UUID]:
    person = Person(name="Demo Person", email=email, role="employee")
    device = Equipment(
        brand="Jabra",
        model="Evolve2 65" if category == "headset" else "Latitude",
        serial=uuid4().hex[:7].upper(),
        category=category,
        assigned_to=person.id,
        purchase_price="199.00",
        purchase_date=date(2024, 1, 15),
    )
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=person.id,
        equipment_id=device.id,
        description="Panne fictive pour les tests.",
        reported_via=IncidentReportedVia.CHAT,
    )
    case = Case(
        incident_id=incident.id,
        equipment_id=device.id,
        status=CaseStatus.PREPARED,
        channel=Channel.EMAIL_RESELLER,
        badge=RealityBadge.SIMULATED,
    )
    with factory.begin() as session:
        session.execute(
            insert(people).values(
                id=str(person.id), name=person.name, email=person.email, role=person.role
            )
        )
        session.execute(
            insert(equipment).values(
                id=str(device.id),
                brand=device.brand,
                model=device.model,
                serial=device.serial,
                category=device.category,
                assigned_to=str(device.assigned_to),
                purchase_price=device.purchase_price,
                currency=device.currency,
                in_loan_stock=device.in_loan_stock,
                purchase_date=device.purchase_date,
                delivery_date=device.delivery_date,
                ship_date=device.ship_date,
            )
        )
        session.execute(
            insert(incidents).values(
                id=str(incident.id),
                kind=incident.kind.value,
                reporter_id=str(incident.reporter_id),
                equipment_id=str(device.id),
                description=incident.description,
                reported_via=incident.reported_via.value,
                created_at=incident.created_at.isoformat(),
            )
        )
        session.execute(
            insert(cases).values(
                id=str(case.id),
                incident_id=str(incident.id),
                equipment_id=str(device.id),
                status=case.status.value,
                verdict_id=None,
                policy_id=None,
                channel=case.channel.value,
                badge=case.badge.value,
                created_at=case.created_at.isoformat(),
                updated_at=case.updated_at.isoformat(),
            )
        )
        write_settings(
            session,
            Settings(
                id=SETTINGS_ID,
                auto_send_threshold_eur="0",
                agent_paused=paused,
                email_allowlist=(
                    allowlist if allowlist is not None else ["warranty@revendeur-test.example"]
                ),
            ),
        )
        append_event(
            session,
            EventType.CASE_CREATED,
            case_id=str(case.id),
        )
    return case, person.id
