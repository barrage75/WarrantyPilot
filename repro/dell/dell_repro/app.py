import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parent.parent
HOME = "/support/home/fr-fr"
SERVICE = "/support/incidents-online/fr-fr/servicerequest"
SIGNIN = "/myaccount/fr-fr/signin"
CATEGORIES = [
    "Ne démarre pas",
    "Écran",
    "Clavier/pavé tactile",
    "Batterie/alimentation",
    "Disque/stockage",
    "Carte mère/autre matériel",
    "Logiciel",
]
SLOTS = ["Matin 8h–12h", "Après-midi 13h–18h"]
STATES = ["received", "in_progress", "part_shipped", "closed"]
STATE_LABELS = ["Reçu", "En cours", "Pièce expédiée", "Clôturé"]
FIELDS = {
    "problemCategory": "Catégorie du problème",
    "problemDescription": "Décrivez votre problème",
    "contactFirstName": "Prénom",
    "contactLastName": "Nom",
    "contactEmail": "Adresse e-mail",
    "contactPhone": "Téléphone",
    "companyName": "Société (facultatif)",
    "addressLine1": "Adresse",
    "addressLine2": "Complément d’adresse (facultatif)",
    "postalCode": "Code postal",
    "city": "Ville",
    "country": "Pays",
    "availabilityDate": "Date de disponibilité",
    "availabilitySlot": "Créneau de disponibilité",
}


def today() -> date:
    return date.fromisoformat(os.getenv("DELL_REPRO_TODAY", date.today().isoformat()))


def now() -> str:
    return os.getenv("DELL_REPRO_NOW", datetime.now().astimezone().isoformat())


def history_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%d/%m/%Y à %H:%M")


def normalize(tag: str) -> str:
    return "".join(tag.split()).upper()


def safe_next(value: str) -> str:
    parsed = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or parsed.netloc
        or parsed.scheme
        or "\\" in value
        or any(ord(c) < 32 for c in value)
    ):
        return HOME
    return value


