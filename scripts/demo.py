"""Lanceur local de démonstration, sans dépendance Python tierce."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.cookiejar
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from contextlib import closing, suppress
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8001/api"
DELL = "http://127.0.0.1:8100"
FRONT = "http://127.0.0.1:5173"
PORTS = {8001: "API", 5173: "interface", 2525: "SMTP", 8100: "reproduction Dell"}
INSTALL = {
    "uv": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    " (macOS/Linux : https://docs.astral.sh/uv/)",
    "node": "installer Node.js LTS : https://nodejs.org/",
    "npm": "réinstaller Node.js LTS (npm inclus) : https://nodejs.org/",
}


class DemoError(RuntimeError):
    pass


def resolve_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise DemoError(f"Outil manquant : {name}. Pour l'installer : {INSTALL[name]}")
    return executable


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, cast(Any, socket).SO_EXCLUSIVEADDRUSE, 1)
        else:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


def process_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}
    return {"start_new_session": True}


def npm_needed(frontend: Path, marker: Path) -> bool:
    if not (frontend / "node_modules").is_dir() or not marker.is_file():
        return True
    return marker.read_text(encoding="utf-8") != lock_hash(frontend)


def lock_hash(frontend: Path) -> str:
    return hashlib.sha256((frontend / "package-lock.json").read_bytes()).hexdigest()


def database_seeded(database: Path) -> bool:
    if not database.is_file():
        return False
    try:
        with closing(
            sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM people), EXISTS(SELECT 1 FROM equipment)"
            ).fetchone()
            return bool(row[0] and row[1])
    except sqlite3.DatabaseError as error:
        if "no such table" in str(error):
            return False
        raise DemoError(
            "Base locale illisible. Sauvegardez-la avant de relancer avec --reset."
        ) from error


def npm_command(node: str, npm: str) -> list[str]:
    if os.name != "nt":
        return [npm, "ci"]
    cli = Path(npm).parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not cli.is_file():
        raise DemoError("npm incomplet. Réinstallez Node.js LTS depuis https://nodejs.org/.")
    return [node, str(cli), "ci"]


class WindowsJob:
    """Le noyau ferme aussi les descendants si la console disparaît."""

    def __init__(self) -> None:
        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t),
                ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimits),
                ("io", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t),
            ]

        self.kernel = cast(Any, ctypes).WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise DemoError("Impossible de créer le groupe de processus Windows de la démo.")

    def add(self, process: subprocess.Popen[bytes]) -> None:
        handle = int(cast(Any, process)._handle)
        if not self.kernel.AssignProcessToJobObject(self.handle, handle):
            raise DemoError("Impossible de protéger les processus enfants Windows.")

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


@dataclass
class Child:
    name: str
    process: subprocess.Popen[bytes]
    log: Path
    stream: BinaryIO

    def failure(self) -> DemoError:
        self.stream.flush()
        tail = "\n".join(self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
        return DemoError(
            f"{self.name} s'est arrêté (code {self.process.returncode}).\n"
            f"Journal : {self.log}\n{tail}"
        )


class Supervisor:
    def __init__(self, root: Path, env: dict[str, str]) -> None:
        self.root = root
        self.env = env
        self.children: list[Child] = []
        self.job = WindowsJob() if os.name == "nt" else None

    def start(self, name: str, command: list[str], cwd: Path | None = None) -> Child:
        logs = self.root / "runtime" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / f"{name}.log"
        stream = log.open("wb")
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd or self.root,
                env=self.env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                **process_options(),
            )
        except OSError:
            stream.close()
            raise
        child = Child(name, process, log, stream)
        self.children.append(child)
        if self.job:
            self.job.add(process)
        return child

    def check(self) -> None:
        for child in self.children:
            if child.process.poll() is not None:
                raise child.failure()

    def run(self, label: str, command: list[str], cwd: Path | None = None) -> None:
        print(label, flush=True)
        child = self.start("setup", command, cwd)
        while child.process.poll() is None:
            time.sleep(0.2)
        if child.process.returncode:
            raise child.failure()
        self.children.remove(child)
        child.stream.close()

    def ready(self, child: Child, port: int, url: str | None = None) -> None:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            self.check()
            try:
                if url:
                    with local_opener().open(url, timeout=1) as response:
                        if response.status == 200:
                            return
                else:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        raise DemoError(f"{child.name} n'est pas prêt après 90 s. Journal : {child.log}")

    def stop(self) -> None:
        for child in reversed(self.children):
            process = child.process
            if os.name == "nt":
                if process.poll() is None and shutil.which("taskkill"):
                    subprocess.run(
                        ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            else:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
        if self.job:
            self.job.close()
        for child in reversed(self.children):
            try:
                child.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    child.process.kill()
                else:
                    with suppress(ProcessLookupError):
                        os.killpg(child.process.pid, signal.SIGKILL)
                child.process.wait()
            if os.name != "nt":
                with suppress(ProcessLookupError):
                    os.killpg(child.process.pid, signal.SIGKILL)
            child.stream.close()


def local_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )


def request_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    data: dict[str, Any] | None = None,
) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with opener.open(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


def backend_info(command: list[str], env: dict[str, str]) -> dict[str, Any]:
    code = (
        "import json; from app.core.settings import AppSettings, DEV_DEMO_PASSWORD; "
        "s=AppSettings(); print(json.dumps(dict(database=s.database_url, "
        "password=s.active_demo_password(), default_password=DEV_DEMO_PASSWORD, "
        "environment=s.environment, demo=s.demo_mode, "
        "gmail=bool(s.gmail_client_id or s.gmail_client_secret or s.gmail_refresh_token))))"
    )
    result = subprocess.run(
        [*command, "python", "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise DemoError(
            "Configuration backend illisible. Vérifiez .env et relancez sans --skip-setup."
        )
    info: dict[str, Any] = json.loads(result.stdout)
    if info["environment"] != "dev" or not info["demo"] or info["gmail"]:
        raise DemoError(
            "Démo locale uniquement : WP_ENV=dev, WP_DEMO_MODE=true, sans identifiants Gmail."
        )
    if not str(info["database"]).startswith("sqlite:///"):
        raise DemoError("La démo exige une base SQLite locale (WP_DATABASE_URL).")
    return info


def advance(info: dict[str, Any]) -> None:
    opener = local_opener()
    people = request_json(opener, f"{API}/auth/people")
    karim = next((person for person in people if person["name"] == "Karim Benali"), None)
    if not karim:
        raise DemoError("Karim Benali est absent : relancez la démo avec --reset.")
    request_json(
        opener, f"{API}/auth/login", {"person_id": karim["id"], "password": info["password"]}
    )
    try:
        cases = request_json(opener, f"{DELL}/__test__/cases")
        if not cases:
            raise DemoError(
                "Aucun dossier Dell. Créez et validez d'abord le dossier dans l'interface."
            )
        case = max(cases, key=lambda item: item["created"])
        number = urllib.parse.quote(str(case["number"]), safe="")
        for _ in range(3):
            if case["status"] == "closed":
                break
            case = request_json(opener, f"{DELL}/__test__/advance/{number}", {})
        if case["status"] != "closed":
            raise DemoError("Le portail Dell n'a pas atteint l'état clôturé.")
        print(f"Portail Dell local : dossier {case['number']} clôturé (simulation).")
        result = request_json(opener, f"{API}/followup/tick", {})
        print("Suivi WarrantyPilot déclenché : " + json.dumps(result, ensure_ascii=False))
    finally:
        request_json(opener, f"{API}/auth/logout", {})


def launch(args: argparse.Namespace) -> None:
    tools = {name: resolve_tool(name) for name in INSTALL}
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "WP_FOLLOWUP_INTERVAL_S": "5",
        "WP_SMTP_PORT": "2525",
        "WP_MAILDIR_PATH": "runtime/mail",
        "WP_BROWSER_ENGINE": "scripted",
        "BROWSER_ENGINE": "scripted",
        "WP_BROWSER_PORTAL_URL": DELL,
        "VITE_API_PROXY_TARGET": "http://127.0.0.1:8001",
        "DELL_REPRO_PORT": "8100",
        "DELL_REPRO_RUNTIME": str(ROOT / "repro" / "dell" / "runtime"),
    }
    python = subprocess.run(
        [tools["uv"], "python", "find", "3.12"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if python.returncode or sys.version_info[:2] != (3, 12):
        raise DemoError(
            "Python 3.12 est requis. Lancez : uv python install 3.12, puis relancez demo."
        )
    backend = [tools["uv"], "run", "--no-sync", "--project", "backend"]
    if args.command == "advance":
        advance(backend_info(backend, env))
        return
    for port, name in PORTS.items():
        if port_busy(port):
            raise DemoError(
                f"Port {port} occupé ({name}). Arrêtez l'autre application puis réessayez."
            )
    (ROOT / "runtime" / "anchors").mkdir(parents=True, exist_ok=True)
    dot_env = ROOT / ".env"
    if not dot_env.exists():
        shutil.copyfile(ROOT / ".env.example", dot_env)
    supervisor = Supervisor(ROOT, env)
    try:
        if not args.skip_setup:
            supervisor.run("Préparation du backend…", [tools["uv"], "sync", "--project", "backend"])
            supervisor.run(
                "Préparation du portail Dell…",
                [tools["uv"], "sync", "--project", "repro/dell", "--locked"],
            )
            marker = ROOT / "runtime" / "npm-lock.sha256"
            if npm_needed(ROOT / "frontend", marker):
                supervisor.run(
                    "Installation de l'interface…",
                    npm_command(tools["node"], tools["npm"]),
                    ROOT / "frontend",
                )
                marker.write_text(lock_hash(ROOT / "frontend"), encoding="utf-8")
            supervisor.run(
                "Vérification de Chromium pour l'action Dell (téléchargé si absent)…",
                [*backend, "playwright", "install", "chromium"],
            )
        info = backend_info(backend, env)
        database = Path(str(info["database"]).removeprefix("sqlite:///"))
        if not database.is_absolute():
            database = ROOT / database
        seed = args.reset or not database_seeded(database)
        if not args.skip_setup:
            supervisor.run(
                "Migrations de la base locale…",
                [*backend, "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
            )
        if seed:
            supervisor.run(
                "Initialisation des données fictives…", [*backend, "python", "-m", "app.core.reset"]
            )
        smtp = supervisor.start(
            "smtp",
            [
                *backend,
                "python",
                "-m",
                "app.actions.email.local_smtp_server",
                "--port",
                "2525",
                "--maildir",
                "runtime/mail",
            ],
        )
        supervisor.ready(smtp, 2525)
        dell = supervisor.start(
            "dell",
            [
                tools["uv"],
                "run",
                "--no-sync",
                "--project",
                str(ROOT / "repro" / "dell"),
                "python",
                "-m",
                "dell_repro",
            ],
            ROOT / "repro" / "dell",
        )
        supervisor.ready(dell, 8100, f"{DELL}/__test__/cases")
        if seed:
            request_json(local_opener(), f"{DELL}/__test__/reset", {})
        api = supervisor.start(
            "api",
            [
                *backend,
                "uvicorn",
                "--app-dir",
                "backend",
                "app.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
            ],
        )
        supervisor.ready(api, 8001, f"{API}/health")
        vite = supervisor.start(
            "vite",
            [
                tools["node"],
                str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ],
            ROOT / "frontend",
        )
        supervisor.ready(vite, 5173, FRONT)
        password = (
            info["default_password"]
            if info["password"] == info["default_password"]
            else "celui configuré dans WP_DEMO_PASSWORD"
        )
        print(
            f"\nWarrantyPilot est prêt : {FRONT}\nConnexion : Karim Benali\n"
            f"Mot de passe : {password}\n"
            "Portail Dell : reproduction locale, aucun envoi à Dell.\n"
            "Arrêt : Ctrl+C. Journaux : runtime/logs/\n",
            flush=True,
        )
        if not args.no_browser:
            webbrowser.open(FRONT)
        while True:
            supervisor.check()
            time.sleep(0.5)
    finally:
        supervisor.stop()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        cast(Any, sys.stderr).reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Démarrer la démo locale WarrantyPilot")
    parser.add_argument("command", nargs="?", choices=["advance"], help="Avancer le portail Dell")
    parser.add_argument(
        "--reset", action="store_true", help="Réinitialiser la base et le portail Dell"
    )
    parser.add_argument(
        "--skip-setup", action="store_true", help="Ignorer les installations et migrations"
    )
    parser.add_argument("--no-browser", action="store_true", help="Ne pas ouvrir le navigateur")
    args = parser.parse_args()

    def interrupted(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    if os.name == "nt":
        signal.signal(cast(Any, signal).SIGBREAK, interrupted)
    else:
        signal.signal(signal.SIGHUP, interrupted)
    try:
        launch(args)
    except KeyboardInterrupt:
        print("\nDémo arrêtée.")
    except (DemoError, OSError, ValueError) as error:
        print(f"\nErreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
