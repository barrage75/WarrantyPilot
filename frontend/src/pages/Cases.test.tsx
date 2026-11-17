import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Decisions, CasesPage, CaseDetail } from "./Cases";
import { Decisions as HomeDecisions } from "./Home";
import type { components } from "@/api/schema";
import i18n from "@/i18n";
import { apiErrorKey } from "@/api/errors";
import { ApiError } from "@/api/client";
import { TestSession, sessionUser } from "@/test/http";
import { resetPendingValidations } from "@/lib/pendingValidation";
const person = "10000000-0000-4000-8000-000000000001";
const caseId = "20000000-0000-4000-8000-000000000002";
const item: components["schemas"]["Case"] = { id: caseId, incident_id: caseId, equipment_id: person, status: "awaiting_validation", badge: "simulated", channel: "email_reseller", verdict: { value: "covered", explanation_fr: "Couverture fictive", explanation_en: "Fictional coverage", checks: [{ name: "Facture", passed: true, detail: "Facture valide" }, { name: "Date", passed: null, detail: "Date absente" }], evidence: [{ document_id: person, page: 2, excerpt: "Achat fictif" }] }, policy: { outcome: "needs_validation", reasons: ["under_threshold"], conditions: { under_threshold: false, verdict_covered: true, equipment_unambiguous: true, no_possible_exclusion: true, no_suspicious_signal: true, low_commitment_action: true } } };
let data: components["schemas"]["Case"][];
let posts: { url: string; body: Record<string, string> }[];
let postStatus: number;
let events: unknown[], actions: unknown[];
let checklistDone: Set<string>;
let people: components["schemas"]["Person"][], peopleStatus: number, checklistPerson: string;
beforeEach(async () => {
 resetPendingValidations();
 localStorage.clear(); await i18n.changeLanguage("fr");
 data = [structuredClone(item)]; posts = []; postStatus = 200; events = []; actions = []; checklistDone = new Set(["backup_verified"]);
 people = [{ id: person, name: "Camille Martin", email: "camille@example.test", role: "IT" }]; peopleStatus = 200; checklistPerson = person;
 vi.stubGlobal("EventSource", class { close() {} addEventListener() {} });
 vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.origin), init);
  const url = new URL(request.url).pathname;
  if (request.method === "POST") {
   posts.push({ url, body: await request.json() as Record<string, string> });
   if (url.includes("/checklist/")) {
    checklistDone.add(url.split("/").at(-1)!);
    return Response.json({ done: true, by_person_id: person, at: "2026-01-01T12:00:00Z" });
   }
   if (postStatus !== 200) return new Response(JSON.stringify({ detail: postStatus === 404 ? "Human approver not found" : "Case is not awaiting validation" }), { status: postStatus });
   data[0] = { ...data[0], status: url.endsWith("/reject") ? "cancelled" : url.endsWith("/resolve") ? "resolved" : "sent" };
   return Response.json(data[0]);
  }
  if (url.endsWith("/checklist")) return Response.json({ case_id: caseId, steps: Object.fromEntries(["repair_type", "backup_verified", "disk_encryption", "disk_handling", "accounts_and_mdm", "shipping_label", "return_inspection"].map(step => [step, { done: checklistDone.has(step), by_person_id: checklistDone.has(step) ? checklistPerson : null, at: checklistDone.has(step) ? "2026-01-01T12:00:00Z" : null }])) });
  if (url.endsWith("/events")) return Response.json(events);
  if (url.endsWith("/actions")) return Response.json(actions);
  if (url === "/api/people") return Response.json(people, { status: peopleStatus });
  if (url === "/api/equipment") return Response.json([{ id: person, brand: "Dell", model: "Latitude 5440", serial: "SVC-FAKE-01", category: "laptop" }]);
  if (url === "/api/equipment/overview") return Response.json([]);
  if (url === "/api/cases") return Response.json(data);
  return Response.json(data[0]);
 }));
});
afterEach(() => { cleanup(); resetPendingValidations(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function show(kind: "decisions" | "homeDecisions" | "cases" | "detail", identity = true) {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
 return render(<QueryClientProvider client={cache}><TestSession user={identity ? sessionUser : null}><MemoryRouter initialEntries={[kind === "detail" ? "/cases/" + caseId : "/"]}><Routes><Route path="/" element={kind === "decisions" ? <Decisions/> : kind === "homeDecisions" ? <HomeDecisions/> : <CasesPage/>}/><Route path="/cases/:id" element={<CaseDetail/>}/></Routes></MemoryRouter></TestSession></QueryClientProvider>);
}
function visibleText(element: HTMLElement) {
 const copy = element.cloneNode(true) as HTMLElement;
 copy.querySelectorAll("details:not([open])").forEach(details => details.replaceWith(details.querySelector("summary")!.cloneNode(true)));
 return copy.textContent ?? "";
}
const uuidPattern = /\b[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}\b/i;
it.each(["fr", "en"])("shows dated rule checks, evidence and timeline messages outside technical details in %s", async language => {
 await i18n.changeLanguage(language);
 const fr = language === "fr", date = fr ? "20/11/2025" : "11/20/2025";
 const details = fr ? ["Date de facture : 20/11/2025 (date estimée)", "Date d'achat : 21/11/2026"] : ["Invoice date: 11/20/2025 (estimated date)", "Purchase date: 11/21/2026"];
 const excerpt = fr ? "Facture émise le " + date : "Invoice issued on " + date;
 const description = fr ? "Formulaire complété le " + date : "Form completed on " + date;
 data[0].verdict!.checks = details.map((detail, index) => ({ name: index ? "purchase_date" : "invoice_date", passed: true, detail }));
 data[0].verdict!.evidence = [{ document_id: person, page: 2, excerpt }];
 events = [
  { seq: 1, case_id: caseId, type: "action_step", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { text: description } },
  { seq: 2, case_id: caseId, type: "fact_extracted", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { purchase_date: date } },
 ];
 show("detail");
 for (const detail of details) {
  const text = await screen.findByText(detail);
  expect(text).toBeVisible();
  expect(text.closest("details")).toBeNull();
 }
 expect(screen.getByText(excerpt, { selector: "blockquote" })).toBeVisible();
 expect(await screen.findByText(description)).toBeVisible();
 expect(screen.getByText(date, { selector: "dd" })).toBeVisible();
});

it.each(["fr", "en"])("keeps paths, URLs, UUIDs and key=value rule checks and evidence collapsed in %s", async language => {
 await i18n.changeLanguage(language);
 const details = ["/tmp/x.pdf", "runtime/browser/case/step.png", "https://example.test/invoice.pdf", "rule_id=dell-laptop", "Date : 20/11/2025 ; fichier /tmp/x.pdf", "2994dff0-6a5d-421a-b61b-c7b71c49dce9"];
 data[0].verdict!.checks = details.map((detail, index) => ({ name: "technical_check_" + index, passed: true, detail }));
 data[0].verdict!.evidence = details.map(excerpt => ({ document_id: person, page: 2, excerpt }));
 const { container } = show("detail");
 await screen.findByRole("heading", { name: language === "fr" ? "Verdict et trace des règles" : "Verdict and rule trace" });
 for (const detail of details) {
  expect(visibleText(container)).not.toContain(detail);
  const raw = Array.from(container.querySelectorAll("details pre")).filter(pre => pre.textContent?.includes(JSON.stringify(detail)));
  expect(raw).toHaveLength(2);
  raw.forEach(pre => expect(pre).not.toBeVisible());
 }
 const path = Array.from(container.querySelectorAll("details pre")).find(pre => pre.textContent?.includes(JSON.stringify(details[0])))!;
 await userEvent.click(within(path.closest("details")!).getByText(language === "fr" ? "Détails techniques" : "Technical details"));
 expect(path).toBeVisible();
});

it.each(["fr", "en"])("shows dated Home evidence while keeping raw paths in nested technical details in %s", async language => {
 await i18n.changeLanguage(language);
 const excerpt = language === "fr" ? "Date de facture : 20/11/2025 (date estimée)" : "Invoice date: 11/20/2025 (estimated date)";
 const path = "runtime/browser/case/step.png";
 data[0].verdict!.evidence = [excerpt, path].map(excerpt => ({ document_id: person, page: 2, excerpt }));
 const { container } = show("homeDecisions");
 await userEvent.click(await screen.findByText(language === "fr" ? "Preuves (2)" : "Evidence (2)", { selector: "summary" }));
 expect(screen.getByText(excerpt, { selector: "blockquote" })).toBeVisible();
 expect(visibleText(container)).not.toContain(path);
 expect(container.querySelectorAll("blockquote")).toHaveLength(1);
});

it("shows the queue and validates after the undo window with the session as actor", async () => {
 show("decisions"); await screen.findByText("Couverture fictive");
 expect(screen.getByText("Achat fictif")).toBeInTheDocument();
 vi.useFakeTimers();
 fireEvent.click(screen.getByRole("button", { name: "Valider" }));
 expect(posts).toEqual([]);
 await act(async () => { await vi.advanceTimersByTimeAsync(5000); await vi.runOnlyPendingTimersAsync(); });
 vi.useRealTimers();
 await waitFor(() => expect(posts).toEqual([{ url: "/api/cases/" + caseId + "/validate", body: {} }]));
 expect(await screen.findByText("Envoyé", { exact: true })).toBeInTheDocument();
 expect(screen.queryByRole("button", { name: "Valider" })).not.toBeInTheDocument();
}, 10000);
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
it("places the journey before decision actions and evidence", async () => {
 show("detail");
 const validate = await screen.findByRole("button", { name: "Valider" });
 const hero = screen.getByRole("heading", { level: 1 }).closest("header")!;
 expect(within(hero).queryByRole("button")).not.toBeInTheDocument();
 const journey = screen.getByRole("heading", { name: "Parcours de l’agent" });
 const evidence = screen.getByRole("heading", { name: "Preuves" });
 expect(journey.compareDocumentPosition(validate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
 expect(validate.compareDocumentPosition(evidence) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
 expect(screen.queryByLabelText("Note de résolution")).not.toBeInTheDocument();
});
it.each(["sent", "tracked"] as const)("places the resolution form after evidence for %s cases", async status => {
 data = [{ ...item, status }];
 show("detail");
 const note = await screen.findByLabelText("Note de résolution");
 const hero = screen.getByRole("heading", { level: 1 }).closest("header")!;
 expect(within(hero).queryByRole("textbox")).not.toBeInTheDocument();
 expect(screen.getByRole("heading", { name: "Preuves" }).compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
 expect(screen.getAllByRole("button", { name: "Marquer comme résolu" })).toHaveLength(1);
});
it.each(["failed", "manual_takeover", "resolved", "cancelled"] as const)("does not offer resolution for %s cases", async status => {
 data = [{ ...item, status }];
 show("detail");
 await screen.findByRole("heading", { level: 1 });
 expect(screen.queryByLabelText("Note de résolution")).not.toBeInTheDocument();
 expect(screen.queryByRole("button", { name: "Marquer comme résolu" })).not.toBeInTheDocument();
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
 const validate = await screen.findByRole("button", { name: "Valider" });
 vi.useFakeTimers();
 fireEvent.click(validate);
 await act(async () => { await vi.advanceTimersByTimeAsync(5000); await vi.runOnlyPendingTimersAsync(); });
 vi.useRealTimers();
 expect(await screen.findByRole("alert")).toHaveTextContent("Personne inconnue");
 expect(apiErrorKey(new ApiError(409, {}))).toBe("common:conflict");
}, 10000);
it("renders policy conditions, nullable checks and seven checklist steps", async () => {
 show("detail"); await screen.findByText("Couverture fictive");
 expect(screen.getByText("Facture valide")).toBeInTheDocument();
 expect(screen.getByText("Non déterminé")).toBeInTheDocument();
 expect(screen.getByText("Montant inférieur au seuil d’envoi automatique")).toBeInTheDocument();
 expect(screen.getByText("Aucune exclusion possible")).toBeInTheDocument();
 expect(await screen.findByRole("heading", { name: "Données du PC — 7 étapes" })).toBeInTheDocument();
 expect(await screen.findAllByRole("button", { name: "Compléter" })).toHaveLength(6);
});
it("updates the PC return banner as checklist steps are completed", async () => {
 show("detail");
 expect(await screen.findByText(/Renvoi du PC bloqué : terminez la protection des données \(1\/7\)/)).toBeInTheDocument();
 for (let completed = 2; completed <= 7; completed += 1) {
  await userEvent.click(screen.getAllByRole("button", { name: "Compléter" })[0]);
  if (completed < 7) await waitFor(() => expect(screen.getByText(new RegExp(`\\(${completed}/7\\)`))).toBeInTheDocument());
 }
 expect(await screen.findByText("Protection des données terminée : le PC peut être renvoyé.")).toBeInTheDocument();
});
it("filters cases by status and ID", async () => {
 data.push({ ...item, id: "30000000-0000-4000-8000-000000000003", status: "failed" });
 show("cases"); await screen.findByRole("link", { name: "20000000" });
 await userEvent.click(within(screen.getByRole("group", { name: "Statut" })).getByRole("button", { name: "Échec" }));
 expect(screen.queryByRole("link", { name: "20000000" })).not.toBeInTheDocument();
 expect(screen.getByRole("link", { name: "30000000" })).toBeInTheDocument();
 await userEvent.type(screen.getByLabelText("Rechercher un ID"), "nothing");
 expect(screen.getByText("Aucun dossier ne correspond aux filtres.")).toBeInTheDocument();
});
it("handles an empty decision queue", async () => { data = []; show("decisions"); expect(await screen.findByText("Rien à décider")).toBeInTheDocument(); });
it("uses the verdict channel consistently in case tiles and channel filters", async () => {
 const otherId = "30000000-0000-4000-8000-000000000003";
 data = [{ ...structuredClone(item), channel: "manual", verdict: { ...item.verdict!, channel: "browser_portal" } }, { ...structuredClone(item), id: otherId, verdict: null }];
 show("cases");
 const tile = await screen.findByRole("article", { name: caseId });
 expect(within(tile).getByText("Portail web")).toBeInTheDocument();
 expect(within(tile).queryByText("Traitement manuel")).not.toBeInTheDocument();
 await userEvent.selectOptions(screen.getByLabelText("Canal"), "browser_portal");
 expect(screen.getByRole("article", { name: caseId })).toBeInTheDocument();
 expect(screen.queryByRole("article", { name: otherId })).not.toBeInTheDocument();
 await userEvent.selectOptions(screen.getByLabelText("Canal"), "email_reseller");
 expect(screen.queryByRole("article", { name: caseId })).not.toBeInTheDocument();
 expect(screen.getByRole("article", { name: otherId })).toBeInTheDocument();
});
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

it.each(["fr", "en"])("formats generated evidence with document fact labels and values in %s", async language => {
 await i18n.changeLanguage(language);
 const fr = language === "fr";
 const excerpts = ["extension_months : 36", "invoice_date : 2025-11-20", "total_ttc : 1234.50", "warranty_extension_mentioned : True", "security.suspicious : false", "supplier_name : None", "serial_number : 00123", "lines[0].unit_price_ht : 12.5", "serial : 12345678901234567890"];
 data[0].verdict!.evidence = excerpts.map(excerpt => ({ document_id: person, page: 2, excerpt }));
 const { container } = show("detail");
 const extension = fr ? "Extension (mois) : 36" : "Extension (months): 36";
 expect(await screen.findByText(extension)).toBeVisible();
 const euro = (amount: number) => new Intl.NumberFormat(language, { style: "currency", currency: "EUR" }).format(amount);
 expect(Array.from(container.querySelectorAll("blockquote"), quote => quote.textContent)).toEqual(fr ? [
  extension, "Date de facture : 20/11/2025", "Total TTC : " + euro(1234.5), "Extension de garantie mentionnée : Oui", "Signal de sécurité suspect : Non", "Nom du fournisseur : —", "Numéro de série : 00123", "Ligne 1 · Prix unitaire HT : " + euro(12.5), "Numéro de série : 12345678901234567890",
 ] : [
  extension, "Invoice date: 11/20/2025", "Total incl. VAT: " + euro(1234.5), "Warranty extension mentioned: Yes", "Suspicious security signal: No", "Supplier name: —", "Serial number: 00123", "Line 1 · Unit price excl. VAT: " + euro(12.5), "Serial number: 12345678901234567890",
 ]);
 expect(visibleText(container)).not.toContain("extension_months");
 const raw = Array.from(container.querySelectorAll("details pre")).find(pre => pre.textContent?.includes(excerpts[0]))!;
 expect(raw).not.toBeVisible();
 await act(async () => { await i18n.changeLanguage(fr ? "en" : "fr"); });
 expect(screen.getByText(fr ? "Extension (months): 36" : "Extension (mois) : 36")).toBeVisible();
 await userEvent.click(within(raw.closest("details")!).getByText(fr ? "Technical details" : "Détails techniques"));
 expect(raw).toBeVisible();
 expect(raw).toHaveTextContent(excerpts[0]);
});

it.each(["fr", "en"])("preserves genuine source quotes and unrecognized fact fields in %s", async language => {
 await i18n.changeLanguage(language);
 const excerpts = ["Extension de garantie : 36 mois à compter de la livraison.", "La clause extension_months : 36 apparaît dans le contrat.", "extension_months : 36\nLa couverture dépend des conditions du contrat.", "unknown_fact : 36", "constructor : unchanged", "  Invoice: supplier_name : Fournisseur original  "];
 data[0].verdict!.evidence = excerpts.map(excerpt => ({ document_id: person, page: 2, excerpt }));
 const { container } = show("detail");
 await screen.findByText(excerpts[0]);
 expect(Array.from(container.querySelectorAll("blockquote"), quote => quote.textContent)).toEqual(excerpts);
});

it.each(["fr", "en"])("keeps technical data in generated evidence collapsed in %s", async language => {
 await i18n.changeLanguage(language);
 const excerpt = "supplier_name : " + person;
 data[0].verdict!.evidence = [{ document_id: person, page: 2, excerpt }];
 const { container } = show("detail");
 await screen.findByRole("heading", { name: language === "fr" ? "Preuves" : "Evidence" });
 expect(visibleText(container)).not.toMatch(uuidPattern);
 expect(container.querySelector("blockquote")).not.toBeInTheDocument();
 const raw = Array.from(container.querySelectorAll("details pre")).find(pre => pre.textContent?.includes(excerpt))!;
 expect(raw).not.toBeVisible();
});

it.each(["fr", "en"])("preserves browser-step free text without a step code in %s", async language => {
 await i18n.changeLanguage(language);
 const description = "Formulaire rempli avec les données de l’action";
 events = [{ seq: 1, case_id: caseId, type: "action_step", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { action_id: "a1", text: "[scripted] " + description, screenshot_name: "01-form-filled.png", screenshot_path: "/runtime/screens/01-form-filled.png" } }];
 const { container } = show("detail");
 expect(await screen.findByRole("heading", { name: language === "fr" ? "Étape navigateur" : "Browser step" })).toBeVisible();
 expect(screen.getByText(description)).toBeVisible();
 expect(visibleText(container)).not.toContain("[scripted]");
 expect(visibleText(container)).not.toContain("01-form-filled.png");
});

it.each([
 ["portal_claim", "Demande sur le portail", "Portal claim"],
 ["api_claim", "Demande par API", "API claim"],
 ["manual_claim", "Demande manuelle", "Manual claim"],
 ["lessor_request", "Demande au bailleur", "Lessor request"],
 ["warranty_claim_email", "Demande de garantie par e-mail", "Warranty claim by email"],
 ["dell_repair_request", "Demande de réparation Dell", "Dell repair request"],
 ["send_claim_email", "Envoi de la demande par e-mail", "Send claim by email"],
 ["send_email", "Envoi d’un e-mail", "Send email"],
])("translates action kind %s in French and English", async (kind, fr, en) => {
 actions = [{ action: { id: "a1", case_id: caseId, channel: "browser_portal", kind, badge: "reproduction" }, results: [] }];
 const { container } = show("detail");
 expect(await screen.findByRole("heading", { name: "Portail web · " + fr })).toBeVisible();
 expect(visibleText(container)).not.toMatch(uuidPattern);
 expect(visibleText(container)).not.toContain("Portal claim");
 await act(async () => { await i18n.changeLanguage("en"); });
 expect(screen.getByRole("heading", { name: "Browser portal · " + en })).toBeVisible();
});

it("keeps French case detail human-readable with named people and technical UUIDs collapsed", async () => {
 const unknown = "2994dff0-6a5d-421a-b61b-c7b71c49dce9";
 events = [
  { seq: 1, case_id: caseId, type: "case_created", actor: "human:" + person, at: "2026-01-01T12:00:00Z", payload: { assigned_to: person, source: "ingestion registry" } },
  { seq: 2, case_id: caseId, type: "validated", actor: "human:" + unknown, at: "2026-01-01T12:00:05Z", payload: { assigned_to: unknown, by_person_id: person, from: "awaiting_validation", to: "sent", kind: "portal_claim", channel: "browser_portal", role: "operator", untrusted: false, text: "Référence interne : " + unknown } },
  { seq: 3, case_id: caseId, type: "action_step", actor: "agent", at: "2026-01-01T12:00:08Z", payload: { text: "Référence interne : " + unknown, case_number: unknown } },
 ];
 actions = [{ action: { id: "a1", case_id: caseId, channel: "browser_portal", kind: "portal_claim", badge: "reproduction" }, results: [{ id: "r1", action_id: "a1", status: "success", proof: JSON.stringify({ case_number: unknown }) }] }];
 const { container } = show("detail");
 await screen.findByRole("heading", { name: "Portail web · Demande sur le portail" });
 expect(await screen.findByText("Registre des documents importés")).toBeVisible();
 await waitFor(() => expect(screen.getAllByText("Camille Martin", { selector: "dd" })).toHaveLength(2));
 expect(screen.getByText("Opérateur", { selector: "dd" })).toBeVisible();
 expect(screen.getByText("Non", { selector: "dd" })).toBeVisible();
 const completed = screen.getByRole("heading", { name: /Sauvegarde vérifiée/ }).closest("li")!;
 expect(visibleText(completed)).toContain("Camille Martin · ");
 expect(visibleText(completed)).toMatch(/01\/01\/2026.*\d{2}:\d{2}:\d{2}/);
 expect(visibleText(container)).not.toMatch(uuidPattern);
 expect(visibleText(container)).not.toContain("Portal claim");
 expect(visibleText(container)).not.toContain("ingestion registry");
 expect(visibleText(container)).not.toContain("Référence interne");
 const raw = Array.from(container.querySelectorAll("details pre")).find(pre => pre.textContent?.includes(unknown))!;
 expect(raw).not.toBeVisible();
 expect(container.querySelector("details[open]")).not.toBeInTheDocument();
 await userEvent.click(within(raw.closest("details")!).getByText("Détails techniques"));
 expect(raw).toBeVisible();
 expect(raw).toHaveTextContent(unknown);
 await act(async () => { await i18n.changeLanguage("en"); });
 expect(screen.getByText("Imported document registry")).toBeVisible();
 expect(screen.getByText("Operator", { selector: "dd" })).toBeVisible();
});

it.each([200, 503])("omits unknown people but preserves timestamps when the people API returns %s", async status => {
 people = []; peopleStatus = status;
 checklistPerson = "97225c38-49ad-4bb9-ac59-b848a3868af0";
 events = [{ seq: 1, case_id: caseId, type: "case_created", actor: "human:" + checklistPerson, at: "2026-01-01T12:00:05Z", payload: { assigned_to: checklistPerson, by_person_id: checklistPerson } }];
 const { container } = show("detail");
 await screen.findByRole("heading", { name: "Dossier créé" });
 await screen.findAllByRole("button", { name: "Compléter" });
 const completed = screen.getByRole("heading", { name: /Sauvegarde vérifiée/ }).closest("li")!;
 expect(visibleText(completed)).toMatch(/01\/01\/2026.*\d{2}:\d{2}:\d{2}/);
 expect(visibleText(completed)).not.toContain(" · ");
 expect(visibleText(container)).toMatch(/01\/01\/2026.*\d{2}:\d{2}:\d{2} · Humain/);
 expect(visibleText(container)).not.toContain("Attribué à:");
 expect(visibleText(container)).not.toMatch(uuidPattern);
 const technical = Array.from(container.querySelectorAll("details pre")).filter(pre => pre.textContent?.includes(checklistPerson));
 expect(technical.length).toBeGreaterThanOrEqual(3);
 technical.forEach(pre => expect(pre).not.toBeVisible());
});

it("translates known event sources and enum values instead of exposing their codes", async () => {
 const sources = ["llm", "structured", "human", "inventory", "classifier", "upload", "gmail", "facturx"];
 events = sources.map((source, index) => ({ seq: index + 1, case_id: caseId, type: "fact_extracted", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { source } }));
 events.push({ seq: 9, case_id: caseId, type: "followup_received", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { source: "ingestion_registry", kind: "portal_status", portal_status: "part_shipped", reported_via: "chat", outcome: "auto_send", status: "done", engine: "scripted" } });
 const { container } = show("detail");
 for (const label of ["Modèle de langage", "Document structuré", "Personne", "Inventaire", "Classificateur", "Téléversement", "Gmail", "Factur-X", "Registre des documents importés", "Statut du portail", "Pièce expédiée", "Discussion", "Envoi automatique", "Terminé", "Moteur de secours (sans IA)"]) {
  expect(await screen.findByText(label, { selector: "dd" })).toBeVisible();
 }
 expect(visibleText(container)).not.toContain("ingestion registry");
 expect(visibleText(container)).not.toContain("portal_status");
 expect(visibleText(container)).not.toContain("part_shipped");
});

it("keeps unknown action kinds and event codes only in collapsed technical details", async () => {
 actions = [{ action: { id: "a1", case_id: caseId, channel: "browser_portal", kind: "future_action_kind", badge: "reproduction" }, results: [] }];
 events = [{ seq: 1, case_id: caseId, type: "fact_extracted", actor: "agent", at: "2026-01-01T12:00:00Z", payload: { source: "future_source", status: "future_status", future_metadata: "future_value" } }];
 const { container } = show("detail");
 expect(await screen.findByRole("heading", { name: "Portail web · Autre action" })).toBeVisible();
 await screen.findByRole("heading", { name: "Fait extrait" });
 expect(visibleText(container)).not.toMatch(/future[_ ]/i);
 expect(container.textContent).toContain("future_action_kind");
 expect(container.textContent).toContain("future_source");
 expect(container.textContent).toContain("future_status");
});

it("does not display UUIDs in French case tiles", async () => {
 const { container } = show("cases");
 await screen.findByRole("link", { name: "20000000" });
 expect(visibleText(container)).not.toMatch(uuidPattern);
});
