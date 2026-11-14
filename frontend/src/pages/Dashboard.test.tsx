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
  if (call.path === "/api/scan/s1") { polls += 1; return Response.json(polls === 1 ? { ...base, status: "running", documentsDone: 50, progress: 77 } : { ...base, status: "completed", invoices: 60, coveredEquipmentEur: 8346, possibleSavingsEur: 120, realizedSavingsEur: 0, progress: 100, documentsDone: 65, expiring: [{ equipment: "Jabra Evolve2 65", right: "manufacturer_warranty", endsAt: "2026-12-30", daysLeft: 10 }] }); }
  return undefined;
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("runs the real scan, shows document progress, three separate amounts and expiring rights", async () => {
 renderWithApi(<Dashboard/>);
 expect(screen.getByText("Économies réalisées").closest("section")).toHaveTextContent("—");
 await userEvent.click(screen.getByRole("button", { name: "Lancer le scan" }));
 expect(await screen.findByText("Progression : 50 / 65 documents")).toBeInTheDocument();
 expect(screen.getByRole("progressbar")).toHaveAttribute("max", "65");
 expect(await screen.findByText(/Scan terminé : 65 \/ 65 documents lus, 60 factures/, {}, { timeout: 3000 })).toBeInTheDocument();
 expect(screen.getByText("Valeur du matériel couvert").closest("section")).toHaveTextContent(/8.346,00/);
 expect(screen.getByText("Économies possibles").closest("section")).toHaveTextContent("120,00");
 expect(screen.getByText("Économies réalisées").closest("section")).toHaveTextContent("0,00");
 expect(screen.getByText("REPRODUCTION")).toBeInTheDocument(); expect(screen.queryByText("SIMULÉ")).not.toBeInTheDocument();
 expect(screen.getByText("Jabra Evolve2 65")).toBeInTheDocument(); expect(screen.getByText("Garantie fabricant")).toBeInTheDocument();
 expect(screen.getByRole("cell", { name: "10" })).toBeInTheDocument();
 expect(calls.filter(call => call.method === "POST")).toEqual([{ method: "POST", path: "/api/scan" }]);
});
it("handles scan errors without inventing savings (English)", async () => {
 await i18n.changeLanguage("en"); scanStatus = 503; renderWithApi(<Dashboard/>);
 await userEvent.click(screen.getByRole("button", { name: "Run scan" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
 expect(screen.getByText("Realized savings").closest("section")).toHaveTextContent("—");
});
