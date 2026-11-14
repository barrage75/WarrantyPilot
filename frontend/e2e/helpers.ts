import { expect, type APIRequestContext, type Page } from "@playwright/test";
export const KARIM = "97225c38-d686-5d99-a6cf-53e18aa92e8d";
export async function loginUi(page: Page, person = KARIM) {
 await page.goto("/");
 await expect(page.getByRole("heading", { name: "Connexion opérateur" })).toBeVisible();
 await page.getByLabel("Personne", { exact: true }).selectOption(person);
 await page.getByLabel("Mot de passe", { exact: true }).fill(process.env.WP_DEMO_PASSWORD ?? "appelia-demo");
 await page.getByRole("button", { name: "Se connecter", exact: true }).click();
 await expect(page.getByText(/Opérateur actif : /)).toBeVisible();
}
export async function resetFromUi(page: Page) {
 if (await page.getByRole("heading", { name: "Connexion opérateur" }).isVisible().catch(() => false) || page.url() === "about:blank") await loginUi(page);
 await page.goto("/demo");
 await page.getByRole("button", { name: "Réinitialiser la démo", exact: true }).click();
 await page.getByRole("dialog").getByRole("button", { name: "Confirmer la remise à zéro" }).click();
 await expect(page.getByText(/Démo réinitialisée. Le journal précédent a été archivé/)).toBeVisible();
}
export async function demoIdentities(request: APIRequestContext): Promise<{ person: string; jabra: string; dell: string }> {
 const people = await request.get("/api/people"), equipment = await request.get("/api/equipment");
 expect(people.ok()).toBeTruthy(); expect(equipment.ok()).toBeTruthy();
 const staff = await people.json() as { id: string; role?: string | null }[];
 const person = staff.find(item => item.role === "responsable informatique") ?? staff[0];
 const items = await equipment.json() as { id: string; brand: string }[];
 const jabra = items.find(item => item.brand === "Jabra"), dell = items.find(item => item.brand === "Dell");
 if (!person || !jabra || !dell) throw new Error("Demo seed must expose a person, a Jabra and a Dell through /api/people and /api/equipment");
 return { person: person.id, jabra: jabra.id, dell: dell.id };
}
export async function expectSignedIn(page: Page) {
 await expect(page.getByText(/Opérateur actif : /)).toBeVisible();
}
export async function configureDemo(request: APIRequestContext) {
 const response = await request.get("/api/settings"); expect(response.ok()).toBeTruthy();
 const settings = await response.json() as Record<string, unknown>;
 const update = await request.put("/api/settings", { data: { ...settings, auto_send_threshold_eur: "0" } });
 expect(update.ok()).toBeTruthy();
}
export async function fakeCase(request: APIRequestContext, equipment: string, person: string) {
 const response = await request.post("/api/dev/fake-case", { data: { equipment_id: equipment, reporter_id: person } });
 expect(response.status()).toBe(201);
 return await response.json() as { id: string; status: string };
}
export async function resolveFromUi(page: Page, request: APIRequestContext = page.request) {
 await resetFromUi(page);
 const identities = await demoIdentities(request);
 await configureDemo(request);
 const item = await fakeCase(request, identities.jabra, identities.person);
 expect(item.status).toBe("awaiting_validation");
 await page.goto("/");
 const card = page.locator("section").filter({ has: page.getByRole("link", { name: new RegExp(item.id.slice(0, 8)) }) });
 await expect(card).toBeVisible();
 await expectSignedIn(page);
 await card.getByRole("button", { name: "Valider", exact: true }).click();
 await expect.poll(async () => (await (await request.get("/api/cases/" + item.id)).json() as { status: string }).status).toMatch(/^(sent|tracked|resolved)$/);
 await page.goto("/cases/" + item.id);
 if ((await (await request.get("/api/cases/" + item.id)).json() as { status: string }).status !== "resolved") {
  await page.getByLabel("Note de résolution", { exact: true }).fill("Remplacement reçu (démo fictive).");
  await page.getByRole("button", { name: "Marquer comme résolu", exact: true }).click();
  await expect.poll(async () => (await (await request.get("/api/cases/" + item.id)).json() as { status: string }).status).toBe("resolved");
 }
 await expect(page.locator("main header").getByText("Résolu", { exact: true })).toBeVisible();
 await expect(page.getByRole("heading", { name: "Ligne de temps", exact: true })).toBeVisible();
 await expect(page.getByText("Actualisation toutes les 2 s", { exact: true })).toBeVisible();
 await expect(page.getByRole("heading", { name: "Action réussie", exact: true }).first()).toBeVisible();
 return { ...identities, resolved: item.id };
}
