"""Structured invoices. Ordinary PDFs return []; malformed XML raises ValueError."""

import re
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from lxml import etree
from pypdf import PdfReader

from app.contracts.enums import FactSource
from app.contracts.models import Document, Fact, Provenance
from app.ingestion import fields as f
from app.ingestion.controls.suspicious import (
    SuspicionReport,
    detect_suspicious,
    scan_text,
    security_fact,
)


class FacturXExtractor:
    def extract(self, document: Document, content: bytes) -> list[Fact]:
        signals = detect_suspicious(content).signals
        if content.lstrip().startswith(b"%PDF"):
            attachments = PdfReader(BytesIO(content)).attachments
            candidates = [
                data
                for name, values in attachments.items()
                if name.lower() in {"factur-x.xml", "zugferd-invoice.xml"}
                for data in values
            ]
            if not candidates:
                return security_fact(document, SuspicionReport(bool(signals), signals))
            content = candidates[0]
        try:
            root = etree.fromstring(
                content,
                parser=etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False),
            )
        except etree.XMLSyntaxError as exc:
            raise ValueError("Invalid invoice XML") from exc
        if root.getroottree().docinfo.doctype:
            raise ValueError("DTD declarations are not allowed in invoices")
        kind = etree.QName(root).localname
        if kind not in {"CrossIndustryInvoice", "Invoice"}:
            return []
        signals.extend(scan_text(" ".join(root.itertext())).signals)
        facts: list[Fact] = security_fact(document, SuspicionReport(bool(signals), signals))

        def nodes(base: Any, path: str) -> list[Any]:
            return list(
                base.xpath("./" + "/".join(f"*[local-name()='{part}']" for part in path.split("/")))
            )

        def emit(field: str, base: Any, path: str, mode: str = "text") -> None:
            found = nodes(base, path)
            if not found:
                return
            node = found[0]
            value: Any = " ".join(" ".join(node.itertext()).split())
            if not value:
                return
            if mode == "decimal":
                value = str(Decimal(value))
            elif mode == "date":
                value = (
                    datetime.strptime(
                        value, "%Y%m%d" if node.get("format") == "102" else "%Y-%m-%d"
                    )
                    .date()
                    .isoformat()
                )
            add(field, value, root.getroottree().getpath(node))

        def add(field: str, value: Any, path: str) -> None:
            facts.append(
                Fact(
                    document_id=document.id,
                    field=field,
                    value=value,
                    confidence=1.0,
                    source=FactSource.STRUCTURED,
                    provenance=Provenance(document_id=document.id, excerpt=f"{path} = {value}"),
                )
            )

        if kind == "CrossIndustryInvoice":
            emit(f.INVOICE_NUMBER, root, "ExchangedDocument/ID")
            emit(f.INVOICE_DATE, root, "ExchangedDocument/IssueDateTime/DateTimeString", "date")
            trade = nodes(root, "SupplyChainTradeTransaction")
            if not trade:
                return facts
            base = trade[0]
            agreement = "ApplicableHeaderTradeAgreement/"
            emit(f.SUPPLIER_NAME, base, agreement + "SellerTradeParty/Name")
            emit(f.SUPPLIER_ADDRESS, base, agreement + "SellerTradeParty/PostalTradeAddress")
            emit(f.CUSTOMER_NAME, base, agreement + "BuyerTradeParty/Name")
            emit(
                f.TOTAL_TTC,
                base,
                "ApplicableHeaderTradeSettlement/"
                "SpecifiedTradeSettlementHeaderMonetarySummation/GrandTotalAmount",
                "decimal",
            )
            for i, line in enumerate(nodes(base, "IncludedSupplyChainTradeLineItem")):
                for name, path in {
                    f.MODEL: "SpecifiedTradeProduct/Name",
                    f.SKU: "SpecifiedTradeProduct/SellerAssignedID",
                    f.QUANTITY: "SpecifiedLineTradeDelivery/BilledQuantity",
                    f.UNIT_PRICE_HT: "SpecifiedLineTradeAgreement/"
                    "NetPriceProductTradePrice/ChargeAmount",
                }.items():
                    emit(
                        f.line_field(i, name),
                        line,
                        path,
                        "decimal" if name in {f.QUANTITY, f.UNIT_PRICE_HT} else "text",
                    )
                for characteristic in nodes(
                    line, "SpecifiedTradeProduct/ApplicableProductCharacteristic"
                ):
                    descriptions = nodes(characteristic, "Description")
                    if descriptions and re.search(
                        r"serial|série", "".join(descriptions[0].itertext()), re.I
                    ):
                        emit(f.line_field(i, f.SERIAL), characteristic, "Value")
                for note in line.xpath(".//*[local-name()='IncludedNote']"):
                    match = re.search(r"S/N:\s*([\w-]+)", " ".join(note.itertext()), re.I)
                    if match:
                        add(f.line_field(i, f.SERIAL), match[1], root.getroottree().getpath(note))
        else:
            for field, path in {
                f.INVOICE_NUMBER: "ID",
                f.INVOICE_DATE: "IssueDate",
                f.SUPPLIER_NAME: "AccountingSupplierParty/Party/PartyName/Name",
                f.SUPPLIER_ADDRESS: "AccountingSupplierParty/Party/PostalAddress",
                f.CUSTOMER_NAME: "AccountingCustomerParty/Party/PartyName/Name",
                f.TOTAL_TTC: "LegalMonetaryTotal/TaxInclusiveAmount",
            }.items():
                emit(
                    field,
                    root,
                    path,
                    "date"
                    if field == f.INVOICE_DATE
                    else "decimal"
                    if field == f.TOTAL_TTC
                    else "text",
                )
            for i, line in enumerate(nodes(root, "InvoiceLine")):
                for name, path in {
                    f.MODEL: "Item/Name",
                    f.SKU: "Item/SellersItemIdentification/ID",
                    f.SERIAL: "Item/ItemInstance/SerialID",
                    f.QUANTITY: "InvoicedQuantity",
                    f.UNIT_PRICE_HT: "Price/PriceAmount",
                }.items():
                    emit(
                        f.line_field(i, name),
                        line,
                        path,
                        "decimal" if name in {f.QUANTITY, f.UNIT_PRICE_HT} else "text",
                    )
        for note in root.xpath(".//*[local-name()='IncludedNote' or local-name()='Note']"):
            text = " ".join(note.itertext())
            path = root.getroottree().getpath(note)
            if re.search(r"Warranty\+|extension de garantie", text, re.I):
                add(f.WARRANTY_EXTENSION_MENTIONED, True, path)
            duration = re.search(r"(\d+)\s*(?:mois|months)", text, re.I)
            if duration and re.search(r"garantie|warranty", text, re.I):
                add(f.WARRANTY_DURATION_MONTHS, int(duration[1]), path)
        return facts
