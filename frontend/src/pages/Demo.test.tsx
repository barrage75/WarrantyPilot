import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Demo from "./Demo";
import i18n, { resources } from "@/i18n";
import { renderWithApi, stubHttp, type Call } from "@/test/http";
let calls: Call[], ok: boolean, checks: { name: string; ok: boolean; detail: string; fix_hint: string | null }[], gate: Promise<void> | undefined;
beforeEach(async () => {
 await i18n.changeLanguage("fr"); ok = true; gate = undefined;
 checks = [{ name: "database", ok: true, detail: "Database connected", fix_hint: null }];
 calls = stubHttp(call => {
  if (call.path === "/api/demo/preflight") return Response.json({ ok, checks });
  if (call.path === "/api/demo/reset") return (async () => { await gate; return Response.json({ status: "reset" }); })();
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("renders real check status and allows refreshing and expanding server details", async () => {
 renderWithApi(<Demo/>); await screen.findByText("Prêt pour la démonstration");
 expect(screen.getByText("Database connected")).not.toBeVisible();
 await userEvent.click(screen.getByText("Détails techniques du serveur (message original)"));
 await waitFor(() => expect(screen.getByText("Database connected")).toBeVisible());
 await userEvent.click(screen.getByRole("button", { name: "Actualiser" }));
 await waitFor(() => expect(calls.filter(call => call.path === "/api/demo/preflight")).toHaveLength(2));
});
it("shows failed diagnostics, original error and remedy", async () => {
 ok = false; checks = [{ name: "database", ok: false, detail: "Connexion refusée", fix_hint: "Relancez le service local" }];
 renderWithApi(<Demo/>); await screen.findByText("Des vérifications nécessitent votre attention");
 expect(screen.getByText("Connexion refusée")).toBeInTheDocument();
 expect(screen.getByText("Relancez le service local")).toBeInTheDocument();
});
it("handles empty checks without adding invented results", async () => {
 checks = []; renderWithApi(<Demo/>); await screen.findByText("Prêt pour la démonstration");
 expect(screen.queryAllByRole("listitem")).toHaveLength(0);
});
it("keeps reset confirmation, sends RESET only after confirmation, and reports progress and success", async () => {
 let finish!: () => void; gate = new Promise<void>(resolve => { finish = resolve; });
 renderWithApi(<Demo/>); await screen.findByText("Prêt pour la démonstration");
 await userEvent.click(screen.getByRole("button", { name: "Réinitialiser la démo" }));
 expect(calls.some(call => call.path === "/api/demo/reset")).toBe(false);
 const dialog = within(screen.getByRole("dialog"));
 await userEvent.click(dialog.getByRole("button", { name: "Confirmer la remise à zéro" }));
 expect(dialog.getByRole("button", { name: "Confirmer la remise à zéro" })).toBeDisabled();
 expect(dialog.getByText("Réinitialisation de la démo…")).toBeInTheDocument();
 await waitFor(() => expect(calls).toContainEqual({ path: "/api/demo/reset", method: "POST", body: { confirm: "RESET" } }));
 finish(); expect(await screen.findByRole("status")).toHaveTextContent("Démo réinitialisée.");
 expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("renders English tiles and aligned namespace keys", async () => {
 await i18n.changeLanguage("en"); renderWithApi(<Demo/>); await screen.findByText("Ready for the demonstration");
 const keys = (value: Record<string, unknown>, prefix = ""): string[] => Object.entries(value).flatMap(([key, entry]) => typeof entry === "object" && entry !== null ? keys(entry as Record<string, unknown>, prefix + key + ".") : [prefix + key]).sort();
 expect(keys(resources.fr.demo)).toEqual(keys(resources.en.demo));
});
