import threading
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.followup.portal import fetch_status_page

URL = "http://127.0.0.1:8100/support/status/1234567890"


@pytest.fixture
def http_guard_server():
    state = {"mode": "ok", "target_hits": 0, "redirect": ""}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.server.server_port != 8100:
                state["target_hits"] += 1
                self.send_response(200)
                self.end_headers()
                return
            if state["mode"] == "redirect":
                self.send_response(302)
                self.send_header("Location", state["redirect"])
                self.end_headers()
                return
            self.send_response(200)
            self.send_header(
                "Content-Type", "application/json" if state["mode"] == "json" else "text/html"
            )
            self.end_headers()
            with suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(b"x" * (1_000_001 if state["mode"] == "large" else 1))

    with (
        ThreadingHTTPServer(("127.0.0.1", 8100), Handler) as local,
        ThreadingHTTPServer(("127.0.0.1", 0), Handler) as target,
    ):
        threads = [
            threading.Thread(target=server.serve_forever, daemon=True) for server in (local, target)
        ]
        for thread in threads:
            thread.start()
        state["redirect"] = f"http://127.0.0.1:{target.server_port}/trap"
        try:
            yield state
        finally:
            local.shutdown()
            target.shutdown()
            for thread in threads:
                thread.join(timeout=5)


def test_http_redirects_are_not_followed(http_guard_server):
    state = http_guard_server
    state["mode"] = "redirect"
    with pytest.raises(ValueError, match="Redirection"):
        fetch_status_page(URL)
    assert state["target_hits"] == 0
    for target in ["https://dell.com/support", "/support/status/9999999999"]:
        state["redirect"] = target
        with pytest.raises(ValueError, match="Redirection"):
            fetch_status_page(URL)


def test_http_ignores_proxy_environment_and_bounds_response(http_guard_server, monkeypatch):
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    assert fetch_status_page(URL) == "x"
    for mode in ["json", "large"]:
        http_guard_server["mode"] = mode
        with pytest.raises(ValueError):
            fetch_status_page(URL)
