import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contracts.enums import CaseStatus
from app.core import flags
from app.core.journal import verify
from app.core.settings import AppSettings
from app.core.tables import cases


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    fix_hint: str | None = None


Check = Callable[..., CheckResult]
_EXTRA_CHECKS: dict[str, Check] = {}


def register_check(name: str, check: Check) -> None:
    _EXTRA_CHECKS[name] = check


def unregister_check(name: str) -> None:
    _EXTRA_CHECKS.pop(name, None)


def _feature_configuration_check() -> CheckResult:
    try:
        flags.load_features()
    except (flags.FeatureConfigurationError, OSError) as error:
        return CheckResult(
            name="feature_flags",
            ok=False,
            detail=str(error),
            fix_hint="Corriger config/features.yaml.",
        )
    return CheckResult("feature_flags", True, "Configuration des drapeaux valide.")


def run_checks(
    engine: Engine,
    session: Session,
    settings: AppSettings,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        results.append(CheckResult("database", True, "Base accessible."))
    except Exception as error:
        results.append(CheckResult("database", False, str(error), "Vérifier WP_DATABASE_URL."))
    journal_result = verify(session, settings)
    results.append(
        CheckResult(
            "journal",
            bool(journal_result["ok"]),
            f"Vérification du journal: {journal_result}",
            None if journal_result["ok"] else "Examiner les événements et ancrages.",
        )
    )
    anchor_parent = Path(settings.anchor_file).expanduser().parent
    anchor_file = Path(settings.anchor_file).expanduser()
    anchor_ok = (
        anchor_parent.exists()
        and anchor_parent.is_dir()
        and os.access(anchor_parent, os.R_OK | os.W_OK)
        and (not anchor_file.exists() or os.access(anchor_file, os.R_OK | os.W_OK))
    )
    results.append(
        CheckResult(
            "anchor_file",
            anchor_ok,
            "Dossier d'ancres accessible." if anchor_ok else "Dossier d'ancres inaccessible.",
            None if anchor_ok else "Créer le dossier runtime/anchors.",
        )
    )
    blocked = session.execute(
        select(cases.c.id).where(cases.c.status == CaseStatus.SENDING.value).limit(1)
    ).first()
    results.append(
        CheckResult(
            "no_stuck_sending",
            blocked is None,
            "Aucun dossier bloqué en sending."
            if blocked is None
            else f"Dossier bloqué en sending: {blocked.id}",
            None if blocked is None else "Redémarrer la reprise des dossiers sending.",
        )
    )
    results.append(_feature_configuration_check())
    for name, check in _EXTRA_CHECKS.items():
        try:
            results.append(check(engine=engine, session=session, settings=settings))
        except Exception as error:
            results.append(
                CheckResult(name, False, str(error), "Examiner le contrôle ajouté par le lot.")
            )
    return results


def preflight_payload(results: list[CheckResult]) -> dict[str, Any]:
    return {
        "ok": all(result.ok for result in results),
        "checks": [result.__dict__ for result in results],
    }
