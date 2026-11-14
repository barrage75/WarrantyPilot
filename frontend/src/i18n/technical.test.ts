import { describe, expect, it } from "vitest";
import { backendTechnicalKeys, isTechnicalValue, technicalLabel } from "./technical";
import { resources } from "./index";

describe("technical labels", () => {
 it.each(backendTechnicalKeys)("%s has French and English labels", key => {
  const fr = technicalLabel(key, "fr");
  const en = technicalLabel(key, "en");
  expect(fr).not.toBe(key);
  expect(fr.trim()).not.toBe("");
  expect(en.trim()).not.toBe("");
  expect((resources.fr.technical as Record<string, string>)[key]).toBe(fr);
  expect((resources.en.technical as Record<string, string>)[key]).toBe(en);
 });

 it("humanizes unknown keys instead of displaying them raw", () => {
  expect(technicalLabel("future_control_name", "fr")).toBe("Future control name");
 });
 it.each([
  "2994dff0-6a5d-421a-b61b-c7b71c49dce9",
  "HUMAN:97225C38-49AD-4BB9-AC59-B848A3868AF0",
  "Référence interne : 10000000-0000-4000-8000-000000000001",
 ])("treats UUIDs as technical content: %s", value => {
  expect(isTechnicalValue(value)).toBe(true);
 });
 it("preserves readable case numbers and serials", () => {
  expect(isTechnicalValue("DELL-REP-123456")).toBe(false);
  expect(isTechnicalValue("SVC-FAKE-01")).toBe(false);
 });
 it.each([
  "20/11/2025", "11/20/2025", "1/2/2025",
  "Date de facture : 20/11/2025 (date estimée)",
  "Date d'achat : 21/11/2026", "Invoice date: 11/20/2025",
  "Date:20/11/2025.", "Achat le 20/11/2025...", "20/11/2025,11/20/2025",
  "Date de facture : 20/11/2025 à 09:30:08",
 ])("keeps standalone dates human-readable: %s", value => {
  expect(isTechnicalValue(value)).toBe(false);
 });
 it.each([
  "/tmp/x.pdf", "runtime/browser/case/step.png", "C:\\runtime\\browser\\step.png",
  "/20/11/2025", "./20/11/2025", "runtime/browser/20/11/2025", "20/11/2025.pdf",
  "invoice-20/11/2025", "invoice.20/11/2025", "20/11/2025-invoice", "20/11/2025:invoice",
  "Date de facture : 20/11/2025 ; fichier /tmp/x.pdf",
  "Date: 11/20/2025 ; runtime/browser/case/step.png",
  "https://example.test/20/11/2025", "20/11/2025 ; https://example.test/invoice.pdf",
  "Date : 20/11/2025 ; 2994dff0-6a5d-421a-b61b-c7b71c49dce9",
  "rule_id=dell-laptop", "invoice_date=20/11/2025", "expected = 20/11/2025",
  "source: /tmp/x.pdf", "camille@example.test",
 ])("keeps real paths and other technical content collapsed: %s", value => {
  expect(isTechnicalValue(value)).toBe(true);
 });
});
