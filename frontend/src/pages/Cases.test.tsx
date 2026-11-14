import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Decisions, CasesPage, CaseDetail } from "./Cases";
import type { components } from "@/api/schema";
import i18n from "@/i18n";
import { apiErrorKey } from "@/api/errors";
import { ApiError } from "@/api/client";
import { TestSession, sessionUser } from "@/test/http";
const person = "10000000-0000-4000-8000-000000000001";
const caseId = "20000000-0000-4000-8000-000000000002";
const item: components["schemas"]["Case"] = { id: caseId, incident_id: caseId, equipment_id: person, status: "awaiting_validation", badge: "simulated", channel: "email_reseller", verdict: { value: "covered", explanation_fr: "Couverture fictive", explanation_en: "Fictional coverage", checks: [{ name: "Facture", passed: true, detail: "Facture valide" }, { name: "Date", passed: null, detail: "Date absente" }], evidence: [{ document_id: person, page: 2, excerpt: "Achat fictif" }] }, policy: { outcome: "needs_validation", reasons: ["under_threshold"], conditions: { under_threshold: false, verdict_covered: true, equipment_unambiguous: true, no_possible_exclusion: true, no_suspicious_signal: true, low_commitment_action: true } } };
let data: components["schemas"]["Case"][];
let posts: { url: string; body: Record<string, string> }[];
let postStatus: number;
let events: unknown[], actions: unknown[];
beforeEach(async () => {
 localStorage.clear(); await i18n.changeLanguage("fr");
 data = [structuredClone(item)]; posts = []; postStatus = 200; events = []; actions = [];
 vi.stubGlobal("EventSource", class { close() {} addEventListener() {} });
 vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.origin), init);
  const url = new URL(request.url).pathname;
  if (request.method === "POST") {
   posts.push({ url, body: await request.json() as Record<string, string> });
   if (postStatus !== 200) return new Response(JSON.stringify({ detail: postStatus === 404 ? "Human approver not found" : "Case is not awaiting validation" }), { status: postStatus });
   data[0] = { ...data[0], status: url.endsWith("/reject") ? "cancelled" : url.endsWith("/resolve") ? "resolved" : "sent" };
   return Response.json(data[0]);
  }
  if (url.endsWith("/checklist")) return Response.json({ case_id: caseId, steps: { backup_verified: { done: true, by_person_id: person, at: "2026-01-01T12:00:00Z" } } });
  if (url.endsWith("/events")) return Response.json(events);
  if (url.endsWith("/actions")) return Response.json(actions);
  if (url === "/api/people") return Response.json([{ id: person, name: "Camille Martin", email: "camille@example.test", role: "IT" }]);
  if (url === "/api/equipment") return Response.json([{ id: person, brand: "Dell", model: "Latitude 5440", serial: "SVC-FAKE-01", category: "laptop" }]);
  if (url === "/api/cases") return Response.json(data);
  return Response.json(data[0]);
 }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function show(kind: "decisions" | "cases" | "detail", identity = true) {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
 return render(<QueryClientProvider client={cache}><TestSession user={identity ? sessionUser : null}><MemoryRouter initialEntries={[kind === "detail" ? "/cases/" + caseId : "/"]}><Routes><Route path="/" element={kind === "decisions" ? <Decisions/> : <CasesPage/>}/><Route path="/cases/:id" element={<CaseDetail/>}/></Routes></MemoryRouter></TestSession></QueryClientProvider>);
}
it("shows the queue and validates in one click with the session as actor", async () => {
 show("decisions"); await screen.findByText("Couverture fictive");
 expect(screen.getByText("Achat fictif")).toBeInTheDocument();
 await userEvent.click(screen.getByRole("button", { name: "Valider" }));
 await waitFor(() => expect(posts).toEqual([{ url: "/api/cases/" + caseId + "/validate", body: {} }]));
 await screen.findByText("Rien à décider");
});
it("requires a note to resolve a sent case as the active person", async () => {
 data = [{ ...item, status: "tracked" }];
 show("detail");
 const resolve = await screen.findByRole("button", { name: "Marquer comme résolu" });
 expect(resolve).toBeDisabled();
 await userEvent.type(screen.getByLabelText("Note de résolution"), "Remplacement reçu");
 await userEvent.click(resolve);
 await waitFor(() => expect(posts).toEqual([{
  url: "/api/cases/" + caseId + "/resolve",
  body: { note: "Remplacement reçu" },
 }]));
});
it("requires a nonblank rejection reason", async () => {
 show("decisions"); await userEvent.click(await screen.findByRole("button", { name: "Rejeter" }));
 const dialog = screen.getByRole("dialog");
 expect(within(dialog).getByRole("button", { name: "Confirmer le rejet" })).toBeDisabled();
 await userEvent.type(within(dialog).getByLabelText("Motif"), "Erreur de matériel");
 await userEvent.click(within(dialog).getByRole("button", { name: "Confirmer le rejet" }));
 await waitFor(() => expect(posts[0]).toEqual({ url: "/api/cases/" + caseId + "/reject", body: { reason: "Erreur de matériel" } }));
});
it("disables human actions without identity", async () => {
 show("decisions", false);
 expect(await screen.findByRole("button", { name: "Valider" })).toBeDisabled();
 expect(screen.getByRole("button", { name: "Rejeter" })).toBeDisabled();
 expect(screen.getByText(/Connectez-vous pour activer/)).toBeInTheDocument();
});
it("shows translated person-not-found errors", async () => {
 postStatus = 404; show("decisions");
 await userEvent.click(await screen.findByRole("button", { name: "Valider" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("Personne inconnue");
 expect(apiErrorKey(new ApiError(409, {}))).toBe("common:conflict");
});
it("renders policy conditions, nullable checks and seven checklist steps", async () => {
 show("detail"); await screen.findByText("Couverture fictive");
 expect(screen.getByText("Facture valide")).toBeInTheDocument();
 expect(screen.getByText("Non déterminé")).toBeInTheDocument();
 expect(screen.getByText("Montant inférieur au seuil d’envoi automatique")).toBeInTheDocument();
 expect(screen.getByText("Aucune exclusion possible")).toBeInTheDocument();
 expect(await screen.findByRole("heading", { name: "Données du PC — 7 étapes" })).toBeInTheDocument();
 expect(await screen.findAllByRole("button", { name: "Compléter" })).toHaveLength(6);
});
it("filters cases by status and ID", async () => {
 data.push({ ...item, id: "30000000-0000-4000-8000-000000000003", status: "failed" });
 show("cases"); await screen.findByRole("link", { name: "20000000" });
 await userEvent.selectOptions(screen.getByLabelText("Statut"), "failed");
 expect(screen.queryByRole("link", { name: "20000000" })).not.toBeInTheDocument();
 expect(screen.getByRole("link", { name: "30000000" })).toBeInTheDocument();
 await userEvent.type(screen.getByLabelText("Rechercher un ID"), "nothing");
 expect(screen.getByText("Aucun dossier ne correspond aux filtres.")).toBeInTheDocument();
});
it("handles an empty decision queue", async () => { data = []; show("decisions"); expect(await screen.findByText("Rien à décider")).toBeInTheDocument(); });
it("shows the decision channel in the case detail header", async () => {
 data = [{ ...structuredClone(item), verdict: { ...item.verdict!, channel: "browser_portal" } }];
 show("detail");
 expect(await screen.findByText("Portail web")).toBeInTheDocument();
 expect(screen.queryByText("E-mail revendeur")).not.toBeInTheDocument();
 await i18n.changeLanguage("en");
 expect(screen.getByText("Browser portal")).toBeInTheDocument();
});
it("renders browser steps with screenshots and the structured Dell case number", async () => {
 events = [
  { seq: 1, case_id: caseId, type: "action_step", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { text: "Formulaire rempli avec les données de l'action", screenshot_path: "/runtime/screens/filled.png", screenshot_url: "/api/cases/case/screenshots/filled.png?action_id=a1" } },
  { seq: 2, case_id: caseId, type: "action_step", actor: "agent", at: "2026-01-01T12:00:05Z", payload: { text: "Dossier créé au portail", case_number: "DELL-REP-123456", screenshot_path: "/runtime/screens/confirmation.png", screenshot_url: "/api/cases/case/screenshots/confirmation.png?action_id=a1" } }
 ];
 actions = [{ action: { id: "a1", case_id: caseId, channel: "browser_portal", kind: "dell_repair_request", badge: "reproduction" }, results: [{ id: "r1", action_id: "a1", status: "success", proof: JSON.stringify({ case_number: "DELL-REP-123456", screenshot_path: "/runtime/screens/confirmation.png" }) }] }];
 show("detail");
 expect(await screen.findByText("Formulaire rempli avec les données de l'action")).toBeInTheDocument();
 const screenshot = screen.getAllByRole("img", { name: "Capture de l’étape navigateur" })[0];
 expect(screenshot).toHaveAttribute("src", "/api/cases/case/screenshots/filled.png?action_id=a1");
 expect(screen.queryByText("/runtime/screens/filled.png")).not.toBeInTheDocument();
 expect(screen.getAllByText("Numéro de dossier Dell : DELL-REP-123456")).toHaveLength(2);
 expect(screen.getAllByRole("heading", { name: "Étape navigateur" })).toHaveLength(2);
 expect(screen.getByText(/Dell Latitude 5440/, { selector: "span" })).toBeInTheDocument();
 await userEvent.click(screen.getAllByRole("button", { name: "Agrandir la capture" })[0]);
 expect(screen.getByRole("dialog")).toBeInTheDocument();
 await i18n.changeLanguage("en");
 expect(screen.getAllByRole("img", { name: "Browser step screenshot" }).length).toBeGreaterThan(0);
});
