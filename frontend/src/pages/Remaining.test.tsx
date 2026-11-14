import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import Settings from "./Settings";
import Demo from "./Demo";
import Journal from "./Journal";
import { OperatorProvider, OperatorSelector } from "@/operator";
import i18n from "@/i18n";
const person = "10000000-0000-4000-8000-000000000001";
const original = { id: person, auto_send_threshold_eur: "25.00", agent_paused: true, email_allowlist: ["camille@example.test"], browser_allowed_origins: ["http://127.0.0.1:*"], feature_flags: { p1_chat: true, p2_voice: false, scan: false }, future_field: { preserved: true } };
let settings: typeof original, requests: { path: string; method: string; body?: unknown }[], status: number;
let verification: { ok: boolean; checked: number; first_bad_seq: number | null; anchors_ok: boolean };
let caches: QueryClient[];
beforeEach(async () => {
 localStorage.clear(); await i18n.changeLanguage("fr"); settings = structuredClone(original); requests = []; status = 200; caches = [];
 verification = { ok: true, checked: 7, first_bad_seq: null, anchors_ok: true };
 vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const request = input instanceof Request ? input : new Request(new URL(String(input), window.location.origin), init);
  const path = new URL(request.url).pathname;
  const body: unknown = request.method === "PUT" ? await request.json() : undefined;
  requests.push({ path, method: request.method, ...(body ? { body } : {}) });
  if (status !== 200) return Response.json({ detail: "Unavailable" }, { status });
  if (path === "/api/settings") {
   if (request.method === "PUT") settings = body as typeof original;
   return Response.json(settings);
  }
  if (path === "/api/people") return Response.json([{ id: person, name: "Camille Martin", email: "camille@example.test", role: "IT" }]);
  if (path === "/api/agent/status") return Response.json({ paused: true });
  if (path === "/api/journal/verify") return Response.json(verification);
  if (path === "/api/journal/anchor") return Response.json({ seq: 8, hash: "hash", hmac: "hmac", at: "2026-01-01T12:00:00Z" });
  if (path === "/api/demo/reset") return Response.json({ status: "reset" });
  if (path === "/api/demo/preflight") return Response.json({ ok: false, checks: [{ name: "network", ok: false, detail: "Fictional diagnostic", fix_hint: "Fictional fix" }] });
  return Response.json({});
 }));
});
afterEach(() => { cleanup(); caches.forEach(cache => cache.clear()); vi.unstubAllGlobals(); });
function show(children: ReactNode) {
 const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); caches.push(cache);
 const result = render(<QueryClientProvider client={cache}><OperatorProvider>{children}</OperatorProvider></QueryClientProvider>);
 return { ...result, cache };
}
it("preserves other settings fields during PUT and validates editable lists", async () => {
 show(<Settings/>); const threshold = await screen.findByLabelText("Seuil d’envoi automatique (€)");
 await userEvent.clear(threshold); await userEvent.type(threshold, "42.50");
 const emails = screen.getByRole("group", { name: "Liste blanche d’e-mails" }), origins = screen.getByRole("group", { name: "Origines navigateur autorisées" });
 await userEvent.type(within(emails).getByLabelText("Valeur à ajouter"), "not-an-email");
 expect(within(emails).getByRole("button", { name: "Ajouter" })).toBeDisabled();
 await userEvent.clear(within(emails).getByLabelText("Valeur à ajouter")); await userEvent.type(within(emails).getByLabelText("Valeur à ajouter"), "alex@example.test");
 await userEvent.click(within(emails).getByRole("button", { name: "Ajouter" }));
 await userEvent.type(within(origins).getByLabelText("Valeur à ajouter"), "https://example.test/path");
 expect(within(origins).getByRole("button", { name: "Ajouter" })).toBeDisabled();
 await userEvent.click(screen.getByRole("switch", { name: "p2_voice" }));
 const form = threshold.closest("form")!;
 await userEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
 await waitFor(() => expect(requests.find(r => r.method === "PUT")?.body).toEqual({ ...original, auto_send_threshold_eur: "42.50", email_allowlist: ["camille@example.test", "alex@example.test"], feature_flags: { ...original.feature_flags, p2_voice: true } }));
});
it("stores SSE locally without sending it to the backend and reports settings errors", async () => {
 show(<Settings/>); await screen.findByLabelText("Seuil d’envoi automatique (€)");
 const sse = screen.getByRole("switch", { name: "Flux temps réel SSE" }); expect(sse).not.toBeChecked();
 await userEvent.click(sse); expect(localStorage.getItem("wp-sse-enabled")).toBe("true"); expect(requests.every(r => r.method === "GET")).toBe(true);
 status = 500; const form = screen.getByLabelText("Seuil d’envoi automatique (€)").closest("form")!;
 await userEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible");
});
it("renders journal integrity and anchors on demand", async () => {
 show(<Journal/>); await screen.findByText("Journal intègre ✓");
 expect(screen.getByText("7 événements vérifiés")).toBeInTheDocument(); expect(screen.getByText("Ancrages OK")).toBeInTheDocument();
 await userEvent.click(screen.getByRole("button", { name: "Ancrer maintenant" }));
 await waitFor(() => expect(requests).toContainEqual({ path: "/api/journal/anchor", method: "POST" }));
});
it("renders the first tampered sequence and failing anchors", async () => {
 verification = { ok: false, checked: 4, first_bad_seq: 5, anchors_ok: false }; show(<Journal/>);
 await screen.findByText("Modification détectée à l'événement n° 5"); expect(screen.getByText("Ancrages KO")).toBeInTheDocument();
});
it("renders an empty intact journal and request errors", async () => {
 verification.checked = 0; const view = show(<Journal/>); await screen.findByText("0 événements vérifiés"); view.unmount();
 status = 500; show(<Journal/>); expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible");
});
it("requires reset confirmation, clears identity, and invalidates the entire cache", async () => {
 localStorage.setItem("wp-person-id", person); const { cache } = show(<><OperatorSelector/><Demo/></>);
 cache.setQueryData(["sentinel"], "old"); cache.setQueryData(["events", "old-case"], []);
 await screen.findByText("Fictional fix"); expect(screen.getByText("Fictional diagnostic")).toBeInTheDocument();
 await userEvent.click(screen.getByRole("button", { name: "Réinitialiser la démo" }));
 expect(requests.some(r => r.path === "/api/demo/reset")).toBe(false);
 await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Annuler" })); expect(requests.some(r => r.path === "/api/demo/reset")).toBe(false);
 await userEvent.click(screen.getByRole("button", { name: "Réinitialiser la démo" }));
 await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Confirmer la remise à zéro" }));
 await screen.findByText(/Démo réinitialisée. L’identité locale/);
 expect(localStorage.getItem("wp-person-id")).toBe(""); expect(screen.getByLabelText("Vous agissez en tant que")).toHaveValue("");
 expect(cache.getQueryState(["sentinel"])?.isInvalidated).toBe(true); expect(cache.getQueryData(["events", "old-case"])).toBeUndefined();
});
it("keeps identity when reset fails", async () => {
 localStorage.setItem("wp-person-id", person); show(<Demo/>); await screen.findByText("Fictional fix");
 status = 500; await userEvent.click(screen.getByRole("button", { name: "Réinitialiser la démo" }));
 await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Confirmer la remise à zéro" }));
 expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible"); expect(localStorage.getItem("wp-person-id")).toBe(person);
});
