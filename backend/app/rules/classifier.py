import re
import unicodedata
from dataclasses import dataclass
from uuid import uuid5

from app.contracts.enums import FactSource
from app.contracts.models import Fact, Incident, Provenance


def normalize(value: str) -> str:
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(c)
        ).split()
    )


@dataclass(frozen=True)
class IncidentClassification:
    category: str
    confidence: float
    matched_keywords: tuple[str, ...]


class KeywordIncidentClassifier:
    """Priorité : réparation, liquide, accident, usure, vol, perte, abus, défaut."""

    keywords = {
        "third_party_repair": ("repare par un tiers", "reparateur", "third-party repair"),
        "liquid_damage": ("cafe", "eau", "liquide", "renverse", "coffee", "water", "spilled"),
        "accidental_damage": ("chute", "tombe", "fissure", "ecran casse", "dropped", "cracked"),
        "consumable_wear": (
            "coussinet",
            "mousse",
            "serre-tete use",
            "cordon use",
            "ear cushion",
            "worn",
        ),
        "theft": ("vole", "vol", "stolen"),
        "loss": ("perdu", "lost"),
        "misuse": ("mauvaise utilisation", "usage abusif", "misuse"),
        "defect": ("panne", "defaut", "defect", "failure"),
    }

    def classify(self, description: str) -> IncidentClassification:
        value = normalize(description)
        for category, keywords in self.keywords.items():
            matched = tuple(k for k in keywords if re.search(r"\b" + re.escape(k) + r"\b", value))
            if matched:
                hedged = any(k in value for k in ("peut-etre", "maybe", "je crois", "possibly"))
                return IncidentClassification(category, 0.6 if hedged else 0.9, matched)
        return IncidentClassification("defect", 0.5, ())

    def to_fact(self, incident: Incident) -> Fact:
        """L'identifiant d'incident tient lieu de document exigé par le contrat Fact."""
        result = self.classify(incident.description)
        return Fact(
            id=uuid5(incident.id, "incident_category"),
            equipment_id=incident.equipment_id,
            document_id=incident.id,
            field="incident_category",
            value=result.category,
            confidence=result.confidence,
            source=FactSource.STRUCTURED,
            provenance=Provenance(
                id=uuid5(incident.id, "incident_category:provenance"),
                document_id=incident.id,
                excerpt=", ".join(result.matched_keywords) or incident.description[:200],
            ),
        )
