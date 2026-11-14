import json
from pathlib import Path

import pytest

from app.contracts.models import Equipment, Fact, Incident, Right
from app.ingestion.normalize import normalize_facts
from app.rules import DEFAULT_RULES_DIR, DEMO_REFERENCE_DATE, DeterministicRulesEngine, load_rules


def test_appelia_traps() -> None:
    path = Path(__file__).resolve().parents[4] / "data" / "appelia" / "traps.json"
    if not path.exists():
        pytest.skip("traps.json pas encore livré par L1")
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases", data.get("traps")) if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        pytest.skip("Format traps.json non encore défini par L1")
    for case in cases:
        if (
            not isinstance(case, dict)
            or not {"equipment", "incident", "facts", "expected_verdict"} <= case.keys()
        ):
            pytest.skip("Format traps.json non encore défini par L1")
        equipment = Equipment.model_validate(case["equipment"])
        result = DeterministicRulesEngine(DEMO_REFERENCE_DATE).evaluate(
            equipment,
            normalize_facts([Fact.model_validate(f) for f in case["facts"]], equipment),
            Incident.model_validate(case["incident"]),
            load_rules(DEFAULT_RULES_DIR),
            [Right.model_validate(r) for r in case.get("rights", [])],
        )
        assert result.value == case["expected_verdict"]
