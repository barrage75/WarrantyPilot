from pathlib import Path

import yaml

from app.contracts.models import Rule

RULES_DIR = Path(__file__).resolve().parents[2] / "app" / "rules" / "rules"


def _load() -> list[Rule]:
    rules: list[Rule] = []
    for path in sorted(RULES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        rules.extend(
            Rule.model_validate({k: v for k, v in item.items() if not k.startswith("<<")})
            for item in data["rules"]
        )
    return rules


def test_rule_files_validate_against_contract() -> None:
    rules = _load()
    assert len(rules) >= 17
    assert len({rule.id for rule in rules}) == len(rules)


def test_jabra_contact_delay_is_never_known() -> None:
    for rule in _load():
        if rule.applies_to.brand == "Jabra" and rule.contact_delay_days is not None:
            assert rule.contact_delay_start.value == "unspecified"


def test_warranty_plus_goes_to_jabra_support_with_certificate() -> None:
    rule = next(rule for rule in _load() if rule.id == "jabra-warranty-plus")
    assert rule.channel.value == "email_manufacturer_support"
    assert rule.requires_certificate
    assert rule.start_event.value == "standard_warranty_end"


def test_refurbished_is_180_days() -> None:
    rule = next(rule for rule in _load() if rule.id == "jabra-refurbished")
    assert rule.duration_days == 180
    assert rule.applies_to.condition == "refurbished"
