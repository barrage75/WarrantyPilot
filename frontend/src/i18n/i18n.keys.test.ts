import { describe, expect, it } from "vitest";
import { resources } from "./index";
function keys(value: Record<string, unknown>, prefix = ""): string[] {
 return Object.entries(value).flatMap(([key, child]) => {
  const path = prefix + key;
  if (child && typeof child === "object") return keys(child as Record<string, unknown>, path + ".");
  expect(typeof child, path).toBe("string");
  expect(String(child).trim().length, path).toBeGreaterThan(0);
  return [path];
 }).sort();
}
describe("translation namespaces", () => {
 it("has identical namespaces", () => expect(Object.keys(resources.fr).sort()).toEqual(Object.keys(resources.en).sort()));
 for (const ns of Object.keys(resources.fr)) it(ns + " has matching nonempty recursive keys", () => expect(keys(resources.fr[ns])).toEqual(keys(resources.en[ns])));
});
