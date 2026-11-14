from enum import StrEnum


class CaseStatus(StrEnum):
    PREPARED = "prepared"
    AWAITING_VALIDATION = "awaiting_validation"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    MANUAL_TAKEOVER = "manual_takeover"
    TRACKED = "tracked"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class VerdictValue(StrEnum):
    COVERED = "covered"
    LIKELY_COVERED = "likely_covered"
    TO_VERIFY = "to_verify"
    NOT_COVERED = "not_covered"
    OUT_OF_MANUFACTURER = "out_of_manufacturer"


class RightType(StrEnum):
    MANUFACTURER_WARRANTY = "manufacturer_warranty"
    EXTENSION = "extension"
    LEASE_CONTRACT = "lease_contract"
    MAINTENANCE_CONTRACT = "maintenance_contract"
    SELLER_RECOURSE = "seller_recourse"


class Channel(StrEnum):
    API = "api"
    EMAIL_RESELLER = "email_reseller"
    EMAIL_MANUFACTURER_SUPPORT = "email_manufacturer_support"
    BROWSER_PORTAL = "browser_portal"
    EMAIL_LESSOR = "email_lessor"
    MANUAL = "manual"


class RealityBadge(StrEnum):
    REAL = "real"
    REPRODUCTION = "reproduction"
    SIMULATED = "simulated"


class IncidentKind(StrEnum):
    FAILURE = "failure"
    PURCHASE_REQUEST = "purchase_request"


class FactSource(StrEnum):
    LLM = "llm"
    STRUCTURED = "structured"
    HUMAN = "human"
    INVENTORY = "inventory"
    CLASSIFIER = "classifier"


class FactField(StrEnum):
    PURCHASE_DATE = "purchase_date"
    INVOICE_DATE = "invoice_date"
    DELIVERY_DATE = "delivery_date"
    SHIP_DATE = "ship_date"
    WARRANTY_TERM_MONTHS = "warranty_term_months"
    EXTENSION_MONTHS = "extension_months"
    WARRANTY_PLUS_CERTIFICATE = "warranty_plus_certificate"
    SERVICE_CONTRACT = "service_contract"
    LEASE_CONTRACT = "lease_contract"
    SERIAL_NUMBER = "serial_number"
    BRAND = "brand"
    MODEL_NUMBER = "model_number"
    PRODUCT_TYPE = "product_type"
    SKU = "sku"
    RESELLER_NAME = "reseller_name"
    RESELLER_ADDRESS = "reseller_address"
    CONDITION = "condition"
    BUYER_NAME = "buyer_name"
    EQUIPMENT_AMBIGUOUS = "equipment_ambiguous"
    SECURITY_SUSPICIOUS = "security.suspicious"
    INCIDENT_CATEGORY = "incident_category"


class PolicyOutcome(StrEnum):
    AUTO_SEND = "auto_send"
    NEEDS_VALIDATION = "needs_validation"
    BLOCKED = "blocked"


class PurchaseGuardState(StrEnum):
    RECOMMENDATION = "recommendation"
    AWAITING_DECISION = "awaiting_decision"
    PURCHASE_SUSPENDED = "purchase_suspended"
    PURCHASE_KEPT = "purchase_kept"
    SAVING_REALIZED = "saving_realized"
    CANCELLED = "cancelled"


class ActionResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class DocumentKind(StrEnum):
    INVOICE = "invoice"
    DELIVERY_NOTE = "delivery_note"
    CONTRACT = "contract"
    EMAIL = "email"
    WARRANTY_CERTIFICATE = "warranty_certificate"


class DocumentSource(StrEnum):
    UPLOAD = "upload"
    GMAIL = "gmail"
    FACTURX = "facturx"


class IncidentReportedVia(StrEnum):
    CHAT = "chat"
    EMAIL = "email"
    VOICE = "voice"
    PURCHASE_FORM = "purchase_form"


class RuleStartEvent(StrEnum):
    PURCHASE_DATE = "purchase_date"
    DELIVERY_DATE = "delivery_date"
    SHIP_DATE = "ship_date"
    STANDARD_WARRANTY_END = "standard_warranty_end"


class ContactDelayStart(StrEnum):
    KNOWN = "known"
    UNSPECIFIED = "unspecified"


class ChecklistStepName(StrEnum):
    REPAIR_TYPE = "repair_type"
    BACKUP_VERIFIED = "backup_verified"
    DISK_ENCRYPTION = "disk_encryption"
    DISK_HANDLING = "disk_handling"
    ACCOUNTS_AND_MDM = "accounts_and_mdm"
    SHIPPING_LABEL = "shipping_label"
    RETURN_INSPECTION = "return_inspection"


