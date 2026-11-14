from __future__ import annotations

import hashlib
import json
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
    assert len(annotations) == 10

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
    assert len(trap_data["demo_cases"]) == 2

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
    assert all(
        person.email and person.email.endswith("@appelia.example")
        for person in dataset.people
    )
    people_by_name = {person.name: person for person in dataset.people}
    assert people_by_name["Paul Martin"].role == "technicien plateau"
    assert people_by_name["Karim Benali"].role == "responsable informatique"
    assert people_by_name["Claire Dubois"].role == "DAF"
