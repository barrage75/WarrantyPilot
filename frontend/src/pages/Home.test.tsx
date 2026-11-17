import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, within } from "@testing-library/react";
import i18n from "@/i18n";
import { renderWithApi, stubHttp } from "@/test/http";
import Home, { Decisions } from "./Home";

const equipment = { id: "device-1", brand: "Dell", model: "Latitude 7440", serial: "7XK4L93", category: "laptop" };
const overview = {
 equipment_id: equipment.id,
 label: "Dell Latitude 7440",
 brand: equipment.brand,
 model: equipment.model,
 serial: equipment.serial,
 category: equipment.category,
 assigned_to: { id: "person-1", name: "Samy Benzeguir" },
 purchase_date: "2025-11-20",
 warranty_end: "2028-11-19",
 days_left: 400,
 coverage: "active",
 verdict: "covered",
 open_case_id: "case-1",
 invoice_document_id: "invoice-1",
};
const caseItem = {
 id: "case-1",
 equipment_id: equipment.id,
 status: "awaiting_validation",
 badge: "reproduction",
 channel: "browser_portal",
 policy: { outcome: "allowed", reasons: [] },
 verdict: {
  value: "covered",
  explanation_fr: "Facture du 20 novembre 2025.",
  explanation_en: "Invoice dated November 20, 2025.",
  evidence: [{ id: "proof-1", document_id: "doc-12345678", excerpt: "Garantie fabricant de 36 mois.", page: 1 }],
 },
};

beforeEach(async () => { await i18n.changeLanguage("fr"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function stubHomeApi(
 cases: unknown[] = [],
 savingsReport: Record<string, unknown> = {
  covered_equipment_eur: 75587.42,
  possible_savings_eur: 120,
  realized_savings_eur: 0,
  purchase_guard_lines: [{ amount_eur: 120, realized: false }],
 },
) {
 stubHttp(call => {
  if (call.path === "/api/cases") return Response.json(cases);
  if (call.path === "/api/equipment") return Response.json([equipment]);
  if (call.path === "/api/equipment/overview") return Response.json([overview]);
  if (call.path === "/api/reports/savings") return Response.json(savingsReport);
  if (call.path === "/api/notifications") return Response.json([]);
  return undefined;
 });
}

it("uses the right illustrations, compact mobile grid, and whole-euro KPI formatting", async () => {
 stubHomeApi();
 renderWithApi(<Home/>);
 const overviewRegion = await screen.findByRole("region", { name: "Vue d’ensemble" });
 expect(await within(overviewRegion).findByText(/75\s?587\s?€/)).toBeInTheDocument();
 expect(await within(overviewRegion).findByText(/120\s?€/)).toBeInTheDocument();
 expect(overviewRegion).toHaveClass("grid-cols-2");
 for (const category of ["calendar", "shield"]) {
  const icon = overviewRegion.querySelector(`img[data-icon="${category}"]`);
  expect(icon).toHaveAttribute("width", "36");
 }
});

it("uses possible savings from the report when purchase guard lines are empty", async () => {
 stubHomeApi([], {
  generated_at: "2026-11-20T09:00:00Z",
  company: "Appelia",
  covered_equipment_eur: 75587.42,
  possible_savings_eur: 120,
  realized_savings_eur: 0,
  journal_ok: true,
  journal_head: "hash",
  lines: [{
   case_id: "case-1",
   equipment_label: "Jabra Evolve2 65",
   manufacturer: "Jabra",
   channel: "email_reseller",
   status: "awaiting_validation",
   amount_eur: 120,
   realized: false,
   resolved_at: null,
   reference: null,
  }],
  purchase_guard_lines: [],
 });
 renderWithApi(<Home/>);
 const overviewRegion = await screen.findByRole("region", { name: "Vue d’ensemble" });
 const avoidableKpi = await within(overviewRegion).findByRole("link", { name: /Achat évitable/ });
 expect(avoidableKpi).toHaveTextContent(/120\s?€/);
});

it("keeps the decision queue in one card with compact rows and collapsed disclosures", async () => {
 stubHomeApi([caseItem]);
 renderWithApi(<Decisions/>);
 const region = await screen.findByRole("region", { name: "À décider" });
 const row = await within(region).findByTestId("decision-beam");
 expect(within(region).getByText("1", { exact: true })).toBeInTheDocument();
 expect(region.querySelectorAll("article")).toHaveLength(0);
 expect(row).toHaveClass("border-accent");
 expect(within(row).getByRole("link", { name: "Dell Latitude 7440" })).toHaveAttribute("href", "/cases/case-1");
 expect(within(row).getByText("Samy Benzeguir · 7XK4L93")).toBeInTheDocument();
 expect(within(row).getByRole("button", { name: "Valider" })).toBeInTheDocument();
 expect(within(row).getByRole("button", { name: "Rejeter" })).toBeInTheDocument();
 expect(within(row).getByText("Détails", { selector: "summary" }).parentElement).not.toHaveAttribute("open");
 expect(within(row).getByText("Preuves (1)", { selector: "summary" }).parentElement).not.toHaveAttribute("open");
 expect(row.querySelector('img[data-icon="laptop"]')).toHaveAttribute("width", "40");
});
