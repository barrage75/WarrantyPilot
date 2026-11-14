from pathlib import Path
from uuid import uuid4

from app.actions.email import EmailReplyChecker
from app.contracts.models import Case
from tests.contract.helpers import assert_action_adapter_contract, assert_follow_up_contract
from tests.unit.actions.email.test_email import Transport, adapter


async def test_contract(tmp_path: Path) -> None:
    transport = Transport()
    instance = adapter(transport, tmp_path / "ledger")
    await assert_action_adapter_contract(instance)
    assert_follow_up_contract(
        EmailReplyChecker(transport, instance.ledger), Case(incident_id=uuid4())
    )
