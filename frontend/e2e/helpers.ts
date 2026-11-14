import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
export async function resetFromUi(page: Page) {
 await page.goto("/demo");
 await page.getByRole("button", { name: "Réinitialiser la démo", exact: true }).click();
 await page.getByRole("dialog").getByRole("button", { name: "Confirmer la remise à zéro" }).click();
 await expect(page.getByText(/Démo réinitialisée. L’identité locale/)).toBeVisible();
}
export function demoIdentities(): { person: string; jabra: string; dell: string } {
 const runtime = process.env.WP_E2E_RUNTIME_DIR;
 if (!runtime) throw new Error("Playwright must allocate an isolated test runtime");
 const script = "import sqlite3,json,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); print(json.dumps({'person':c.execute(\"SELECT id FROM people WHERE email='camille@example.test'\").fetchone()[0],'jabra':c.execute(\"SELECT id FROM equipment WHERE brand='Jabra'\").fetchone()[0],'dell':c.execute(\"SELECT id FROM equipment WHERE brand='Dell'\").fetchone()[0]}))";
 return JSON.parse(execFileSync("uv", ["run", "--project", "../backend", "python", "-c", script, join(runtime, "warrantypilot.db")], { encoding: "utf8" })) as { person: string; jabra: string; dell: string };
}
export async function configureDemo(request: APIRequestContext) {
 const response = await request.get("/api/settings"); expect(response.ok()).toBeTruthy();
 const settings = await response.json() as Record<string, unknown>;
 const update = await request.put("/api/settings", { data: { ...settings, auto_send_threshold_eur: "0", email_allowlist: ["camille@example.test", "alex@example.test"] } });
 expect(update.ok()).toBeTruthy();
}
export async function fakeCase(request: APIRequestContext, equipment: string, person: string) {
 const response = await request.post("/api/dev/fake-case", { data: { equipment_id: equipment, reporter_id: person } });
 expect(response.status()).toBe(201);
 return await response.json() as { id: string; status: string };
}
export async function resolveFromUi(page: Page, request: APIRequestContext) {
 await resetFromUi(page);
 const identities = demoIdentities();
 await configureDemo(request);
 const item = await fakeCase(request, identities.jabra, identities.person);
 expect(item.status).toBe("awaiting_validation");
 await page.goto("/");
 const card = page.locator("section").filter({ has: page.getByRole("link", { name: new RegExp(item.id.slice(0, 8)) }) });
 await expect(card).toBeVisible();
 await page.getByLabel("Vous agissez en tant que", { exact: true }).fill(identities.person);
 await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
 await card.getByRole("button", { name: "Valider", exact: true }).click();
 await expect.poll(async () => (await (await request.get("/api/cases/" + item.id)).json() as { status: string }).status).toBe("resolved");
 await page.goto("/cases/" + item.id);
 await expect(page.locator("main header").getByText("Résolu", { exact: true })).toBeVisible();
 await expect(page.getByRole("heading", { name: "Ligne de temps", exact: true })).toBeVisible();
 await expect(page.getByText("Actualisation toutes les 2 s", { exact: true })).toBeVisible();
 await expect(page.getByRole("heading", { name: "Action réussie", exact: true }).first()).toBeVisible();
 return { ...identities, resolved: item.id };
}
