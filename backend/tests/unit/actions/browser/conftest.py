"""Starts the local Dell reproduction (repro/dell) on a free loopback port."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
REPRO_DIR = REPO_ROOT / "repro" / "dell"
REPRO_TODAY = "2026-11-14"
SLOW_SECONDS = 1.5


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class ReproServer:
    port: int

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _call(self, method: str, path: str) -> Any:
        request = urllib.request.Request(self.url + path, method=method)
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            return json.loads(response.read() or b"null")

    def cases(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._call("GET", "/__test__/cases")
        return result

    def reset(self) -> None:
        self._call("POST", "/__test__/reset")


@pytest.fixture(scope="session")
def dell_repro(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ReproServer]:
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed in the backend environment")
    uv = shutil.which("uv")
    if uv is None or not (REPRO_DIR / "pyproject.toml").exists():
        pytest.skip("uv or repro/dell is unavailable")
    port = free_port()
    env = {
        **os.environ,
        "DELL_REPRO_PORT": str(port),
        "DELL_REPRO_RUNTIME": str(tmp_path_factory.mktemp("dell-runtime")),
        "DELL_REPRO_TODAY": REPRO_TODAY,
        "DELL_REPRO_TIMEOUT_SECONDS": "0.25",
        "DELL_REPRO_SLOW_SECONDS": str(SLOW_SECONDS),
    }
    env.pop("VIRTUAL_ENV", None)
    process = subprocess.Popen(
        [uv, "run", "--project", str(REPRO_DIR), "--locked", "python", "-m", "dell_repro"],
        cwd=REPRO_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server = ReproServer(port)
    try:
        deadline = time.monotonic() + 120
        while True:
            try:
                server.cases()
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("the Dell reproduction did not start")
                time.sleep(0.2)
        yield server
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture
def adapter_logs(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> pytest.LogCaptureFixture:
    """Capture adapter warnings even if another test's ``fileConfig`` disabled the logger."""
    monkeypatch.setattr(logging.getLogger("app.actions.browser.adapter"), "disabled", False)
    caplog.set_level(logging.WARNING, logger="app.actions.browser.adapter")
    return caplog