class EventType(StrEnum):
    CASE_CREATED = "case_created"
    FACT_EXTRACTED = "fact_extracted"
    FACT_CORRECTED = "fact_corrected"
    VERDICT_COMPUTED = "verdict_computed"
    POLICY_DECIDED = "policy_decided"
    VALIDATION_REQUESTED = "validation_requested"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ACTION_STARTED = "action_started"
    ACTION_STEP = "action_step"
    ACTION_SUCCEEDED = "action_succeeded"
    ACTION_FAILED = "action_failed"
    STATUS_CHANGED = "status_changed"
    CHECKLIST_STEP_DONE = "checklist_step_done"
    PURCHASE_GUARD_RECOMMENDED = "purchase_guard_recommended"
    PURCHASE_GUARD_DECISION = "purchase_guard_decision"
    PURCHASE_GUARD_SUSPENDED = "purchase_guard_suspended"
    PURCHASE_GUARD_KEPT = "purchase_guard_kept"
    PURCHASE_GUARD_SAVING_REALIZED = "purchase_guard_saving_realized"
    PURCHASE_GUARD_CANCELLED = "purchase_guard_cancelled"
    AGENT_PAUSED = "agent_paused"
    AGENT_RESUMED = "agent_resumed"
    JOURNAL_ANCHORED = "journal_anchored"
    DEMO_RESET = "demo_reset"
    FOLLOWUP_RECEIVED = "followup_received"
    INTAKE_MESSAGE_RECEIVED = "intake_message_received"
    INTAKE_DOCUMENT_RECEIVED = "intake_document_received"
    REMINDER_DRAFTED = "reminder_drafted"
    CHAT_DISCLOSURE = "chat_disclosure"
    SETTINGS_CHANGED = "settings_changed"


