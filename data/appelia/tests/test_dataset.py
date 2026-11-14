from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.contracts.models import Document, Equipment, Person
from appelia.generate import HIDDEN_PROMPT, generate_dataset
from appelia.load import load_dataset
from pypdf import PdfReader

DATA_DIRECTORY = Path(__file__).resolve().parents[1]
XML_NAMESPACES = {
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


def _read_json(filename: str) -> Any:
    return json.loads((DATA_DIRECTORY / filename).read_text(encoding="utf-8"))


def _hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _xml_text(element: ElementTree.Element, path: str) -> str:
    value = element.findtext(path, namespaces=XML_NAMESPACES)
    assert value is not None
    return value


def test_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_dataset(first)
    generate_dataset(second)
    assert _hashes(first) == _hashes(second)


def test_invoice_serials_match_equipment() -> None:
    equipment = _read_json("equipment.json")
    annotations = _read_json("annotations.json")
    equipment_by_serial = {item["serial"]: item for item in equipment}
    invoiced_serials: set[str] = set()

    for annotation in annotations:
        for line in annotation["lines"]:
            for serial in line["serials"]:
                assert serial in equipment_by_serial
                invoiced_serials.add(serial)

    expected_serials = {
        item["serial"] for item in equipment if item["invoice_number"] is not None
    }
    assert invoiced_serials == expected_serials


def test_facturx_xml_matches_annotations() -> None:
    annotations = [
        item for item in _read_json("annotations.json") if item["format"] == "facturx"
    ]
    suppliers = {item["id"]: item for item in _read_json("suppliers.json")}
    assert len(annotations) == 12

    for annotation in annotations:
        reader = PdfReader(str(DATA_DIRECTORY / annotation["filename"]))
        xml_attachments = [
            content
            for name, contents in reader.attachments.items()
            if name.lower().endswith(".xml")
            for content in contents
        ]
        assert len(xml_attachments) == 1
        root = ElementTree.fromstring(xml_attachments[0])

        assert (
            _xml_text(root, ".//rsm:ExchangedDocument/ram:ID")
            == annotation["invoice_number"]
        )
        issue_date = _xml_text(root, ".//ram:IssueDateTime/udt:DateTimeString")
        assert (
            f"{issue_date[:4]}-{issue_date[4:6]}-{issue_date[6:]}"
            == annotation["invoice_date"]
        )
        assert (
            _xml_text(root, ".//ram:SellerTradeParty/ram:Name")
            == annotation["supplier_name"]
        )
        assert (
            _xml_text(root, ".//ram:BuyerTradeParty/ram:Name")
            == annotation["client_name"]
        )

        supplier = suppliers[annotation["supplier_id"]]
        address = root.find(
            ".//ram:SellerTradeParty/ram:PostalTradeAddress", XML_NAMESPACES
        )
        assert address is not None
        xml_address = (
            f"{_xml_text(address, 'ram:LineOne')}, "
            f"{_xml_text(address, 'ram:PostcodeCode')} "
            f"{_xml_text(address, 'ram:CityName')}, France"
        )
        assert xml_address == annotation["supplier_address"]
        assert xml_address == (
            f"{supplier['address']}, {supplier['postal_code']} {supplier['city']}, France"
        )

        xml_lines = root.findall(
            ".//ram:IncludedSupplyChainTradeLineItem", XML_NAMESPACES
        )
        assert len(xml_lines) == len(annotation["lines"])
        for xml_line, expected in zip(xml_lines, annotation["lines"], strict=True):
            product = xml_line.find("ram:SpecifiedTradeProduct", XML_NAMESPACES)
            assert product is not None
            assert _xml_text(product, "ram:Name") == expected["model"]
            assert _xml_text(product, "ram:SellerAssignedID") == expected["sku"]
            description = _xml_text(product, "ram:Description")
            for serial in expected["serials"]:
                assert serial in description
            if expected["warranty_term_months"] is not None:
                assert (
                    f"garantie {expected['warranty_term_months'] // 12} ans Dell Basic Onsite"
                    in description
                )
            assert (
                int(
                    _xml_text(
                        xml_line,
                        "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity",
                    )
                )
                == expected["qty"]
            )
            assert (
                _xml_text(
                    xml_line,
                    "ram:SpecifiedLineTradeAgreement/"
                    "ram:NetPriceProductTradePrice/ram:ChargeAmount",
                )
                == expected["unit_price_ht"]
            )

        total_ttc = _xml_text(
            root,
            ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount",
        )
        assert total_ttc == annotation["total_ttc"]
        warranty_note = _xml_text(root, ".//ram:IncludedNote/ram:Content")
        assert ("oui" in warranty_note) is annotation["has_warranty_plus"]


def test_traps_reference_existing_equipment_and_documents() -> None:
    trap_data = _read_json("traps.json")
    equipment_ids = {item["id"] for item in _read_json("equipment.json")}
    assert len(trap_data["traps"]) == 15
    assert {trap["id"] for trap in trap_data["traps"]} == set(range(1, 16))
    assert len(trap_data["demo_cases"]) == 3
    assert all(
        trap["expected_channel"] == "manual"
        for trap in trap_data["traps"]
        if trap["expected_verdict"] == "to_verify"
    )
    traps_by_id = {trap["id"]: trap for trap in trap_data["traps"]}
    assert traps_by_id[4]["expected_channel"] == "email_lessor"
    assert traps_by_id[10]["expected_channel"] == "email_manufacturer_support"
    assert traps_by_id[13]["expected_channel"] == "browser_portal"
    assert all(
        traps_by_id[trap_id]["expected_channel"] == "email_reseller"
        for trap_id in (2, 3, 5, 9, 11)
    )

    assert all(
        case["expected_channel"] == "email_reseller"
        for case in trap_data["demo_cases"]
        if case["id"] == "demo-paul-martin"
    )
    assert all(
        case["expected_channel"] == "browser_portal"
        for case in trap_data["demo_cases"]
        if case["id"] == "demo-dell-latitude-7440"
    )
    missing_term_case = next(
        case
        for case in trap_data["demo_cases"]
        if case["id"] == "demo-dell-no-warranty-term"
    )
    assert missing_term_case["expected_verdict"] == "to_verify"
    assert missing_term_case["expected_channel"] == "manual"

    for case in [*trap_data["traps"], *trap_data["demo_cases"]]:
        case_equipment_ids = case.get("equipment_ids", [case["equipment_id"]])
        for equipment_id in case_equipment_ids:
            assert equipment_id in equipment_ids
        for filename in case["documents"]:
            assert (DATA_DIRECTORY / filename).is_file()

    duplicate = trap_data["traps"][4]["documents"]
    assert (
        hashlib.sha256((DATA_DIRECTORY / duplicate[0]).read_bytes()).digest()
        == hashlib.sha256((DATA_DIRECTORY / duplicate[1]).read_bytes()).digest()
    )


def test_dell_prosupport_rights_match_contract() -> None:
    dataset = load_dataset()
    prosupport = next(
        item
        for item in dataset.documents
        if item.filename.endswith("contrat-dell-prosupport.pdf")
    )
    contract_text = (
        PdfReader(str(DATA_DIRECTORY / prosupport.filename)).pages[0].extract_text()
    )
    contracted_serials = set(
        re.findall(
            r"\b[A-Z0-9]{7}\b", contract_text.split("Numéros de série couverts :")[-1]
        )
    )
    equipment_by_id = {item.id: item for item in dataset.equipment}
    rights_serials = {
        equipment_by_id[right.equipment_id].serial
        for right in dataset.rights
        if right.rule_id == "dell-prosupport"
    }
    assert rights_serials == contracted_serials


def test_hidden_instruction_is_extractable_but_white() -> None:
    trap = next(item for item in _read_json("traps.json")["traps"] if item["id"] == 6)
    invoice_path = DATA_DIRECTORY / trap["documents"][0]
    page = PdfReader(str(invoice_path)).pages[0]
    assert HIDDEN_PROMPT in (page.extract_text() or "")

    page_content = page.get_contents()
    assert page_content is not None
    content = page_content.get_data()
    prompt_position = content.index(HIDDEN_PROMPT.encode("ascii"))
    white_position = content.rfind(b"1 1 1 rg", 0, prompt_position)
    black_position = content.rfind(b"0 0 0 rg", 0, prompt_position)
    assert white_position > black_position


def test_loader_validates_contract_models() -> None:
    dataset = load_dataset()
    assert len(dataset.people) == 200
    assert len(dataset.equipment) == 230
    assert len(dataset.documents) == 65
    assert dataset.facts
    assert dataset.rights
    demo_dell = next(
        item for item in dataset.equipment_records if item["scenario"] == "demo-dell"
    )
    assert demo_dell["serial"] == "7XK4L93"
    equipment_records = dataset.equipment_records
    assert sum(item["category"] == "headset" for item in equipment_records) == 150
    assert sum(item["category"] == "laptop" for item in equipment_records) == 50
    assert sum(item["category"] == "monitor" for item in equipment_records) == 15
    assert sum(item["category"] == "printer" for item in equipment_records) == 10
    assert sum(item["category"] == "other" for item in equipment_records) == 5
    assert all(isinstance(item, Person) for item in dataset.people)
    assert all(isinstance(item, Equipment) for item in dataset.equipment)
    assert all(
        isinstance(item, Document) and item.untrusted for item in dataset.documents
    )
    paul_case = next(
        item for item in dataset.demo_cases if item["id"] == "demo-paul-martin"
    )
    paul_equipment = next(
        item for item in dataset.equipment_records if item["id"] == paul_case["equipment_id"]
    )
    paul_invoice = next(
        item for item in dataset.annotations if item["filename"] == paul_case["documents"][0]
    )
    assert paul_invoice["format"] == "facturx"
    assert paul_invoice["invoice_date"] == "2025-03-20"
    assert paul_equipment["purchase_date"] == "2025-03-20"
    assert paul_equipment["delivery_date"] == "2025-03-24"
    paul_invoice_dates = [
        fact.value
        for fact in dataset.facts
        if fact.equipment_id is not None
        and str(fact.equipment_id) == paul_equipment["id"]
        and fact.field == "invoice_date"
    ]
    assert paul_invoice_dates and set(paul_invoice_dates) == {"2025-03-20"}
    assert all(
        item["condition"] in {"new", "refurbished"} for item in equipment_records
    )
    assert all(
        item["condition"] == "refurbished"
        for item in equipment_records
        if item["refurbished"]
    )
    annotations = _read_json("annotations.json")
    equipment_by_serial = {item["serial"]: item for item in equipment_records}
    for annotation in annotations:
        is_dell_invoice = any(
            equipment_by_serial[serial]["brand"] == "Dell"
            for line in annotation["lines"]
            for serial in line["serials"]
        )
        if is_dell_invoice:
            for line in annotation["lines"]:
                for serial in line["serials"]:
                    assert (
                        line["warranty_term_months"]
                        == equipment_by_serial[serial]["warranty_months"]
                    )
            warranty_terms = {
                line["warranty_term_months"]
                for line in annotation["lines"]
                if line["warranty_term_months"] is not None
            }
            expected_invoice_term = (
                next(iter(warranty_terms)) if len(warranty_terms) == 1 else None
            )
            assert annotation["warranty_term_months"] == expected_invoice_term
    docs_by_filename = {item["filename"]: item for item in _read_json("documents.json")}
    for filename in (
        "documents/jabra-warranty-plus-001.pdf",
        "documents/jabra-warranty-plus-002.pdf",
    ):
        assert docs_by_filename[filename]["extension_months"] == 12
        certificate_text = (
            PdfReader(str(DATA_DIRECTORY / filename)).pages[0].extract_text() or ""
        )
        assert "extension_months : 12 mois" in certificate_text
    assert (
        docs_by_filename["documents/contrat-dell-prosupport.pdf"]["extension_months"]
        == 36
    )
    prosupport_text = (
        PdfReader(str(DATA_DIRECTORY / "documents/contrat-dell-prosupport.pdf"))
        .pages[0]
        .extract_text()
        or ""
    )
    assert "extension_months : 36 mois" in prosupport_text
    no_term_equipment = next(
        item for item in equipment_records if item["scenario"] == "demo-dell-no-term"
    )
    assert no_term_equipment["warranty_months"] is None
    assert all(
        person.email and person.email.endswith("@appelia.example")
        for person in dataset.people
    )
    people_by_name = {person.name: person for person in dataset.people}
    assert people_by_name["Paul Martin"].role == "technicien plateau"
    assert people_by_name["Karim Benali"].role == "responsable informatique"
    assert str(people_by_name["Karim Benali"].id) == "97225c38-d686-5d99-a6cf-53e18aa92e8d"
    assert people_by_name["Karim Benali"].email == "karim.benali.002@appelia.example"
    assert people_by_name["Claire Dubois"].role == "DAF"


def test_jabra_invoice_pdfs_show_required_purchase_proof() -> None:
    annotations = _read_json("annotations.json")
    suppliers = {item["id"]: item for item in _read_json("suppliers.json")}
    equipment = {item["serial"]: item for item in _read_json("equipment.json")}
    jabra_invoices = [
        item for item in annotations if item["supplier_id"] == "SUP-AUDIO"
    ]
    assert jabra_invoices

    for annotation in jabra_invoices:
        text = (
            PdfReader(str(DATA_DIRECTORY / annotation["filename"]))
            .pages[0]
            .extract_text()
            or ""
        )
        supplier = suppliers[annotation["supplier_id"]]
        assert supplier["name"] in text
        assert supplier["address"] in text
        assert annotation["invoice_number"] in text
        invoice_date = annotation["invoice_date"]
        assert f"{invoice_date[8:10]}/{invoice_date[5:7]}/{invoice_date[:4]}" in text
        for line in annotation["lines"]:
            assert line["model"] in text
            assert line["sku"] in text
            assert all(
                equipment[serial]["brand"] == "Jabra" for serial in line["serials"]
            )


def test_dell_invoice_warranty_terms_are_present_or_explicitly_missing() -> None:
    annotations = _read_json("annotations.json")
    equipment = {item["serial"]: item for item in _read_json("equipment.json")}
    dell_annotations = [
        annotation
        for annotation in annotations
        if any(
            equipment[serial]["brand"] == "Dell"
            for line in annotation["lines"]
            for serial in line["serials"]
        )
    ]
    missing_terms = []

    for annotation in dell_annotations:
        warranty_terms = {
            line["warranty_term_months"]
            for line in annotation["lines"]
            if line["warranty_term_months"] is not None
        }
        expected_invoice_term = (
            next(iter(warranty_terms)) if len(warranty_terms) == 1 else None
        )
        assert annotation["warranty_term_months"] == expected_invoice_term
        path = DATA_DIRECTORY / annotation["filename"]
        if annotation["format"] == "pdf":
            text = PdfReader(str(path)).pages[0].extract_text() or ""
        else:
            reader = PdfReader(str(path))
            xml_content = next(
                contents[0]
                for name, contents in reader.attachments.items()
                if name.lower().endswith(".xml")
            )
            xml_root = ElementTree.fromstring(xml_content)
            text = " ".join(
                element.text or ""
                for element in xml_root.findall(".//ram:Description", XML_NAMESPACES)
            )
        for line in annotation["lines"]:
            for serial in line["serials"]:
                term_months = line["warranty_term_months"]
                if term_months is None:
                    missing_terms.append(serial)
                    assert equipment[serial]["scenario"] == "demo-dell-no-term"
                    assert "Dell Basic Onsite" not in text
                else:
                    assert term_months in {24, 36}
                    expected_term = (
                        f"garantie {term_months // 12} ans dell basic onsite"
                    )
                    normalized_text = " ".join(text.lower().replace(":", "").split())
                    assert expected_term in normalized_text

    assert len(missing_terms) == 1
    assert equipment[missing_terms[0]]["scenario"] == "demo-dell-no-term"
