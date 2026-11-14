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
});
