"""``BrowserPortalAdapter`` honours the ``ActionAdapter`` contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.actions.browser import BrowserPortalAdapter, BrowserSettings, PortalErrorCode
from app.actions.browser.settings import BrowserEngine
from app.contracts.enums import ActionResultStatus, Channel, RealityBadge
from app.contracts.interfaces import ActionAdapter
from app.contracts.models import Action
from tests.contract.helpers import assert_action_adapter_contract
from tests.unit.actions.browser.support import FakeDriver, make_action


def build(tmp_path: Path, driver: FakeDriver) -> ActionAdapter:
    adapter: ActionAdapter = BrowserPortalAdapter(
        BrowserSettings(runtime_dir=tmp_path), drivers={BrowserEngine.SCRIPTED: driver}
    )
    return adapter


def test_adapter_declares_browser_portal_reproduction(tmp_path) -> None:
    adapter = build(tmp_path, FakeDriver("scripted"))
    assert adapter.channel == Channel.BROWSER_PORTAL
    assert adapter.badge == RealityBadge.REPRODUCTION


async def test_shared_action_adapter_contract(tmp_path) -> None:
    await assert_action_adapter_contract(build(tmp_path, FakeDriver("scripted")))


@pytest.mark.parametrize("error", [None, *PortalErrorCode])
async def test_every_outcome_is_a_valid_action_result(tmp_path, error) -> None:
    adapter = build(tmp_path, FakeDriver("scripted", error=error))
    action = make_action()

    result = await adapter.execute(action)

    assert result.action_id == action.id
    assert result.badge == RealityBadge.REPRODUCTION
    if error is None:
        assert result.status == ActionResultStatus.SUCCESS
        proof = json.loads(result.proof or "")
        assert {"case_number", "url", "screenshot_path", "captured_at"} <= proof.keys()
    else:
        assert result.status == ActionResultStatus.FAILURE
        assert result.error == error.value


async def test_other_channels_are_refused(tmp_path) -> None:
    adapter = build(tmp_path, FakeDriver("scripted"))
    action = Action(
        case_id=make_action().case_id,
        channel=Channel.EMAIL_RESELLER,
        kind="send_claim_email",
        idempotency_key="k",
        badge=RealityBadge.REPRODUCTION,
    )

    result = await adapter.execute(action)

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == "unsupported_channel"
