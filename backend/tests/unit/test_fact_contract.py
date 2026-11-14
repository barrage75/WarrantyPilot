from uuid import uuid4

from app.contracts.enums import FactField, FactSource
from app.contracts.models import Fact, Provenance


def test_incident_classifier_fact_needs_no_document() -> None:
    incident_id = uuid4()
    fact = Fact(
        incident_id=incident_id,
        field=FactField.INCIDENT_CATEGORY.value,
        value="accidental_damage",
        provenance=Provenance(excerpt="The case was classified from the incident."),
        confidence=0.9,
        source=FactSource.CLASSIFIER,
    )

    assert fact.document_id is None
    assert fact.incident_id == incident_id
    assert fact.provenance.document_id is None
    assert FactField.SECURITY_SUSPICIOUS.value == "security.suspicious"