_LABELS: dict[type[StrEnum], dict[str, tuple[str, str]]] = {
    CaseStatus: {
        "prepared": ("Préparé", "Prepared"),
        "awaiting_validation": ("En attente de validation", "Awaiting validation"),
        "sending": ("Envoi en cours", "Sending"),
        "sent": ("Envoyé", "Sent"),
        "failed": ("Échec", "Failed"),
        "manual_takeover": ("Pris en main par un humain", "Handed to a human"),
        "tracked": ("Suivi", "Tracked"),
        "resolved": ("Résolu", "Resolved"),
        "cancelled": ("Annulé", "Cancelled"),
    },
    VerdictValue: {
        "covered": ("Couvert", "Covered"),
        "likely_covered": ("Probablement couvert", "Likely covered"),
        "to_verify": ("À vérifier", "To verify"),
        "not_covered": ("Non couvert", "Not covered"),
        "out_of_manufacturer": ("Hors garantie fabricant", "Out of manufacturer warranty"),
    },
    RealityBadge: {
        "real": ("Réel", "Real"),
        "reproduction": ("Reproduction", "Reproduction"),
        "simulated": ("Simulé", "Simulated"),
    },
    RightType: {
        "manufacturer_warranty": ("Garantie fabricant", "Manufacturer warranty"),
        "extension": ("Extension de garantie", "Warranty extension"),
        "lease_contract": ("Contrat de location", "Lease contract"),
        "maintenance_contract": ("Contrat de maintenance", "Maintenance contract"),
        "seller_recourse": ("Recours vendeur", "Seller recourse"),
    },
    Channel: {
        "api": ("API", "API"),
        "email_reseller": ("E-mail revendeur", "Reseller email"),
        "email_manufacturer_support": (
            "E-mail support fabricant",
            "Manufacturer support email",
        ),
        "browser_portal": ("Portail web", "Browser portal"),
        "email_lessor": ("E-mail bailleur", "Lessor email"),
        "manual": ("Traitement manuel", "Manual handling"),
    },
    IncidentKind: {
        "failure": ("Panne", "Failure"),
        "purchase_request": ("Demande d'achat", "Purchase request"),
    },
    FactSource: {
        "llm": ("Modèle de langage", "Language model"),
        "structured": ("Document structuré", "Structured document"),
        "human": ("Personne", "Human"),
        "inventory": ("Inventaire", "Inventory"),
        "classifier": ("Classificateur", "Classifier"),
    },
    PolicyOutcome: {
        "auto_send": ("Envoi automatique", "Automatic send"),
        "needs_validation": ("Validation requise", "Validation required"),
        "blocked": ("Bloqué", "Blocked"),
    },
    PurchaseGuardState: {
        "recommendation": ("Recommandation", "Recommendation"),
        "awaiting_decision": ("En attente de décision", "Awaiting decision"),
        "purchase_suspended": ("Achat suspendu", "Purchase suspended"),
        "purchase_kept": ("Achat maintenu", "Purchase kept"),
        "saving_realized": ("Économie réalisée", "Saving realized"),
        "cancelled": ("Annulé", "Cancelled"),
    },
    ActionResultStatus: {
        "success": ("Réussi", "Success"),
        "failure": ("Échec", "Failure"),
    },
    Priority: {
        "P0": ("Priorité P0", "Priority P0"),
        "P1": ("Priorité P1", "Priority P1"),
        "P2": ("Priorité P2", "Priority P2"),
        "P3": ("Priorité P3", "Priority P3"),
    },
    DocumentKind: {
        "invoice": ("Facture", "Invoice"),
        "delivery_note": ("Bon de livraison", "Delivery note"),
        "contract": ("Contrat", "Contract"),
        "email": ("E-mail", "Email"),
        "warranty_certificate": ("Certificat de garantie", "Warranty certificate"),
    },
    DocumentSource: {
        "upload": ("Téléversement", "Upload"),
        "gmail": ("Gmail", "Gmail"),
        "facturx": ("Factur-X", "Factur-X"),
    },
    IncidentReportedVia: {
        "chat": ("Discussion", "Chat"),
        "email": ("E-mail", "Email"),
        "voice": ("Voix", "Voice"),
        "purchase_form": ("Formulaire d'achat", "Purchase form"),
    },
    RuleStartEvent: {
        "purchase_date": ("Date d'achat", "Purchase date"),
        "delivery_date": ("Date de livraison", "Delivery date"),
        "ship_date": ("Date d'expédition", "Ship date"),
        "standard_warranty_end": ("Fin de garantie standard", "Standard warranty end"),
    },
    ContactDelayStart: {
        "known": ("Délai connu", "Known delay"),
        "unspecified": ("Délai non précisé", "Unspecified delay"),
    },
    ChecklistStepName: {
        "repair_type": ("Type de réparation", "Repair type"),
        "backup_verified": ("Sauvegarde vérifiée", "Backup verified"),
        "disk_encryption": ("Chiffrement du disque", "Disk encryption"),
        "disk_handling": ("Traitement du disque", "Disk handling"),
        "accounts_and_mdm": ("Comptes et MDM", "Accounts and MDM"),
        "shipping_label": ("Étiquette d'expédition", "Shipping label"),
        "return_inspection": ("Inspection au retour", "Return inspection"),
    },
    EventType: {
        "case_created": ("Dossier créé", "Case created"),
        "fact_extracted": ("Fait extrait", "Fact extracted"),
        "fact_corrected": ("Fait corrigé", "Fact corrected"),
        "verdict_computed": ("Verdict calculé", "Verdict computed"),
        "policy_decided": ("Politique décidée", "Policy decided"),
        "validation_requested": ("Validation demandée", "Validation requested"),
        "validated": ("Validé", "Validated"),
        "rejected": ("Rejeté", "Rejected"),
        "action_started": ("Action démarrée", "Action started"),
        "action_step": ("Étape de l'action", "Action step"),
        "action_succeeded": ("Action réussie", "Action succeeded"),
        "action_failed": ("Échec de l'action", "Action failed"),
        "status_changed": ("Statut modifié", "Status changed"),
        "checklist_step_done": ("Étape de contrôle terminée", "Checklist step completed"),
        "purchase_guard_recommended": ("Achat recommandé", "Purchase recommended"),
        "purchase_guard_decision": ("Décision d'achat", "Purchase decision"),
        "purchase_guard_suspended": ("Achat suspendu", "Purchase suspended"),
        "purchase_guard_kept": ("Achat maintenu", "Purchase kept"),
        "purchase_guard_saving_realized": ("Économie réalisée", "Saving realized"),
        "purchase_guard_cancelled": ("Achat annulé", "Purchase cancelled"),
        "agent_paused": ("Agent mis en pause", "Agent paused"),
        "agent_resumed": ("Agent repris", "Agent resumed"),
        "journal_anchored": ("Journal ancré", "Journal anchored"),
        "demo_reset": ("Démo réinitialisée", "Demo reset"),
        "followup_received": ("Suivi reçu", "Follow-up received"),
        "intake_message_received": ("Message reçu", "Intake message received"),
        "intake_document_received": ("Document reçu", "Intake document received"),
        "reminder_drafted": ("Rappel préparé", "Reminder drafted"),
        "chat_disclosure": ("Information IA affichée", "AI disclosure shown"),
        "settings_changed": ("Réglages modifiés", "Settings changed"),
    },
}


def enum_label[T: StrEnum](value: T, language: str = "fr") -> str:
    """Return a localized display label while preserving English enum IDs."""
    labels = _LABELS.get(type(value), {})
    localized = labels.get(value.value)
    if localized is None:
        return value.value.replace("_", " ").capitalize()
    return localized[1] if language.lower().startswith("en") else localized[0]
