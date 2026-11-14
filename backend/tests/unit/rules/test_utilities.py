from datetime import date
from pathlib import Path

import pytest
import yaml

from app.rules import DEFAULT_RULES_DIR, KeywordIncidentClassifier, add_months, load_rules
from tests.unit.rules.test_engine_cases import incident


def test_loader_merges_and_duplicates(tmp_path: Path) -> None:
    rules = load_rules(DEFAULT_RULES_DIR)
    assert len(rules) >= 17
    assert len({r.id for r in rules}) == len(rules)
    assert next(r for r in rules if r.id == "jabra-evolve").duration_months == 24
    assert yaml.safe_load("base: &base {a: 1}\nmerged: {<<: *base, b: 2}")["merged"] == {
        "a": 1,
        "b": 2,
    }
    data = {"rules": [rules[0].model_dump(mode="json")] * 2}
    (tmp_path / "duplicate.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="dupliqué"):
        load_rules(tmp_path)
    (tmp_path / "duplicate.yaml").write_text("rules: [{}]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_rules(tmp_path)


@pytest.mark.parametrize(
    "start,months,end",
    [
        (date(2025, 1, 31), 1, date(2025, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2024, 2, 29), 12, date(2025, 2, 28)),
        (date(2025, 12, 31), 2, date(2026, 2, 28)),
    ],
)
def test_add_months(start: date, months: int, end: date) -> None:
    assert add_months(start, months) == end


@pytest.mark.parametrize(
    "text,category,confidence",
    [
        ("CAFÉ renversé", "liquid_damage", 0.9),
        ("Maybe water spilled", "liquid_damage", 0.6),
        ("Je crois qu'il est tombé", "accidental_damage", 0.6),
        ("écran cassé", "accidental_damage", 0.9),
        ("dropped and cracked", "accidental_damage", 0.9),
        ("coussinet usé", "consumable_wear", 0.9),
        ("worn ear cushion", "consumable_wear", 0.9),
        ("réparé par un tiers", "third_party_repair", 0.9),
        ("third-party repair", "third_party_repair", 0.9),
        ("volé", "theft", 0.9),
        ("lost", "loss", 0.9),
        ("misuse", "misuse", 0.9),
        ("", "defect", 0.5),
        ("water and dropped", "liquid_damage", 0.9),
    ],
)
def test_classifier(text: str, category: str, confidence: float) -> None:
    classifier = KeywordIncidentClassifier()
    result = classifier.classify(text)
    assert (result.category, result.confidence) == (category, confidence)
    assert result == classifier.classify(text)
    event = incident()
    output = classifier.to_fact(event)
    assert output.document_id == event.id
    assert output.source == "structured"
    assert output.model_dump() == classifier.to_fact(event).model_dump()
