import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.api.main import create_app
from app.contracts.enums import FactField, FactSource, VerdictValue
from app.core.orchestrator import Orchestrator
from app.core.tables import facts, policy_decisions
from tests.integration.helpers import create_case


def test_orchestrator_uses_ingested_suspicious_fact(
    db_engine, session_factory, app_settings
) -> None:
    case, _ = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            insert(facts).values(
                id=str(uuid4()),
                equipment_id=str(case.equipment_id),
                document_id=None,
                incident_id=str(case.incident_id),
                field=FactField.SECURITY_SUSPICIOUS.value,
                value=[{"kind": "injection"}],
                provenance={"excerpt": "suspicious instruction"},
                confidence=1,
                source=FactSource.STRUCTURED.value,
            )
        )

    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application):
        services = application.state.services
        orchestrator = Orchestrator(
            session_factory=session_factory,
            extractor=services["extractor"],
            rules_engine=services["rules_engine"],
            action_adapters=services["action_adapters"],
            follow_up=services["follow_up"],
            app_settings=app_settings,
            rules=services["rules"],
        )
        result = asyncio.run(orchestrator.run(case.id))
    with session_factory() as session:
        stored_policy = session.execute(select(policy_decisions)).mappings().one()

    assert result.verdict is not None
    assert result.verdict.value == VerdictValue.TO_VERIFY
    assert stored_policy["conditions"]["no_suspicious_signal"] is False
