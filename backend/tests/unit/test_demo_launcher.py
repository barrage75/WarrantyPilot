import json
import socket
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from scripts import demo


def test_port_busy_detects_bound_socket_and_free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        assert demo.port_busy(port)
    assert not demo.port_busy(port)


@pytest.mark.skipif(demo.os.name == "nt", reason="POSIX address reuse semantics")
def test_port_busy_allows_restart_after_server_closes_connection():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(2)
        port = listener.getsockname()[1]
        assert demo.port_busy(port)
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(2)
                connection.shutdown(socket.SHUT_WR)
                assert client.recv(1) == b""
                client.shutdown(socket.SHUT_WR)
                assert connection.recv(1) == b""
    with socket.socket() as probe, pytest.raises(OSError):
        probe.bind(("127.0.0.1", port))
    assert not demo.port_busy(port)


@pytest.mark.parametrize("name", ["uv", "node", "npm"])
def test_missing_command_has_french_hint(monkeypatch, name):
    monkeypatch.setattr(demo.shutil, "which", lambda command: None)
    with pytest.raises(demo.DemoError, match=f"Outil manquant : {name}.*installer"):
        demo.resolve_tool(name)


def test_command_resolution_preserves_windows_cmd(monkeypatch):
    monkeypatch.setattr(demo.shutil, "which", lambda name: r"C:\Program Files\nodejs\npm.cmd")
    assert demo.resolve_tool("npm") == r"C:\Program Files\nodejs\npm.cmd"


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_process_options_separate_windows_and_posix(monkeypatch, platform):
    with monkeypatch.context() as patch:
        patch.setattr(demo, "os", SimpleNamespace(name=platform))
        options = demo.process_options()
    if platform == "nt":
        assert options == {"creationflags": 0x200}
    else:
        assert options == {"start_new_session": True}
    assert "preexec_fn" not in options
    assert "shell" not in options


def test_lock_marker_requires_modules_and_matching_lockfile(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    lock = frontend / "package-lock.json"
    lock.write_text("first", encoding="utf-8")
    marker = tmp_path / "npm-lock.sha256"
    assert demo.npm_needed(frontend, marker)
    (frontend / "node_modules").mkdir()
    assert demo.npm_needed(frontend, marker)
    marker.write_text(demo.lock_hash(frontend), encoding="utf-8")
    assert not demo.npm_needed(frontend, marker)
    lock.write_text("second", encoding="utf-8")
    assert demo.npm_needed(frontend, marker)
    marker.write_text(demo.lock_hash(frontend), encoding="utf-8")
    (frontend / "node_modules").rmdir()
    assert demo.npm_needed(frontend, marker)


def test_database_seed_detection_handles_missing_partial_and_complete_setup(tmp_path):
    database = tmp_path / "demo.sqlite3"
    assert not demo.database_seeded(database)
    with sqlite3.connect(database) as connection:
        assert not demo.database_seeded(database)
        connection.executescript("CREATE TABLE people (id); CREATE TABLE equipment (id);")
        assert not demo.database_seeded(database)
        connection.executescript("INSERT INTO people VALUES (1); INSERT INTO equipment VALUES (1);")
        assert demo.database_seeded(database)


def test_database_seed_detection_rejects_corrupt_db_without_deleting_it(tmp_path):
    database = tmp_path / "demo.sqlite3"
    database.write_bytes(b"not a database")
    with pytest.raises(demo.DemoError, match="Base locale illisible"):
        demo.database_seeded(database)
    assert database.read_bytes() == b"not a database"


def test_advance_authenticates_closes_last_case_and_ticks(monkeypatch):
    calls = []
    cases = [
        {"number": "old", "status": "received", "created": "2026-01-01"},
        {"number": "new", "status": "received", "created": "2026-02-01"},
    ]
    states = iter(["in_progress", "part_shipped", "closed"])

    def request(opener, url, data=None):
        calls.append((opener, url, data))
        if url.endswith("/auth/people"):
            return [{"id": "samy", "name": "Samy Benzeguir"}]
        if url.endswith("/__test__/cases"):
            return cases
        if "/advance/" in url:
            return {"number": "new", "status": next(states)}
        return {}

    monkeypatch.setattr(demo, "request_json", request)
    demo.advance({"password": "local-test"})
    assert len({id(opener) for opener, _, _ in calls}) == 1
    assert calls[1][1:] == (
        f"{demo.API}/auth/login",
        {"person_id": "samy", "password": "local-test"},
    )
    assert [url for _, url, _ in calls if "/advance/" in url] == [
        f"{demo.DELL}/__test__/advance/new"
    ] * 3
    assert calls[-2][1] == f"{demo.API}/followup/tick"
    assert calls[-1][1] == f"{demo.API}/auth/logout"


def test_advance_empty_portal_logs_out(monkeypatch):
    calls = []

    def request(opener, url, data=None):
        calls.append(url)
        return [{"id": "samy", "name": "Samy Benzeguir"}] if url.endswith("/auth/people") else []

    monkeypatch.setattr(demo, "request_json", request)
    with pytest.raises(demo.DemoError, match="Aucun dossier Dell"):
        demo.advance({"password": "local-test"})
    assert calls[-1].endswith("/auth/logout")
    assert not any("/tick" in url for url in calls)


def test_request_json_posts_utf8():
    response = Mock()
    response.read.return_value = b'{"ok":true}'
    opener = Mock()
    opener.open.return_value.__enter__ = Mock(return_value=response)
    opener.open.return_value.__exit__ = Mock(return_value=False)
    assert demo.request_json(opener, demo.API, {"note": "clôturé"}) == {"ok": True}
    request = opener.open.call_args.args[0]
    assert json.loads(request.data) == {"note": "clôturé"}
    assert request.get_method() == "POST"


def test_request_json_accepts_empty_logout_response():
    response = Mock()
    response.read.return_value = b""
    opener = Mock()
    opener.open.return_value.__enter__ = Mock(return_value=response)
    opener.open.return_value.__exit__ = Mock(return_value=False)
    assert demo.request_json(opener, f"{demo.API}/auth/logout", {}) is None


def test_supervisor_reports_dead_child_and_tail(tmp_path):
    log = tmp_path / "api.log"
    log.write_text("\n".join(f"ligne {i}" for i in range(30)), encoding="utf-8")
    process = Mock()
    process.poll.return_value = 1
    process.returncode = 1
    with log.open("ab") as stream:
        child = demo.Child("api", process, log, stream)
        supervisor = demo.Supervisor(tmp_path, {})
        supervisor.children.append(child)
        with pytest.raises(demo.DemoError, match="api s'est arrêté") as error:
            supervisor.check()
        assert "ligne 29" in str(error.value)
        assert "ligne 0\n" not in str(error.value)
        if supervisor.job:
            supervisor.job.close()


def test_busy_port_prevents_setup(monkeypatch):
    monkeypatch.setattr(demo, "resolve_tool", lambda name: name)
    monkeypatch.setattr(
        demo.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )
    monkeypatch.setattr(demo.sys, "version_info", (3, 12))
    monkeypatch.setattr(demo, "port_busy", lambda port: port == 8100)
    setup = Mock()
    monkeypatch.setattr(demo, "Supervisor", setup)
    with pytest.raises(demo.DemoError, match="Port 8100 occupé"):
        demo.launch(SimpleNamespace(command=None))
    setup.assert_not_called()


def test_npm_windows_command_avoids_cmd_shell(tmp_path, monkeypatch):
    npm = tmp_path / "npm.cmd"
    cli = tmp_path / "node_modules/npm/bin/npm-cli.js"
    cli.parent.mkdir(parents=True)
    cli.touch()
    monkeypatch.setattr(demo, "os", SimpleNamespace(name="nt"))
    assert demo.npm_command("node.exe", str(npm)) == ["node.exe", str(cli), "ci"]


def test_npm_windows_incomplete_install_has_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "os", SimpleNamespace(name="nt"))
    with pytest.raises(demo.DemoError, match="Réinstallez Node.js LTS"):
        demo.npm_command("node.exe", str(tmp_path / "npm.cmd"))


