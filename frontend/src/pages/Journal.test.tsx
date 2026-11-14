import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Journal from "./Journal";
import i18n, { resources } from "@/i18n";
import { renderWithApi, stubHttp, person, type Call } from "@/test/http";
const first = "10000000-0000-4000-8000-000000000011", second = "10000000-0000-4000-8000-000000000012";
const event = (seq: number, at = "2026-01-02T12:00:00Z") => ({ seq, at, actor: "human:" + person, type: "case_created", payload: { reason: "Équipement en panne" }, hash: "hash", prev_hash: "previous" });
let cases: { id: string; updated_at: string }[], events: Record<string, ReturnType<typeof event>[]>, calls: Call[], fail: string, gate: Promise<void> | undefined;
beforeEach(async () => {
 await i18n.changeLanguage("fr"); localStorage.clear(); fail = ""; gate = undefined;
 cases = [{ id: first, updated_at: "2026-01-03T00:00:00Z" }, { id: second, updated_at: "2026-01-02T00:00:00Z" }];
 events = { [first]: [event(1)], [second]: [event(2, "2026-01-03T12:00:00Z")] };
 calls = stubHttp(call => {
  if (call.path === fail) return Response.json({}, { status: 500 });
  if (call.path === "/api/journal/verify") return Response.json({ ok: true, checked: 32, first_bad_seq: null, anchors_ok: true });
  if (call.path === "/api/journal/anchor") return Response.json({ seq: 33, hash: "hash", hmac: "hmac", at: "2026-01-03T12:00:00Z" });
  if (call.path === "/api/cases") return Response.json(cases);
  const match = call.path.match(/^\/api\/cases\/([^/]+)\/events$/);
  if (match) return (async () => { await gate; return Response.json(events[match[1]] ?? []); })();
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("merges case events newest first, resolves actors, links cases and expands details", async () => {
 renderWithApi(<Journal/>);
 await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
 const rows = screen.getAllByRole("listitem");
 expect(within(rows[0]).getByRole("link")).toHaveAttribute("href", "/cases/" + second);
 expect(within(rows[1]).getByRole("link")).toHaveAttribute("href", "/cases/" + first);
 expect(within(rows[0]).getByText("Camille Martin")).toBeInTheDocument();
 expect(within(rows[0]).getByText("Équipement en panne")).not.toBeVisible();
 await userEvent.click(within(rows[0]).getByText("Voir les détails"));
 await waitFor(() => expect(within(rows[0]).getByText("Équipement en panne")).toBeVisible());
 expect(screen.getByRole("status")).toHaveTextContent("Journal intègre");
 expect(screen.getByText("32 événements vérifiés")).toBeInTheDocument();
});
it("caps event requests at the 20 most recently updated cases", async () => {
 cases = Array.from({ length: 22 }, (_, i) => ({ id: String(i), updated_at: `2026-01-${String(i + 1).padStart(2, "0")}T00:00:00Z` }));
 renderWithApi(<Journal/>); await screen.findByText("Aucun événement de dossier à afficher");
 const requests = calls.filter(call => call.path.endsWith("/events"));
 expect(requests).toHaveLength(20); expect(requests.some(call => /\/cases\/[01]\/events$/.test(call.path))).toBe(false);
});
it("shows ten events initially and reveals more on demand", async () => {
 events[first] = Array.from({ length: 12 }, (_, i) => event(i + 3)); events[second] = [];
 renderWithApi(<Journal/>); await screen.findByRole("button", { name: "Afficher plus d’événements" });
 expect(screen.getAllByRole("listitem")).toHaveLength(10);
 await userEvent.click(screen.getByRole("button", { name: "Afficher plus d’événements" }));
 expect(screen.getAllByRole("listitem")).toHaveLength(12);
 expect(screen.queryByRole("button", { name: "Afficher plus d’événements" })).not.toBeInTheDocument();
});
it("shows an empty state without fetching events when there are no cases", async () => {
 cases = []; renderWithApi(<Journal/>); await screen.findByText("Aucun événement de dossier à afficher");
 expect(calls.some(call => call.path.endsWith("/events"))).toBe(false);
});
it.each(["/api/cases", `/api/cases/${first}/events`])("reports %s failures without claiming the timeline is empty", async path => {
 fail = path; renderWithApi(<Journal/>);
 expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible");
 expect(screen.queryByText("Aucun événement de dossier à afficher")).not.toBeInTheDocument();
 if (path.endsWith("/events")) await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(1));
});
it("keeps event loading visible until requests finish", async () => {
 let finish!: () => void; gate = new Promise<void>(resolve => { finish = resolve; });
 renderWithApi(<Journal/>); await screen.findByRole("heading", { name: "Événements des dossiers" });
 expect(screen.getByText("Chargement…")).toBeInTheDocument(); finish();
 await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
});
it("reports anchor failures", async () => {
 fail = "/api/journal/anchor"; renderWithApi(<Journal/>);
 await userEvent.click(await screen.findByRole("button", { name: "Ancrer maintenant" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible");
});
it("translates nested policy details and reasons without exposing codes", async () => {
 events[first][0].payload = { reasons: ["under_threshold"], conditions: { under_threshold: false }, outcome: "needs_validation" } as unknown as ReturnType<typeof event>["payload"];
 renderWithApi(<Journal/>);
 await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
 const row = screen.getAllByRole("listitem")[1];
 await userEvent.click(within(row).getByText("Voir les détails"));
 await waitFor(() => expect(within(row).getByText("Le montant dépasse le seuil ou aucun seuil n’est défini")).toBeVisible());
 expect(within(row).getByText("Montant sous le seuil : Non")).toBeVisible();
 expect(within(row).getByText("Validation requise")).toBeVisible();
});
it("translates the timeline to English and keeps namespace keys aligned", async () => {
 await i18n.changeLanguage("en"); renderWithApi(<Journal/>);
 await screen.findByRole("heading", { name: "Case events" });
 await screen.findAllByRole("heading", { name: "Case created" });
 const keys = (value: Record<string, unknown>, prefix = ""): string[] => Object.entries(value).flatMap(([key, entry]) => typeof entry === "object" && entry !== null ? keys(entry as Record<string, unknown>, prefix + key + ".") : [prefix + key]).sort();
 expect(keys(resources.fr.journal)).toEqual(keys(resources.en.journal));
});
