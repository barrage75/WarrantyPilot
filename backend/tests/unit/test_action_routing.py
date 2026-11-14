import pytest

from app.contracts.enums import Channel
from app.core.orchestrator import _action_kind_for_channel


@pytest.mark.parametrize(
    ("channel", "expected"),
    [
        (Channel.EMAIL_RESELLER, "warranty_claim_email"),
        (Channel.EMAIL_MANUFACTURER_SUPPORT, "warranty_claim_email"),
        (Channel.BROWSER_PORTAL, "portal_claim"),
        (Channel.EMAIL_LESSOR, "lessor_request"),
        (Channel.API, "api_claim"),
        (Channel.MANUAL, "manual_claim"),
    ],
)
def test_action_kind_is_derived_from_channel(channel: Channel, expected: str) -> None:
    assert _action_kind_for_channel(channel) == expected
