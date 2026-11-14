import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PurchaseGuard from "./PurchaseGuard";
import i18n, { resources } from "@/i18n";
import { person, renderWithApi, stubHttp, type Call } from "@/test/http";
const caseId = "40000000-0000-4000-8000-000000000004";
const initial: Record<string, unknown> = { id: "p1", company: "Appelia", equipment: "Jabra Evolve2 65", amountEur: 120, state: "recommendation", reason: null, cancelledAt: null, resolvedAt: null, verdict: "covered", explanationFr: "Casque encore sous garantie fabricant.", explanationEn: "Headset still under manufacturer warranty.", caseId: null };
let calls: Call[], item: Record<string, unknown>, list: unknown[] | null, failList: boolean;
let equipment: unknown[], failAction: boolean, actionGate: Promise<void> | undefined;
beforeEach(async () => {
 localStorage.clear(); await i18n.changeLanguage("fr"); item = { ...initial }; list = null; failList = false;
 equipment = [{ brand: "Jabra", model: "Evolve2 65", category: "headset" }]; failAction = false; actionGate = undefined;
 calls = stubHttp(call => {
  if (call.path === "/api/equipment") return Response.json(equipment);
  if (call.path === "/api/purchase-requests") return failList ? Response.json({}, { status: 500 }) : Response.json(list ?? [item]);
  if (!call.path.startsWith("/api/purchase-requests/p1/")) return undefined;
  return (async () => {
  await actionGate; if (failAction) return Response.json({}, { status: 500 });
  const body = call.body as Record<string, string> | undefined;
  if (call.path === "/api/purchase-requests/p1/decision") item = body?.choice === "keep" ? { ...item, state: "purchase_kept", reason: body.reason } : { ...item, state: "purchase_suspended", reason: "Garantie lancée", caseId };
  else if (call.path === "/api/purchase-requests/p1/confirm-cancellation") item = { ...item, state: "cancelled", cancelledAt: "2026-01-02T10:00:00Z" };
  else if (call.path === "/api/purchase-requests/p1/resolve-case") item = { ...item, state: "saving_realized", resolvedAt: "2026-01-05T10:00:00Z" };
  else return Response.json({}, { status: 404 });
  return Response.json(item);
  })();
 });
});
it("renders a bento equipment tile with the API category, amount and covered verdict", async () => {
 const view = renderWithApi(<PurchaseGuard/>);
 const card = within(await screen.findByRole("article", { name: "Jabra Evolve2 65" }));
 expect(card.getByText(/^120,00\s€$/)).toHaveClass("rounded-full");
 expect(card.getByText("Couvert")).toHaveClass("bg-ok/15");
 await waitFor(() => expect(card.getByText("Encore sous garantie : privilégiez la réparation avant d’acheter.")).toBeVisible());
 await waitFor(() => expect(view.container.querySelector('[data-icon="headphones"]')).toBeInTheDocument());
});
it.each([
 ["to_verify", "À vérifier", "bg-warn/20"],
 ["not_covered", "Non couvert", "bg-bad/15"],
])("renders the real %s verdict and its explanation", async (verdict, label, tone) => {
 item.verdict = verdict;
 renderWithApi(<PurchaseGuard/>);
 expect(await screen.findByText(label)).toHaveClass(tone);
 await waitFor(() => expect(screen.getByText("Casque encore sous garantie fabricant.")).toBeVisible());
});
it.each([{ items: [] }, { items: [{ brand: "Jabra", model: "Evolve2 65", category: "headset" }, { brand: "Jabra", model: "Evolve2 65", category: "laptop" }] }])("uses a package icon when the equipment category cannot be resolved uniquely", async ({ items }) => {
 equipment = items;
 const view = renderWithApi(<PurchaseGuard/>);
 await screen.findByRole("article", { name: "Jabra Evolve2 65" });
 expect(view.container.querySelector('[data-icon="package"]')).toBeInTheDocument();
 expect(view.container.querySelector('[data-icon="headphones"]')).not.toBeInTheDocument();
});
it("disables decisions while saving and exposes action failures", async () => {
 let finish!: () => void;
 actionGate = new Promise<void>(resolve => { finish = resolve; }); failAction = true;
 renderWithApi(<PurchaseGuard/>);
 await userEvent.click(await screen.findByRole("button", { name: "Lancer la garantie et suspendre l'achat" }));
 expect(screen.getByRole("button", { name: "Lancer la garantie et suspendre l'achat" })).toBeDisabled();
 expect(screen.getByText("Enregistrement de votre décision…")).toHaveAttribute("aria-busy", "true");
 finish();
 expect(await screen.findByRole("alert")).toHaveTextContent("API indisponible");
 expect(screen.getByRole("button", { name: "Lancer la garantie et suspendre l'achat" })).toBeEnabled();
});
it("keeps FR and EN namespace keys aligned", () => {
 const keys = (value: Record<string, unknown>, prefix = ""): string[] => Object.entries(value).flatMap(([key, entry]) => typeof entry === "object" && entry !== null ? keys(entry as Record<string, unknown>, prefix + key + ".") : [prefix + key]).sort();
 expect(keys(resources.fr.purchaseGuard)).toEqual(keys(resources.en.purchaseGuard));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("requires a nonblank reason to buy anyway and sends it to the server", async () => {
 renderWithApi(<PurchaseGuard/>); expect(await screen.findByText("Casque encore sous garantie fabricant.")).toBeInTheDocument();
 const keep = screen.getByRole("button", { name: "Acheter quand même" }); expect(keep).toBeDisabled();
 await userEvent.type(screen.getByLabelText("Motif obligatoire pour conserver l’achat"), "   "); expect(keep).toBeDisabled();
 await userEvent.type(screen.getByLabelText("Motif obligatoire pour conserver l’achat"), "Besoin immédiat"); await userEvent.click(keep);
 await screen.findByText("Achat maintenu");
 expect(calls).toContainEqual({ method: "POST", path: "/api/purchase-requests/p1/decision", body: { choice: "keep", reason: "Besoin immédiat" } });
 expect(screen.getByRole("status")).toHaveTextContent("Économie réelle : 0,00");
});
it("suspends, confirms cancellation as the session user, and shows realized savings only from the server state", async () => {
 localStorage.setItem("wp-person-id", person); renderWithApi(<PurchaseGuard/>);
 await userEvent.click(await screen.findByRole("button", { name: "Lancer la garantie et suspendre l'achat" }));
 const confirm = await screen.findByRole("button", { name: "Confirmer l’annulation de l’achat" });
 expect(screen.getByRole("link", { name: "Dossier de garantie #40000000" })).toHaveAttribute("href", "/cases/" + caseId);
 await userEvent.click(confirm);
 await waitFor(() => expect(calls).toContainEqual({ method: "POST", path: "/api/purchase-requests/p1/confirm-cancellation", body: {} }));
 await waitFor(() => expect(screen.getByText(/Achat annulé le : 02/)).toBeInTheDocument());
 expect(screen.getByRole("status")).toHaveTextContent("Économie réelle : 0,00");
 await userEvent.click(screen.getByRole("button", { name: "Vérifier la résolution du dossier" }));
 await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/120,00.*économisés : achat annulé le/));
 expect(calls).toContainEqual({ method: "POST", path: "/api/purchase-requests/p1/decision", body: { choice: "suspend", reason: null } });
});
it("disables cancellation without identity and renders empty lists and errors (English)", async () => {
 await i18n.changeLanguage("en"); item = { ...item, state: "purchase_suspended", caseId };
 const view = renderWithApi(<PurchaseGuard/>, "/", null);
 expect(await screen.findByRole("button", { name: "Confirm purchase cancellation" })).toBeDisabled();
 expect(screen.getByText("Headset still under manufacturer warranty.")).toBeInTheDocument(); view.unmount();
 list = []; const empty = renderWithApi(<PurchaseGuard/>); await screen.findByText("No purchase recommendations."); empty.unmount();
 failList = true; renderWithApi(<PurchaseGuard/>); expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
});