def create_app(runtime: Path | None = None, *, allow_testclient: bool = False) -> FastAPI:
    runtime = runtime or Path(os.getenv("DELL_REPRO_RUNTIME", str(ROOT / "runtime")))
    runtime.mkdir(parents=True, exist_ok=True)
    uploads = runtime / "uploads"
    uploads.mkdir(exist_ok=True)
    db_path = runtime / "cases.sqlite3"

    def db() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    with closing(db()) as conn, conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cases (number TEXT PRIMARY KEY, "
            "token TEXT UNIQUE NOT NULL, tag TEXT NOT NULL, status TEXT NOT NULL, "
            "created TEXT NOT NULL, updated TEXT NOT NULL, payload TEXT NOT NULL, "
            "history TEXT NOT NULL)"
        )
    assets: list[dict[str, Any]] = json.loads((ROOT / "data/assets.json").read_text())
    account = json.loads((ROOT / "config/demo_account.json").read_text())
    templates = Jinja2Templates(directory=ROOT / "templates")
    templates.env.filters["history_date"] = history_date
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32), same_site="strict")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    def render(request: Request, template: str, status: int = 200, **ctx: Any) -> Response:
        return templates.TemplateResponse(
            request=request,
            name=template,
            status_code=status,
            context={
                "home": HOME,
                "service": SERVICE,
                "signin": SIGNIN,
                "fields": FIELDS,
                "categories": CATEGORIES,
                "slots": SLOTS,
                **ctx,
            },
        )

    def asset(tag: str) -> dict[str, Any]:
        for item in assets:
            if item["tag"] == normalize(tag):
                days = (date.fromisoformat(item["expires"]) - today()).days
                state = "expired" if days < 0 else "expiring" if days < 90 else "active"
                return {
                    **item,
                    "status": state,
                    "label": {"expired": "Expiré", "expiring": "Expire bientôt", "active": "Actif"}[
                        state
                    ],
                    "expiry_fr": date.fromisoformat(item["expires"]).strftime("%d/%m/%Y"),
                }
        raise HTTPException(404, "Produit introuvable.")

    @app.middleware("http")
    async def local_host(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not re.fullmatch(
            r"(?:localhost|127\.0\.0\.1)(?::[0-9]+)?", request.headers.get("host", "")
        ):
            return render(request, "error.html", 400, code=400, message="Hôte non autorisé.")
        return await call_next(request)

    def get_case(number: str) -> dict[str, Any]:
        with closing(db()) as conn, conn:
            row = conn.execute("SELECT * FROM cases WHERE number=?", (number,)).fetchone()
        if row is None:
            raise HTTPException(404, "Dossier introuvable.")
        return {
            **dict(row),
            "payload": json.loads(row["payload"]),
            "history": json.loads(row["history"]),
        }

    def test_access(request: Request) -> None:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1"} and not (allow_testclient and host == "testclient"):
            raise HTTPException(403, "Accès local uniquement.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        return render(
            request, "error.html", exc.status_code, code=exc.status_code, message=str(exc.detail)
        )

    app.add_exception_handler(StarletteHTTPException, http_error)  # type: ignore[arg-type]

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> Response:
        return render(request, "error.html", 500, code=500, message="Une erreur est survenue.")

    @app.get("/")
    async def root() -> Response:
        return RedirectResponse(HOME, status_code=302)

    @app.get(HOME)
    async def home(request: Request, servicetag: str | None = None) -> Response:
        error = None
        if servicetag is not None:
            try:
                item = asset(servicetag)
                return RedirectResponse(
                    f"{HOME}/product-support/servicetag/{item['tag']}/overview", status_code=302
                )
            except HTTPException:
                error = (
                    "Nous n'avons pas pu identifier ce produit. Vérifiez l'étiquette de service "
                    "et réessayez."
                )
        return render(request, "home.html", error=error, tag=servicetag or "")

    @app.get(SIGNIN)
    async def signin(request: Request, next: str = HOME) -> Response:
        return render(request, "signin.html", next=safe_next(next), stage="email", error=None)

    @app.post(SIGNIN)
    async def login(request: Request) -> Response:
        form = await request.form()
        target = safe_next(str(form.get("next", HOME)))
        if "userPwd_UserInputSecret" not in form:
            request.session["pending_email"] = str(form.get("SignInModel.EmailAddress", ""))
            return render(request, "signin.html", next=target, stage="password", error=None)
        email = request.session.pop("pending_email", "")
        password = str(form.get("userPwd_UserInputSecret", ""))
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(account["salt"]), account["iterations"]
        ).hex()
        valid = hmac.compare_digest(digest, account["hash"])
        valid_email = hmac.compare_digest(str(email).encode(), account["email"].encode())
        if valid and valid_email:
            request.session.clear()
            request.session["signed_in"] = True
            return RedirectResponse(target, status_code=303)
        request.session.clear()
        return render(
            request,
            "signin.html",
            401,
            next=target,
            stage="email",
            error="L'adresse e-mail ou le mot de passe est incorrect.",
        )

    @app.post("/myaccount/fr-fr/signout")
    async def signout(request: Request) -> Response:
        request.session.clear()
        return RedirectResponse(HOME, status_code=303)

    @app.get(HOME + "/product-support/servicetag/{tag}/overview")
    async def product(request: Request, tag: str) -> Response:
        return render(request, "product.html", item=asset(tag))

    def check_service(request: Request, tag: str) -> dict[str, Any] | RedirectResponse:
        if not request.session.get("signed_in"):
            return RedirectResponse(
                SIGNIN + "?next=" + quote(SERVICE + "?servicetag=" + normalize(tag), safe=""),
                status_code=302,
            )
        item = asset(tag)
        if item["status"] == "expired":
            raise HTTPException(403, "Cet appareil n’est plus couvert par la garantie.")
        return item

    @app.get(SERVICE)
    async def service_form(request: Request, servicetag: str = "") -> Response:
        item = check_service(request, servicetag)
        if isinstance(item, RedirectResponse):
            return item
        token = str(uuid4())
        return render(
            request,
            "request.html",
            item=item,
            values={"country": "France"},
            errors={},
            token=token,
            tomorrow=(today() + timedelta(days=1)).isoformat(),
            fail=request.query_params.get("__fail", ""),
        )

    @app.post(SERVICE)
    async def submit(request: Request, servicetag: str = "") -> Response:
        item = check_service(request, servicetag)
        if isinstance(item, RedirectResponse):
            return item
        form = await request.form(max_part_size=6 * 1024 * 1024)
        values = {key: str(form.get(key, "")).strip() for key in FIELDS}
        token = str(form.get("requestToken", ""))
        errors: dict[str, str] = {}
        try:
            UUID(token)
        except ValueError:
            errors["requestToken"] = "Jeton de demande invalide. Rechargez la page."
        with closing(db()) as conn, conn:
            old = conn.execute("SELECT number FROM cases WHERE token=?", (token,)).fetchone()
        if old:
            return RedirectResponse(SERVICE + "/confirmation/" + old["number"], status_code=303)
        mode = request.query_params.get("__fail", str(form.get("__fail", ""))) or os.getenv(
            "DELL_REPRO_FAIL", ""
        )
        if mode not in {"", "500", "timeout", "slow"}:
            raise HTTPException(400, "Mode de panne inconnu.")
        if mode == "500":
            raise HTTPException(500, "Une erreur est survenue. Aucune demande n’a été créée.")
        if mode in {"timeout", "slow"}:
            seconds = os.getenv(
                "DELL_REPRO_TIMEOUT_SECONDS" if mode == "timeout" else "DELL_REPRO_SLOW_SECONDS",
                "35" if mode == "timeout" else "8",
            )
            await asyncio.sleep(float(seconds))
            if mode == "timeout":
                raise HTTPException(504, "Le délai a été dépassé. Aucune demande n’a été créée.")
        for key, value in values.items():
            if key not in {"companyName", "addressLine2"} and not value:
                errors[key] = "Ce champ est obligatoire."
            if len(value) > (2000 if key == "problemDescription" else 200):
                errors[key] = "Ce champ est trop long."
        if values["problemCategory"] not in CATEGORIES:
            errors["problemCategory"] = "Sélectionnez une catégorie."
        if not 20 <= len(values["problemDescription"]) <= 2000:
            errors["problemDescription"] = "Saisissez entre 20 et 2000 caractères."
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["contactEmail"]):
            errors["contactEmail"] = "Saisissez une adresse e-mail valide."
        if not re.fullmatch(
            r"(?:0|\+33)[1-9][0-9]{8}", re.sub(r"[ .-]", "", values["contactPhone"])
        ):
            errors["contactPhone"] = "Saisissez un numéro de téléphone français valide."
        if not re.fullmatch(r"\d{5}", values["postalCode"]):
            errors["postalCode"] = "Saisissez un code postal à 5 chiffres."
        if values["country"] != "France":
            errors["country"] = "Le pays doit être France."
        try:
            if date.fromisoformat(values["availabilityDate"]) <= today():
                raise ValueError
        except ValueError:
            errors["availabilityDate"] = "Choisissez une date à partir de demain."
        if values["availabilitySlot"] not in SLOTS:
            errors["availabilitySlot"] = "Sélectionnez un créneau."
        if form.get("consent") != "on":
            errors["consent"] = "Votre consentement est obligatoire."
        attachment = form.get("attachment")
        content = b""
        filename = ""
        if isinstance(attachment, UploadFile) and attachment.filename:
            content = await attachment.read(5 * 1024 * 1024 + 1)
            filename = Path(attachment.filename.replace("\\", "/")).name[:150]
            if not content.startswith(b"%PDF-") or len(content) > 5 * 1024 * 1024:
                errors["attachment"] = "Joignez un PDF de 5 Mo maximum."
        if errors:
            return render(
                request,
                "request.html",
                422,
                item=item,
                values=values,
                errors=errors,
                token=token,
                tomorrow=(today() + timedelta(days=1)).isoformat(),
                fail=mode,
                consent=form.get("consent") == "on",
            )
        created = now()
        payload: dict[str, Any] = {**values, "attachment": {"name": filename, "size": len(content)}}
        with closing(db()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT number FROM cases WHERE token=?", (token,)).fetchone()
            if old:
                return RedirectResponse(SERVICE + "/confirmation/" + old["number"], status_code=303)
            seq = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]) + 1
            while True:
                raw = (
                    f"{os.getenv('DELL_REPRO_SEED', 'appelia-demo')}|{item['tag']}|{created}|{seq}"
                )
                number = str(
                    1_000_000_000
                    + int(hashlib.sha256(raw.encode()).hexdigest(), 16) % 9_000_000_000
                )
                if not conn.execute("SELECT 1 FROM cases WHERE number=?", (number,)).fetchone():
                    break
                seq += 1
            if content:
                folder = uploads / number
                folder.mkdir(exist_ok=True)
                (folder / "attachment.pdf").write_bytes(content)
            history = [{"status": "received", "date": created}]
            conn.execute(
                "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?)",
                (
                    number,
                    token,
                    item["tag"],
                    "received",
                    created,
                    created,
                    json.dumps(payload),
                    json.dumps(history),
                ),
            )
        return RedirectResponse(SERVICE + "/confirmation/" + number, status_code=303)

    @app.get(SERVICE + "/confirmation/{number}")
    async def confirmation(request: Request, number: str) -> Response:
        case = get_case(number)
        return render(
            request,
            "case.html",
            case=case,
            item=asset(case["tag"]),
            confirmation=True,
            states=STATES,
            labels=STATE_LABELS,
        )

    @app.get("/support/status/{number}")
    async def status(request: Request, number: str) -> Response:
        case = get_case(number)
        return render(
            request,
            "case.html",
            case=case,
            item=asset(case["tag"]),
            confirmation=False,
            states=STATES,
            labels=STATE_LABELS,
        )

    @app.get("/__test__/cases")
    async def cases(request: Request) -> Response:
        test_access(request)
        with closing(db()) as conn, conn:
            rows = conn.execute("SELECT number,tag,status,created,updated FROM cases").fetchall()
        return JSONResponse([dict(row) for row in rows])

    @app.post("/__test__/reset")
    async def reset(request: Request) -> Response:
        test_access(request)
        with closing(db()) as conn, conn:
            conn.execute("DELETE FROM cases")
        shutil.rmtree(uploads)
        uploads.mkdir()
        return JSONResponse({"reset": True})

    @app.post("/__test__/advance/{number}")
    async def advance(request: Request, number: str) -> Response:
        test_access(request)
        case = get_case(number)
        if case["status"] == "closed":
            raise HTTPException(409, "Ce dossier est déjà clôturé.")
        state = STATES[STATES.index(case["status"]) + 1]
        timestamp = now()
        case["history"].append({"status": state, "date": timestamp})
        with closing(db()) as conn, conn:
            conn.execute(
                "UPDATE cases SET status=?,updated=?,history=? WHERE number=?",
                (state, timestamp, json.dumps(case["history"]), number),
            )
        return JSONResponse(get_case(number))

    return app


app = create_app()
