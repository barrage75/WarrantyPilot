import { expect, type APIRequestContext, type Page } from "@playwright/test";
export async function resetFromUi(page: Page) {
 await page.goto("/demo");
 await page.getByRole("button", { name: "Réinitialiser la démo", exact: true }).click();
 await page.getByRole("dialog").getByRole("button", { name: "Confirmer la remise à zéro" }).click();
 await expect(page.getByText(/Démo réinitialisée. L’identité locale/)).toBeVisible();
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
export async function selectOperator(page: Page, person: string) {
 const select = page.getByLabel("Vous agissez en tant que", { exact: true });
 await expect(select.locator("option[value='" + person + "']")).toBeAttached();
 await select.selectOption(person);
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
export async function resolveFromUi(page: Page, request: APIRequestContext) {
 await resetFromUi(page);
 const identities = await demoIdentities(request);
 await configureDemo(request);
 const item = await fakeCase(request, identities.jabra, identities.person);
 expect(item.status).toBe("awaiting_validation");
 await page.goto("/");
 const card = page.locator("section").filter({ has: page.getByRole("link", { name: new RegExp(item.id.slice(0, 8)) }) });
 await expect(card).toBeVisible();
 await selectOperator(page, identities.person);
 await card.getByRole("button", { name: "Valider", exact: true }).click();
 await expect.poll(async () => (await (await request.get("/api/cases/" + item.id)).json() as { status: string }).status).toBe("resolved");
 await page.goto("/cases/" + item.id);
 await expect(page.locator("main header").getByText("Résolu", { exact: true })).toBeVisible();
 await expect(page.getByRole("heading", { name: "Ligne de temps", exact: true })).toBeVisible();
 await expect(page.getByText("Actualisation toutes les 2 s", { exact: true })).toBeVisible();
 await expect(page.getByRole("heading", { name: "Action réussie", exact: true }).first()).toBeVisible();
 return { ...identities, resolved: item.id };
}
