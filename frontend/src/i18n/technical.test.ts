import { describe, expect, it } from "vitest";
import { backendTechnicalKeys, technicalLabel } from "./technical";
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
});
