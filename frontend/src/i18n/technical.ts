import { resources } from "./index";

export const backendTechnicalKeys = [
 "lease", "suspicious_signal", "equipment_identity", "buyer", "document_conflict", "rule_match",
 "purchase_proof", "start_date", "end_date", "extension", "exclusions", "contact_delay",
 "purchase_date", "invoice_date", "delivery_date", "ship_date", "warranty_term_months",
 "extension_months", "warranty_plus_certificate", "service_contract", "lease_contract",
 "serial_number", "brand", "model_number", "product_type", "sku", "reseller_name",
 "reseller_address", "condition", "buyer_name", "equipment_ambiguous", "security.suspicious",
 "incident_category", "supplier_name", "lines[1].model",
 "scripted", "hcompany", "browser_use",
 "action_id", "idempotency_key", "case_number", "case_id", "incident_id", "equipment_id",
 "assigned_to", "reported_via", "kind", "status", "proof", "url", "portal_status",
 "observed_at", "reality", "untrusted", "code", "error_type", "error", "from", "to",
 "reason", "approved", "manual", "channel", "badge", "step", "by_person_id", "text",
 "screenshot_path", "screenshot_url", "message_id", "reminder_number", "due_at", "planned_at",
 "recommended_status", "executed", "manufacturer", "source", "due_on", "alert_on", "days_left",
 "alert", "observed_on", "requires_data_checklist", "return_blocked", "blocking_prerequisite",
 "replacement_blocked_until_return_received", "purchase_request_id", "amount_eur", "document_id",
 "page", "excerpt", "confidence", "rule_id", "rule_version", "checks", "missing",
 "possible_exclusions", "conditions", "outcome", "reasons", "target_url", "engine", "sent_at",
 "in_reply_to", "received_at", "subject", "matched_by", "injection_suspected", "rma_number",
 "xml_path", "xpath", "hash", "sha256", "received", "in_progress", "part_shipped", "closed",
 "covered", "likely_covered", "to_verify", "reproduction", "real", "simulated",
 "fake_rule_match", "dell_repair_request", "return_deadline", "email_reply", "followup_error",
 "reminder_drafted", "manual_takeover_recommended", "accepted", "info_requested", "rejected",
 "unknown", "portal_unavailable_or_invalid", "checker_error",
] as const;

export function technicalLabel(key: string, language: string): string {
 const namespace = resources[language.startsWith("fr") ? "fr" : "en"]?.technical;
 const label = namespace?.[key];
 return typeof label === "string" && label.trim() ? label : key.replaceAll("_", " ").replace(/^./, first => first.toLocaleUpperCase());
}

export function isTechnicalValue(value: unknown): boolean {
 if (typeof value !== "string") return false;
 return /https?:\/\/|(?:[A-Za-z]:\\|\/{1,2}[A-Za-z_][\w:.-]*(?:\/[\w:.*@-]+)+)|\b(?:[A-Za-z_][\w.-]*:)?[\w.-]+(?:\/(?:[A-Za-z_][\w.-]*:)?[\w.*@-]+){2,}|\b[a-f0-9]{32,}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(value)
  || (value.length > 160 && !/\s/.test(value));
}

export function isTechnicalField(key: string): boolean {
 return /(?:url|path|hash|proof|idempotency|xml|xpath|matched_by|in_reply_to|(?:^|_)id$)/i.test(key);
}
