from pathlib import Path

import yaml

from app.contracts.models import Rule

DEFAULT_RULES_DIR = Path(__file__).parent / "rules"


def load_rules(directory: Path | str) -> list[Rule]:
    rules: list[Rule] = []
    seen: set[str] = set()
    for path in sorted(Path(directory).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for item in data["rules"]:
            rule = Rule.model_validate({key: value for key, value in item.items() if key != "<<"})
            if rule.id in seen:
                raise ValueError(f"Identifiant de règle dupliqué : {rule.id}")
            seen.add(rule.id)
            rules.append(rule)
    return rules
