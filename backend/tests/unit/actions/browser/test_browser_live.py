"""Live engine runs (skipped unless real AI credentials are present)."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from app.actions.browser import BrowserPortalAdapter, BrowserSettings
from app.contracts.enums import ActionResultStatus

from .conftest import ReproServer
from .support import make_action


def live_settings(repro: ReproServer, tmp_path: Path, engine: str) -> BrowserSettings:
    return BrowserSettings(
        browser_engine=engine,
        fallback_to_scripted=False,
        portal_url=repro.url,
        test_mode=True,
        test_origins=[f"127.0.0.1:{repro.port}", f"localhost:{repro.port}"],
        runtime_dir=tmp_path,
        action_timeout_seconds=600,
    )


@pytest.mark.skipif(not os.getenv("HCOMPANY_API_KEY"), reason="live: HCOMPANY_API_KEY absent")
async def test_live_hcompany_agent_files_the_request(dell_repro: ReproServer, tmp_path) -> None:
    dell_repro.reset()
    adapter = BrowserPortalAdapter(live_settings(dell_repro, tmp_path, "hcompany"))

    result = await adapter.execute(make_action(url=dell_repro.url))

    assert result.status == ActionResultStatus.SUCCESS, result.error
    assert json.loads(result.proof or "")["engine"] == "hcompany"
    assert len(dell_repro.cases()) == 1


@pytest.mark.skipif(
    importlib.util.find_spec("browser_use") is None
    or not (os.getenv("BROWSER_USE_API_KEY") or os.getenv("OPENAI_API_KEY")),
    reason="live: browser-use or its LLM key absent",
)
async def test_live_browser_use_agent_files_the_request(dell_repro: ReproServer, tmp_path) -> None:
    dell_repro.reset()
    adapter = BrowserPortalAdapter(live_settings(dell_repro, tmp_path, "browser_use"))

    result = await adapter.execute(make_action(url=dell_repro.url))

    assert result.status == ActionResultStatus.SUCCESS, result.error
    assert len(dell_repro.cases()) == 1
