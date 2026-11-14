from pathlib import Path
from typing import Any, cast

import yaml

from app.contracts.enums import Priority
from app.contracts.models import Settings

FEATURE_FILE = Path(__file__).parents[3] / "config" / "features.yaml"


class FeatureConfigurationError(ValueError):
    pass


def load_features(path: Path = FEATURE_FILE) -> dict[str, dict[str, Any]]:
    try:
        value: object = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise FeatureConfigurationError(f"cannot load feature configuration: {error}") from error
    if not isinstance(value, dict):
        raise FeatureConfigurationError("features.yaml must contain a features mapping")
    feature_values = value.get("features")
    if not isinstance(feature_values, dict):
        raise FeatureConfigurationError("features.yaml must contain a features mapping")
    features: dict[str, dict[str, Any]] = {}
    for name, feature in feature_values.items():
        if not isinstance(name, str):
            raise FeatureConfigurationError("feature names must be strings")
        if not isinstance(feature, dict):
            raise FeatureConfigurationError(f"feature {name} must be a mapping")
        try:
            Priority(feature["priority"])
        except (KeyError, ValueError) as error:
            raise FeatureConfigurationError(f"feature {name} has an invalid priority") from error
        if not isinstance(feature.get("default_enabled"), bool):
            raise FeatureConfigurationError(f"feature {name} must define default_enabled")
        features[name] = feature
    return features


def is_enabled(name: str, settings: Settings | None = None, path: Path = FEATURE_FILE) -> bool:
    features = load_features(path)
    if name not in features:
        raise KeyError(f"unknown feature: {name}")
    feature = features[name]
    if feature["priority"] == Priority.P0.value:
        return True
    overrides = (settings or Settings()).feature_flags
    return overrides.get(name, cast(bool, feature["default_enabled"]))
