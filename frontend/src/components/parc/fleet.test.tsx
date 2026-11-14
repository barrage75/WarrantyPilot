import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import Parc from "@/pages/Parc";
import Dashboard from "@/pages/Dashboard";
import { CommandPalette } from "@/components/command/CommandPalette";
import { renderWithApi, stubHttp } from "@/test/http";
import i18n from "@/i18n";

const equipment = Array.from({ length: 30 }, (_, index) => ({ equipment_id: `device-${index}`, label: `Dell Latitude ${index}`, brand: "Dell", model: "Latitude", serial: `SERIAL-${index}`, category: "laptop", assigned_to: { id: "person", name: "Karim" }, purchase_date: "2026-01-01", warranty_end: "2028-01-01", days_left: 400, coverage: "active", verdict: "covered", open_case_id: index === 0 ? "case-1" : null, invoice_document_id: index === 0 ? "invoice-1" : null }));
const report = { generated_at: "2026-11-14T09:00:00Z", company: "Appelia", covered_equipment_eur: 14064, possible_savings_eur: 120, realized_savings_eur: 120, journal_ok: true, journal_head: "hash", lines: [{ case_id: "case-1", equipment_label: "Dell Latitude 0", manufacturer: "Dell", channel: "email_reseller", status: "resolved", amount_eur: 120, realized: true, resolved_at: "2026-11-14", reference: "REF-1" }] };
beforeEach(async () => {
 await i18n.changeLanguage("fr");
 stubHttp(call => {
  if (call.path === "/api/equipment/overview") return Response.json(equipment);
  if (call.path === "/api/reports/savings") return Response.json(report);
  if (call.path === "/api/cases") return Response.json([{ id: "case-1", equipment_id: "device-0", status: "resolved" }]);
  return undefined;
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("paginates the fleet and opens an accessible sheet with document, case and serial links", async () => {
 renderWithApi(<Parc/>, "/parc");
 const tiles = await screen.findAllByTestId("equipment-tile");
 expect(tiles).toHaveLength(24);
 await userEvent.click(tiles[0]);
 const sheet = screen.getByRole("dialog");
 expect(within(sheet).getByRole("heading")).toHaveTextContent("Dell Latitude 0");
 expect(within(sheet).getByRole("link", { name: "Voir la facture" })).toHaveAttribute("href", "/documents?document=invoice-1");
 expect(within(sheet).getByRole("link", { name: "Ouvrir le dossier" })).toHaveAttribute("href", "/cases/case-1");
 expect(decodeURIComponent(within(sheet).getByRole("link", { name: "Signaler une panne" }).getAttribute("href")!)).toContain("SERIAL-0");
 await userEvent.keyboard("{Escape}");
 await waitFor(() => expect(tiles[0]).toHaveFocus());
 await userEvent.click(screen.getByRole("button", { name: "Page suivante" }));
 expect(screen.getAllByTestId("equipment-tile")).toHaveLength(6);
 expect(screen.getByText("Dell Latitude 24")).toBeInTheDocument();
});
it("requests coverage and search filters through the API", async () => {
 renderWithApi(<Parc/>, "/parc");
 await screen.findAllByTestId("equipment-tile");
 await userEvent.click(screen.getByRole("button", { name: "Expire bientôt" }));
 expect(screen.getByRole("button", { name: "Expire bientôt" })).toHaveAttribute("aria-pressed", "true");
 await userEvent.type(screen.getByRole("searchbox"), "SERIAL");
 await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([request]) => request instanceof Request && request.url.includes("coverage=expiring_soon") && request.url.includes("q=SERIAL"))).toBe(true));
});
it("opens command search from the keyboard and follows URL changes on the current fleet page", async () => {
 Element.prototype.scrollIntoView = vi.fn();
 vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
 renderWithApi(<><CommandPalette/><Routes><Route path="/parc" element={<Parc/>}/></Routes></>, "/parc");
 await screen.findAllByTestId("equipment-tile");
 await userEvent.keyboard("{Control>}k{/Control}");
 const dialog = await screen.findByRole("dialog");
 await userEvent.click(await within(within(dialog).getByRole("group", { name: "Équipements" })).findByRole("option", { name: /Dell Latitude 0/ }));
 expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
 expect(screen.getByRole("searchbox")).toHaveValue("SERIAL-0");
});
it("renders report evidence and enables CSV download after report data arrives", async () => {
 renderWithApi(<Dashboard/>);
 expect(await screen.findByRole("cell", { name: "REF-1" })).toBeInTheDocument();
 expect(screen.getByRole("link", { name: "Journal intègre" })).toHaveAttribute("href", "/journal");
 expect(screen.getByRole("button", { name: "Télécharger le CSV" })).toBeEnabled();
 expect(screen.getByRole("link", { name: "Dell Latitude 0" })).toHaveAttribute("href", "/cases/case-1");
});
