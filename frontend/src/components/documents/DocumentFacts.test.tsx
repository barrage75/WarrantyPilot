import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import i18n from "@/i18n";
import { DocumentFacts } from "./DocumentFacts";

afterEach(cleanup);

describe.each([
 ["fr", "20/11/2025"],
 ["en", "11/20/2025"],
])("DocumentFacts in %s", (language, date) => {
 it("shows a formatted invoice date as visible text, outside technical details", async () => {
  await i18n.changeLanguage(language);
  const { container } = render(<DocumentFacts facts={[{ field: "invoice_date", value: "2025-11-20", confidence: 1 }]}/>);
  const value = screen.getByText(date);
  expect(value.closest("details")).toBeNull();
  expect(container.querySelector("details")).toBeNull();
 });

 it("still collapses a raw URL or path value", async () => {
  await i18n.changeLanguage(language);
  const { container } = render(<DocumentFacts facts={[
   { field: "source_url", value: "https://example.test/invoices/041.pdf", confidence: 1 },
   { field: "storage", value: "/var/data/invoices/041.pdf", confidence: 1 },
  ]}/>);
  expect(container.querySelectorAll("details")).toHaveLength(2);
  expect(screen.getByText("https://example.test/invoices/041.pdf").closest("details")).not.toBeNull();
  expect(screen.getByText("/var/data/invoices/041.pdf").closest("details")).not.toBeNull();
 });
});
