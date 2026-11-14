import csv
import io
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from app.contracts.enums import CaseStatus, Channel
from app.contracts.models import utc_now
from app.core import tables
from app.core.journal import verify
from app.core.warranty import rules_engine, savings_totals

router = APIRouter(prefix="/reports", tags=["reports"])


class SavingsLine(BaseModel):
    case_id: str
    equipment_label: str
    manufacturer: str
    channel: Channel
    status: CaseStatus
    amount_eur: float
    realized: bool
    resolved_at: str | None
    reference: str | None


class SavingsReport(BaseModel):
    generated_at: datetime
    company: str
    covered_equipment_eur: float
    possible_savings_eur: float
    realized_savings_eur: float
    journal_ok: bool
    journal_head: str | None
    lines: list[SavingsLine]


@router.get("/savings", response_model=SavingsReport)
def savings(request: Request) -> SavingsReport:
    application = request.app
    with application.state.session_factory() as session:
        totals = savings_totals(
            session, rules_engine(application), application.state.services.get("rules", [])
        )
        journal_ok = bool(verify(session, application.state.app_settings)["ok"])
        head = session.execute(
            select(tables.events.c.hash).order_by(tables.events.c.seq.desc()).limit(1)
        ).scalar_one_or_none()
        equipment = {row.id: row for row in session.execute(select(tables.equipment))}
        purchases: dict[str, list[tuple[float, str, str | None]]] = {}
        for row in session.execute(select(tables.purchase_requests)):
            if row.case_id:
                purchases.setdefault(row.case_id, []).append(
                    (float(row.amount), row.state, row.resolved_at)
                )
        references: dict[str, str] = {}
        for row in session.execute(select(tables.actions)):
            if row.payload.get("proof_type") == "case_number":
                reference = row.payload.get("reference")
                if isinstance(reference, str):
                    references[row.case_id] = reference
        channels = {row.id: row.channel for row in session.execute(select(tables.verdicts))}
        for row in session.execute(select(tables.events).order_by(tables.events.c.seq)):
            payload = row.payload
            proof = payload.get("proof")
            proof = proof if isinstance(proof, dict) else {}
            reference = (
                payload.get("case_number")
                or payload.get("rma")
                or proof.get("case_number")
                or proof.get("rma")
                or (
                    payload.get("reference") if payload.get("proof_type") == "case_number" else None
                )
            )
            if isinstance(reference, str) and row.case_id:
                references[row.case_id] = reference
        lines = []
        for row in session.execute(
            select(tables.cases).order_by(tables.cases.c.created_at, tables.cases.c.id)
        ):
            item = equipment.get(row.equipment_id)
            linked = purchases.get(row.id, [])
            resolved = [p[2] for p in linked if p[2]]
            lines.append(
                SavingsLine(
                    case_id=row.id,
                    equipment_label=f"{item.brand} {item.model}" if item else "",
                    manufacturer=item.brand if item else "",
                    channel=channels.get(row.verdict_id) or row.channel,
                    status=row.status,
                    amount_eur=round(sum(p[0] for p in linked), 2)
                    if linked
                    else float(item.purchase_price or 0)
                    if item
                    else 0,
                    realized=bool(linked) and all(p[1] == "saving_realized" for p in linked),
                    resolved_at=max(resolved)
                    if resolved
                    else row.updated_at
                    if row.status == "resolved"
                    else None,
                    reference=references.get(row.id),
                )
            )
    return SavingsReport(
        generated_at=utc_now(),
        company="Appelia",
        **totals,
        journal_ok=journal_ok,
        journal_head=head,
        lines=lines,
    )


@router.get("/savings.csv")
def savings_csv(request: Request) -> Response:
    report = savings(request)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(
        [
            "Dossier",
            "Équipement",
            "Fabricant",
            "Canal",
            "Statut",
            "Montant EUR",
            "Réalisé",
            "Résolu le",
            "Référence",
        ]
    )
    for line in report.lines:
        writer.writerow(
            [
                line.case_id,
                line.equipment_label,
                line.manufacturer,
                line.channel.value,
                line.status.value,
                f"{line.amount_eur:.2f}",
                "oui" if line.realized else "non",
                line.resolved_at or "",
                line.reference or "",
            ]
        )
    return Response(
        content=stream.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; filename=warrantypilot-economies-"
                f"{report.generated_at.date().isoformat()}.csv"
            )
        },
    )
