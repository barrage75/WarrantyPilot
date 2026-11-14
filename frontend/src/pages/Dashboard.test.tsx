import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "./Dashboard";
import i18n from "@/i18n";
import { renderWithApi, stubHttp, type Call } from "@/test/http";
const base = { scanId: "s1", company: "Appelia", invoices: 0, coveredEquipmentEur: 0, possibleSavingsEur: 0, realizedSavingsEur: 0, expiring: [], progress: 0, documentsTotal: 65, documentsDone: 0, badge: "reproduction", error: null };
let calls: Call[], polls: number, scanStatus: number;
beforeEach(async () => {
 await i18n.changeLanguage("fr"); polls = 0; scanStatus = 200;
 calls = stubHttp(call => {
  if (call.method === "POST" && call.path === "/api/scan") return scanStatus === 200 ? Response.json({ scan_id: "s1" }, { status: 202 }) : Response.json({ detail: "down" }, { status: scanStatus });
  if (call.path === "/api/reports/savings") return scanStatus === 200 ? Response.json({ generated_at: "2026-11-14T09:00:00Z", company: "Appelia", covered_equipment_eur: 8346, possible_savings_eur: 120, realized_savings_eur: 0, journal_ok: true, journal_head: "hash", lines: [] }) : Response.json({ detail: "down" }, { status: scanStatus });
  if (call.path === "/api/scan/s1") { polls += 1; return Response.json(polls === 1 ? { ...base, status: "running", documentsDone: 50, progress: 77 } : { ...base, status: "completed", invoices: 60, coveredEquipmentEur: 8346, possibleSavingsEur: 120, realizedSavingsEur: 0, progress: 100, documentsDone: 65, expiring: [{ equipment: "Jabra Evolve2 65", right: "manufacturer_warranty", endsAt: "2026-12-30", daysLeft: 10 }] }); }
  return undefined;
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("runs the real scan, shows progress and expiring rights with one compact savings report", async () => {
 renderWithApi(<Dashboard/>);
 expect((await screen.findByText("Matériel couvert")).closest("span")).toHaveTextContent(/8.346,00/);
 await userEvent.click(screen.getByRole("button", { name: "Lancer le scan" }));
 expect(await screen.findByText("Progression : 50 / 65 documents")).toBeInTheDocument();
 expect(screen.getByRole("progressbar")).toHaveAttribute("max", "65");
 expect(await screen.findByText(/Scan terminé : 65 \/ 65 documents lus, 60 factures/, {}, { timeout: 3000 })).toBeInTheDocument();
 expect(screen.getAllByText(/8.346,00/)).toHaveLength(1);
 expect(screen.getByText("Achats évitables").closest("span")).toHaveTextContent("120,00");
 expect(screen.getByText("Achats évités").closest("span")).toHaveTextContent("0,00");
 expect(screen.getByText("Reproduction")).toBeInTheDocument(); expect(screen.queryByText("Simulé")).not.toBeInTheDocument();
 expect(screen.getByText("Jabra Evolve2 65")).toBeInTheDocument(); expect(screen.getByText("Garantie fabricant")).toBeInTheDocument();
 expect(screen.getByRole("cell", { name: "10" })).toBeInTheDocument();
 expect(calls.filter(call => call.method === "POST")).toEqual([{ method: "POST", path: "/api/scan" }]);
});
it("handles scan errors without inventing savings (English)", async () => {
 await i18n.changeLanguage("en"); scanStatus = 503; renderWithApi(<Dashboard/>);
 await userEvent.click(screen.getByRole("button", { name: "Run scan" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
 expect(await screen.findByText("Unable to load the report.")).toBeInTheDocument();
 expect(screen.queryByText("Avoided purchases")).not.toBeInTheDocument();
});
