from collections.abc import Callable
from datetime import date, datetime, timedelta
from fnmatch import fnmatchcase

from app.contracts.enums import Channel, FactField, RightType, VerdictValue
from app.contracts.models import (
    Equipment,
    Fact,
    Incident,
    Provenance,
    Right,
    Rule,
    RuleCheck,
    Verdict,
)
from app.rules.classifier import KeywordIncidentClassifier, normalize
from app.rules.dates import add_months

DEMO_REFERENCE_DATE = date(2026, 11, 20)
CHECK_NAMES = (
    "lease",
    "suspicious_signal",
    "equipment_identity",
    "buyer",
    "document_conflict",
    "rule_match",
    "purchase_proof",
    "start_date",
    "end_date",
    "extension",
    "exclusions",
    "contact_delay",
)
DATE_FIELDS = {"purchase_date", "invoice_date", "delivery_date", "ship_date"}
FACT_LABELS = {
    "purchase_date": "Date d'achat",
    "invoice_date": "Date de facture",
    "delivery_date": "Date de livraison",
    "ship_date": "Date d'expédition",
    "standard_warranty_end": "Fin de garantie standard",
    "warranty_term_months": "Durée de garantie",
    "extension_months": "Durée de l'extension de garantie",
    "serial_number": "Numéro de série",
    "reseller_name": "Nom du revendeur",
    "reseller_address": "Adresse du revendeur",
    "product_type": "Type de produit",
    "model_number": "Modèle",
    "warranty_plus_certificate": "Certificat Warranty+",
    "sku": "Référence produit",
    "lease_contract": "Contrat de location",
}
EXCLUSION_LABELS = {
    "third_party_repair": "réparation par un tiers",
    "liquid_damage": "dommage causé par un liquide",
    "accidental_damage": "dommage accidentel",
    "consumable_wear": "usure d'un consommable",
    "theft": "vol",
    "loss": "perte",
    "misuse": "mauvaise utilisation",
}


def _fact_label(name: str) -> str:
    return FACT_LABELS.get(name, name.replace("_", " "))


def fact_value(fact: Fact) -> str | int | bool | date:
    value = fact.value
    if fact.field in DATE_FIELDS:
        if isinstance(value, date):
            return value
        for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(value), pattern).date()
            except ValueError:
                continue
        return str(value)
    if fact.field in {"warranty_term_months", "extension_months"}:
        try:
            return int(value)
        except (ValueError, TypeError):
            return str(value)
    if isinstance(value, bool):
        return value
    return normalize(str(value))


def truthy(fact: Fact | None) -> bool:
    return fact is not None and fact_value(fact) in (True, "true")


def _page_reference(page: int | None) -> str:
    return f" p. {page}" if page is not None else ""


def specificity(rule: Rule) -> tuple[bool, int, str]:
    pattern = rule.applies_to.model_glob
    prefix = next((i for i, c in enumerate(pattern) if c in "*?["), len(pattern))
    return prefix != len(pattern), -prefix, rule.id


def _guard_coverage(value: VerdictValue, proof: Fact | None, rule: Rule | None) -> None:
    if value == VerdictValue.COVERED and (proof is None or rule is None):
        raise RuntimeError("Couverture impossible sans preuve d'achat et règle fabricant")