def test_windows_stop_uses_taskkill_and_closes_job_without_posix_calls(tmp_path, monkeypatch):
    job = Mock()
    monkeypatch.setattr(demo, "WindowsJob", lambda: job)
    monkeypatch.setattr(demo, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(demo.shutil, "which", lambda name: name)
    run = Mock()
    monkeypatch.setattr(demo.subprocess, "run", run)
    supervisor = demo.Supervisor(tmp_path, {})
    process = Mock(pid=123)
    process.poll.return_value = None
    stream = Mock()
    supervisor.children.append(demo.Child("api", process, tmp_path / "api.log", stream))
    supervisor.stop()
    assert run.call_args.args[0] == ["taskkill", "/T", "/F", "/PID", "123"]
    job.close.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)
    stream.close.assert_called_once()


def test_posix_stop_kills_group_even_after_parent_exits(tmp_path, monkeypatch):
    killpg = Mock()
    monkeypatch.setattr(demo, "os", SimpleNamespace(name="posix", killpg=killpg))
    monkeypatch.setattr(demo, "signal", SimpleNamespace(SIGTERM=15, SIGKILL=9))
    supervisor = demo.Supervisor(tmp_path, {})
    process = Mock(pid=123)
    supervisor.children.append(demo.Child("api", process, tmp_path / "api.log", Mock()))
    supervisor.stop()
    assert [call.args for call in killpg.call_args_list] == [(123, 15), (123, 9)]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"environment": "production"}, "Démo locale uniquement"),
        ({"gmail": True}, "sans identifiants Gmail"),
        ({"database": "postgresql://server/db"}, "base SQLite locale"),
    ],
)
def test_backend_info_rejects_nonlocal_configuration(monkeypatch, overrides, message):
    info = {
        "environment": "dev",
        "demo": True,
        "gmail": False,
        "database": "sqlite:///runtime/demo.db",
        **overrides,
    }
    monkeypatch.setattr(
        demo.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(info)),
    )
    with pytest.raises(demo.DemoError, match=message):
        demo.backend_info(["uv"], {})
