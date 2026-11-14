import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Settings from "./Settings";
import i18n, { resources } from "@/i18n";
import { renderWithApi, stubHttp, type Call } from "@/test/http";
let calls: Call[], flags: Record<string, boolean>, paused: boolean, failAgent: boolean;
beforeEach(async () => {
 localStorage.clear(); await i18n.changeLanguage("fr"); flags = { p1_chat: true, p2_voice: false }; paused = false; failAgent = false;
 calls = stubHttp(call => {
  if (call.path === "/api/settings") return Response.json({ auto_send_threshold_eur: "25.00", feature_flags: flags, email_allowlist: ["a@example.test"], browser_allowed_origins: [] });
  if (call.path === "/api/agent/status") return Response.json({ paused }, { status: failAgent ? 500 : 200 });
  if (["/api/agent/pause", "/api/agent/resume"].includes(call.path)) { paused = call.path.endsWith("pause"); return Response.json({ paused }); }
 });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it.each(["-1", "1,20", "1.234", "", "abc"])("blocks saving an invalid threshold %s with an associated explanation", async value => {
 renderWithApi(<Settings/>); const field = await screen.findByLabelText("Seuil d’envoi automatique (€)");
 await userEvent.clear(field); if (value) await userEvent.type(field, value);
 expect(field).toHaveAttribute("aria-invalid", "true");
 expect(field).toHaveAccessibleDescription("Saisissez un montant positif ou nul avec deux décimales au maximum (point décimal).");
 expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
 expect(calls.some(call => call.method === "PUT")).toBe(false);
});
it("keeps duplicate prevention, removal and empty feature state inside tiles", async () => {
 flags = {}; renderWithApi(<Settings/>); await screen.findByText("Aucun drapeau de fonctionnalité renvoyé par l’API.");
 const emails = within(screen.getByRole("group", { name: "Liste blanche d’e-mails" }));
 await userEvent.type(emails.getByLabelText("Valeur à ajouter"), "a@example.test");
 expect(emails.getByRole("button", { name: "Ajouter" })).toBeDisabled();
 await userEvent.click(emails.getByRole("button", { name: "Supprimer a@example.test" }));
 expect(emails.queryByText("a@example.test")).not.toBeInTheDocument();
 expect(emails.getByRole("button", { name: "Ajouter" })).toBeEnabled();
 expect(screen.getAllByRole("article")).toHaveLength(6);
});
it("pauses and resumes independently of saving settings", async () => {
 renderWithApi(<Settings/>);
 await userEvent.click(await screen.findByRole("button", { name: "Mettre en pause" }));
 await userEvent.click(await screen.findByRole("button", { name: "Reprendre l’agent" }));
 await waitFor(() => expect(calls.filter(call => call.method === "POST").map(call => call.path)).toEqual(["/api/agent/pause", "/api/agent/resume"]));
 expect(calls.some(call => call.method === "PUT")).toBe(false);
});
it("disables agent controls if status is unavailable", async () => {
 failAgent = true; renderWithApi(<Settings/>); await screen.findByText("État indisponible");
 expect(screen.getByRole("button", { name: "Mettre en pause" })).toBeDisabled();
});
it("renders English tiles and aligned namespace keys", async () => {
 await i18n.changeLanguage("en"); renderWithApi(<Settings/>);
 await screen.findByRole("heading", { name: "Automatic sending" });
 const keys = (value: Record<string, unknown>, prefix = ""): string[] => Object.entries(value).flatMap(([key, entry]) => typeof entry === "object" && entry !== null ? keys(entry as Record<string, unknown>, prefix + key + ".") : [prefix + key]).sort();
 expect(keys(resources.fr.settings)).toEqual(keys(resources.en.settings));
});