class DeterministicRulesEngine:
    def __init__(
        self,
        today: date | Callable[[], date],
        *,
        portal_url: str = "http://127.0.0.1:8100/support",
        company_name: str | None = "Appelia",
        classifier: KeywordIncidentClassifier | None = None,
    ) -> None:
        self.today = today
        self.portal_url = portal_url
        self.company_name = company_name
        self.classifier = classifier

    def evaluate(
        self,
        equipment: Equipment,
        facts: list[Fact],
        incident: Incident,
        rules: list[Rule],
        rights: list[Right],
        *,
        dates: dict[str, date] | None = None,
    ) -> Verdict:
        today = self.today() if callable(self.today) else self.today
        usable = [
            f for f in facts if f.equipment_id in (None, equipment.id) and f.confidence >= 0.5
        ]
        fields: dict[str, list[Fact]] = {}
        for fact in usable:
            fields.setdefault(fact.field, []).append(fact)
        evidence: list[Provenance] = []
        checks = {
            name: RuleCheck(name=name, passed=None, detail="Non évalué") for name in CHECK_NAMES
        }
        missing: list[str] = []
        possible: list[str] = []

        def use(fact: Fact | None) -> Fact | None:
            if fact is not None and fact.provenance not in evidence:
                evidence.append(fact.provenance)
            return fact

        def get(name: str) -> Fact | None:
            values = fields.get(name, [])
            return use(values[0]) if values else None

        def check(name: str, passed: bool | None, detail: str) -> None:
            checks[name] = RuleCheck(name=name, passed=passed, detail=detail)

        condition = get("condition")
        refurbished = condition is not None and fact_value(condition) == "refurbished"
        matches = sorted(
            [
                r
                for r in rules
                if r.applies_to.brand.casefold() == equipment.brand.casefold()
                and fnmatchcase(equipment.model.casefold(), r.applies_to.model_glob.casefold())
                and (r.applies_to.condition != "refurbished" or refurbished)
            ],
            key=specificity,
        )
        bases = [r for r in matches if r.right_type == RightType.MANUFACTURER_WARRANTY]
        special = [r for r in bases if r.applies_to.condition == "refurbished"]
        candidates = special or bases
        rule: Rule | None = candidates[0] if candidates else None
        proof: Fact | None = None

        def finish(value: VerdictValue, reason: str, english: str) -> Verdict:
            _guard_coverage(value, proof, rule)
            channel = rule.channel if rule else Channel.MANUAL
            return Verdict(
                value=value,
                channel=channel,
                target_url=self.portal_url if channel == Channel.BROWSER_PORTAL else None,
                rule_id=rule.id if rule else None,
                rule_version=rule.version if rule else None,
                checks=list(checks.values()),
                evidence=evidence,
                missing=missing,
                possible_exclusions=possible,
                explanation_fr=reason,
                explanation_en=english,
            )

        def verify(reason: str, english: str) -> Verdict:
            return finish(VerdictValue.TO_VERIFY, "À vérifier : " + reason, "To verify: " + english)

        own_rights = [r for r in rights if r.equipment_id == equipment.id]
        lease = next((r for r in matches if r.right_type == RightType.LEASE_CONTRACT), None)
        lease_rights = [r for r in own_rights if r.right_type == RightType.LEASE_CONTRACT]
        if lease and (truthy(get("lease_contract")) or lease_rights):
            rule = lease
            for right in lease_rights:
                evidence.extend(p for p in right.evidence if p not in evidence)
            check("lease", True, "Contrat de location prouvé : contacter le bailleur")
            return finish(
                VerdictValue.OUT_OF_MANUFACTURER,
                "Matériel loué : contacter le bailleur.",
                "Leased equipment: contact the lessor.",
            )
        check(
            "lease",
            False,
            "Règle de location sans preuve, poursuite" if lease else "Aucune location prouvée",
        )
        security_signal = get(FactField.SECURITY_SUSPICIOUS.value)
        if (security_signal is not None and bool(security_signal.value)) or truthy(
            get("suspicious")
        ):
            check("suspicious_signal", False, "Signal suspect dans les documents")
            return verify("signal suspect", "suspicious document signal")
        check("suspicious_signal", True, "Aucun signal suspect")
        ambiguous = truthy(get("equipment_ambiguous"))
        for name, expected in (
            ("serial_number", equipment.serial),
            ("brand", equipment.brand),
            ("model_number", equipment.model),
        ):
            for fact in fields.get(name, []):
                use(fact)
                ambiguous |= normalize(str(fact.value)).replace(" ", "") != normalize(
                    expected
                ).replace(" ", "")
        check(
            "equipment_identity",
            not ambiguous,
            "Identité contradictoire ou ambiguë" if ambiguous else "Identité cohérente",
        )
        if ambiguous:
            return verify("identité de l'équipement ambiguë", "ambiguous equipment identity")
        buyer = get("buyer_name")
        other = (
            buyer is not None
            and self.company_name is not None
            and normalize(self.company_name) not in normalize(str(buyer.value))
        )
        check(
            "buyer",
            not other,
            "Acheteur différent" if other else "Acheteur compatible ou non renseigné",
        )
        if other:
            return verify("acheteur différent", "different buyer")
        for name in sorted(
            DATE_FIELDS | {"warranty_term_months", "extension_months", "serial_number"}
        ):
            values = fields.get(name, [])
            if len({str(fact_value(f)).replace(" ", "") for f in values}) > 1:
                for fact in values:
                    use(fact)
                detail = "; ".join(f"{f.value}{_page_reference(f.provenance.page)}" for f in values)
                check("document_conflict", False, f"Conflit — {_fact_label(name)} : {detail}")
                return verify(
                    f"documents contradictoires : {detail}", f"conflicting documents: {detail}"
                )
        check("document_conflict", True, "Aucun conflit documentaire")
        if not bases:
            check("rule_match", False, "Modèle sans règle fabricant")
            return verify("modèle sans règle", "model without a warranty rule")
        if rule is None:
            raise RuntimeError("Règle fabricant absente après sélection")
        check(
            "rule_match",
            True,
            f"{rule.id} version {rule.version}, motif {rule.applies_to.model_glob}",
        )
        proof = get("purchase_date") or get("invoice_date")
        if proof is None or not isinstance(fact_value(proof), date):
            missing.append("purchase_date")
            check("purchase_proof", False, "Preuve d'achat datée absente ou invalide")
            return verify("preuve d'achat absente", "missing purchase proof")
        purchase = fact_value(proof)
        if not isinstance(purchase, date):
            raise RuntimeError("Date d'achat invalide après validation de la preuve")
        if dates is not None:
            dates["purchase_date"] = purchase
        missing.extend(
            name for name in rule.proof_required if name not in fields and name != "purchase_date"
        )
        missing_labels = ", ".join(_fact_label(name) for name in missing)
        check(
            "purchase_proof",
            True,
            "Preuve d'achat présente"
            + (f" ; avertissement : champs absents {missing_labels}" if missing else ""),
        )
        months = rule.duration_months
        if not rule.duration_days and not months:
            term = get("warranty_term_months")
            duration = fact_value(term) if term else None
            if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
                missing[:] = ["warranty_term_months"]
                return verify("durée de garantie absente", "missing warranty duration")
            months = duration
        event = rule.start_event.value
        start_fact = get(event)
        start = fact_value(start_fact) if start_fact else None
        approximated = False
        origin = _fact_label(event)
        if not isinstance(start, date):
            start = (
                getattr(equipment, event, None) if event in {"ship_date", "delivery_date"} else None
            )
            approximated = True
            origin += " (inventaire)"
        if not isinstance(start, date):
            invoice = get("invoice_date")
            fallback = invoice if invoice and isinstance(fact_value(invoice), date) else proof
            start = fact_value(fallback)
            origin = _fact_label(fallback.field)
        if not isinstance(start, date):
            raise RuntimeError("Date de départ invalide après résolution")
        check(
            "start_date",
            today >= start,
            f"{origin} : {start:%d/%m/%Y}" + (" (date estimée)" if approximated else ""),
        )
        if today < start:
            return verify(
                f"garantie non commencée (début le {start:%d/%m/%Y})",
                f"warranty has not started (starts on {start:%d/%m/%Y})",
            )
        end = (
            start + timedelta(days=rule.duration_days - 1)
            if rule.duration_days
            else add_months(start, months) - timedelta(days=1)
        )
        check("end_date", today <= end, f"Dernier jour couvert : {end:%d/%m/%Y} (inclus)")
        exclusions = set(rule.exclusions)
        duration_label = f"{rule.duration_days} jours" if rule.duration_days else f"{months} mois"
        duration_english = (
            f"{rule.duration_days} days" if rule.duration_days else f"{months} months"
        )
        check("extension", None, "Extension non nécessaire ou sans preuve")
        coverage_end = end
        for extension in (r for r in matches if r.right_type == RightType.EXTENSION):
            certificate = get(
                "warranty_plus_certificate"
                if extension.requires_certificate
                else "service_contract"
            )
            extension_right = next(
                (
                    r
                    for r in own_rights
                    if r.right_type == RightType.EXTENSION and r.rule_id == extension.id
                ),
                None,
            )
            if not truthy(certificate) and extension_right is None:
                continue
            if extension_right:
                evidence.extend(p for p in extension_right.evidence if p not in evidence)
                if (
                    today < extension_right.start_date
                    and extension_right.start_date > end + timedelta(days=1)
                ):
                    check(
                        "extension",
                        False,
                        f"Extension non commencée : {extension_right.start_date:%d/%m/%Y}",
                    )
                    continue
                extended_end = extension_right.end_date
                extension_label = "extension contractuelle"
                extension_english = "contractual extension"
            else:
                term = get("extension_months")
                duration = fact_value(term) if term else None
                if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
                    check("extension", False, "Preuve présente mais durée d'extension absente")
                    if today > end:
                        missing[:] = ["extension_months"]
                        return verify("durée d'extension absente", "missing extension duration")
                    continue
                extended_end = add_months(end + timedelta(days=1), duration) - timedelta(days=1)
                extension_label = f"extension de {duration} mois"
                extension_english = f"{duration} month extension"
            check(
                "extension",
                today <= extended_end,
                f"{extension.id} jusqu'au {extended_end:%d/%m/%Y}",
            )
            if today <= extended_end:
                coverage_end = max(end, extended_end)
                if today > end:
                    rule = extension
                    end = extended_end
                    duration_label = extension_label
                    duration_english = extension_english
                    exclusions.update(extension.exclusions)
                    check(
                        "rule_match",
                        True,
                        f"{rule.id} version {rule.version}, motif {rule.applies_to.model_glob}",
                    )
                break
        if dates is not None:
            dates["warranty_end"] = coverage_end
        categories = fields.get("incident_category", [])
        if not categories and self.classifier:
            categories = [self.classifier.to_fact(incident)]
        certain: list[str] = []
        for fact in categories:
            use(fact)
            category = str(fact_value(fact))
            if category in exclusions:
                early_wear = category == "consumable_wear" and timedelta(
                    0
                ) <= today - purchase <= timedelta(days=14)
                target = certain if fact.confidence >= 0.8 and not early_wear else possible
                if category not in target:
                    target.append(category)
        certain_labels = ", ".join(EXCLUSION_LABELS.get(c, c.replace("_", " ")) for c in certain)
        possible_labels = ", ".join(EXCLUSION_LABELS.get(c, c.replace("_", " ")) for c in possible)
        check(
            "exclusions",
            not certain,
            "Exclusions certaines : " + certain_labels
            if certain
            else "Aucune exclusion certaine"
            + (" ; possibles : " + possible_labels if possible else ""),
        )
        if rule.contact_delay_days is not None and rule.contact_delay_start.value == "unspecified":
            check(
                "contact_delay",
                None,
                "Contacter le revendeur au plus vite "
                f"(délai de {rule.contact_delay_days} jours, "
                "point de départ non précisé) — non bloquant",
            )
        else:
            check("contact_delay", None, "Aucun délai de contact bloquant")
        if certain:
            return finish(
                VerdictValue.NOT_COVERED,
                "Non couvert : exclusion " + certain_labels,
                "Not covered: exclusion " + ", ".join(c.replace("_", " ") for c in certain),
            )
        near = approximated and abs((today - end).days) < 30
        if today > end and not near:
            return finish(
                VerdictValue.NOT_COVERED,
                f"Non couvert : garantie expirée le {end:%d/%m/%Y}.",
                f"Not covered: warranty expired on {end:%d/%m/%Y}.",
            )
        low_confidence_date = any(
            f.confidence < 0.8
            for f in usable
            if f.field in DATE_FIELDS and f.provenance in evidence
        )
        value = (
            VerdictValue.LIKELY_COVERED
            if near or possible or low_confidence_date
            else VerdictValue.COVERED
        )
        label = "Probablement couvert" if value == VerdictValue.LIKELY_COVERED else "Couvert"
        english = "Likely covered" if value == VerdictValue.LIKELY_COVERED else "Covered"
        page_reference = _page_reference(proof.provenance.page)
        return finish(
            value,
            f"{label} : {equipment.model}, {duration_label}, acheté le {purchase:%d/%m/%Y}, "
            f"facture{page_reference} (jusqu'au {end:%d/%m/%Y}).",
            f"{english}: {equipment.model}, {duration_english}, bought {purchase:%d/%m/%Y}, "
            f"invoice{page_reference} (until {end:%d/%m/%Y}).",
        )
