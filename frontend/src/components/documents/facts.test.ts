import { describe, expect, it } from "vitest";
import { resources } from "@/i18n";
import { formatDocumentFact, groupDocumentFacts } from "./facts";

const fact = (field: string, value: unknown, confidence = 1) => ({ field, value, confidence });
describe.each(["fr", "en"])("document facts in %s", language => {
 const fr = language === "fr";
 it("formats a single known fact with the same labels and values as grouped facts", () => {
  for (const entry of [fact("extension_months", 36), fact("invoice_date", "2025-11-20"), fact("lease_contract", false), fact("total_ttc", "1234.50"), fact("lines[0].unit_price_ht", "12.5"), fact("serial_number", "00123"), fact("supplier_name", null)]) {
   const formatted = formatDocumentFact(entry, language);
   expect(formatted.known).toBe(true);
   expect(groupDocumentFacts([entry], language)[0].facts[0]).toMatchObject({ label: formatted.label, formatted: formatted.formatted });
  }
  expect(formatDocumentFact(fact("extension_months", 36), language)).toEqual({ label: fr ? "Extension (mois)" : "Extension (months)", formatted: "36", known: true });
  expect(formatDocumentFact(fact("unknown_field", "raw"), language)).toEqual({ label: "Unknown field", formatted: "raw", known: false });
  expect(formatDocumentFact(fact("constructor", "raw"), language).known).toBe(false);
 });
 it("labels every extractor and normalized field, groups and sorts lines", () => {
  const fields = ["supplier_name", "supplier_address", "invoice_number", "invoice_date", "customer_name", "total_ttc", "warranty_extension_mentioned", "warranty_duration_months", "model", "sku", "serial", "quantity", "unit_price_ht", "purchase_date", "delivery_date", "ship_date", "warranty_term_months", "extension_months", "warranty_plus_certificate", "service_contract", "lease_contract", "serial_number", "brand", "model_number", "product_type", "reseller_name", "reseller_address", "condition", "buyer_name", "equipment_ambiguous", "security.suspicious", "incident_category"];
  const labels = resources[language].documents.factLabels as Record<string, string>;
  expect(fields.every(field => typeof labels[field] === "string")).toBe(true);
  const groups = groupDocumentFacts([fact("lines[3].sku", "REF"), fact("invoice_number", "INV"), fact("lines[0].serial", "SN"), fact("lines[0].unit_price_ht", "12.5"), fact("lines[0].warranty_duration_months", 24)], language);
  expect(groups.map(group => group.label)).toEqual([undefined, fr ? "Ligne 1" : "Line 1", fr ? "Ligne 4" : "Line 4"]);
  expect(groups[0].facts[0].label).toBe(fr ? "Numéro de facture" : "Invoice number");
  expect(groups[1].facts.map(item => item.label)).toEqual(fr ? ["Ligne 1 · Numéro de série", "Ligne 1 · Prix unitaire HT", "Ligne 1 · Durée de garantie (mois)"] : ["Line 1 · Serial number", "Line 1 · Unit price excl. VAT", "Line 1 · Warranty duration (months)"]);
 });
 it("formats dates, booleans and euro amounts without changing identifiers", () => {
  const rows = groupDocumentFacts([fact("invoice_date", "2025-11-20"), fact("warranty_extension_mentioned", true), fact("lease_contract", false), fact("total_ttc", "1234.50"), fact("serial", "00123"), fact("unit_price_ht", 0)], language)[0].facts;
  expect(rows.map(row => row.formatted)).toEqual([fr ? "20/11/2025" : "11/20/2025", fr ? "Oui" : "Yes", fr ? "Non" : "No", new Intl.NumberFormat(language, { style: "currency", currency: "EUR" }).format(1234.5), "00123", new Intl.NumberFormat(language, { style: "currency", currency: "EUR" }).format(0)]);
 });
 it("deduplicates field/value pairs, including objects with reordered keys, but keeps conflicting values and different lines", () => {
  const rows = groupDocumentFacts([fact("model", "A"), fact("model", "A", 0.5), fact("model", "B"), fact("security.suspicious", { a: 1, b: 2 }), fact("security.suspicious", { b: 2, a: 1 }), fact("lines[0].sku", "A"), fact("lines[1].sku", "A")], language);
  expect(rows.map(group => group.facts.length)).toEqual([3, 1, 1]);
 });
 it("humanizes unknown fields and preserves malformed values safely", () => {
  expect(groupDocumentFacts([], language)).toEqual([]);
  const groups = groupDocumentFacts([fact("foo_bar", null), fact("invoice_date", "2025-02-30"), fact("total_ttc", "not money"), fact("lines[2].unknown_field", "raw"), fact("delivery_date", "invalid")], language);
  expect(groups[0].facts.map(row => row.formatted)).toEqual(["—", "2025-02-30", "not money", "invalid"]);
  expect(groups[0].facts[0].label).toBe("Foo bar");
  expect(groups[1].label).toBe(fr ? "Ligne 3" : "Line 3");
  expect(groups[1].facts[0].label).toBe(fr ? "Ligne 3 · Unknown field" : "Line 3 · Unknown field");
 });
});
