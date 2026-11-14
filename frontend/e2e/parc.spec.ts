import { expect, test } from "@playwright/test";
import { configureDemo, demoIdentities, fakeCase, resetFromUi } from "./helpers";

test("fleet uses seeded equipment, server filters, pagination and an Escape-safe detail sheet", async ({ page }) => {
 await resetFromUi(page);
 const response = await page.request.get("/api/equipment/overview");
 expect(response.ok()).toBeTruthy();
 const items = await response.json() as { equipment_id: string; label: string; serial: string; coverage: string; invoice_document_id: string | null }[];
 expect(items).toHaveLength(230);
 await page.goto("/parc");
 await expect(page.getByTestId("equipment-tile")).toHaveCount(24);
 await page.getByRole("navigation").getByRole("link", { name: "Parc", exact: true }).click();
 await page.getByRole("button", { name: "Page suivante", exact: true }).click();
 await expect(page.getByRole("status")).toContainText("2 / 10");
 await page.getByRole("button", { name: "Expire bientôt", exact: true }).click();
 await expect(page.getByTestId("equipment-tile")).toHaveCount(Math.min(24, items.filter(item => item.coverage === "expiring_soon").length));
 await page.getByRole("button", { name: "Tout le parc", exact: true }).click();
 const device = items.find(item => item.invoice_document_id)!;
 await page.getByRole("searchbox").fill(device.serial);
 await expect(page.getByTestId("equipment-tile")).toHaveCount(1);
 const tile = page.getByTestId("equipment-tile");
 await tile.click();
 const dialog = page.getByRole("dialog");
 await expect(dialog.getByRole("heading")).toHaveText(device.label);
 await expect(dialog.getByRole("link", { name: "Voir la facture", exact: true })).toHaveAttribute("href", `/documents?document=${device.invoice_document_id}`);
 await expect(dialog.getByRole("link", { name: "Signaler une panne", exact: true })).toHaveAttribute("href", new RegExp(encodeURIComponent(device.serial)));
 await page.keyboard.press("Escape");
 await expect(dialog).not.toBeVisible();
 await expect(tile).toBeFocused();
});

test("command palette searches equipment and navigates from the current fleet page", async ({ page }) => {
 await resetFromUi(page);
 const devices = await (await page.request.get("/api/equipment/overview")).json() as { serial: string; label: string }[];
 await page.goto("/parc");
 await expect(page.getByTestId("command-trigger")).toBeVisible();
 await expect(page.getByTestId("equipment-tile")).toHaveCount(24);
 await page.keyboard.press("Control+k");
 const dialog = page.getByRole("dialog");
 await expect(dialog).toBeVisible();
 await dialog.getByRole("combobox").fill(devices[0].serial);
 await expect(dialog.getByRole("group", { name: "Équipements", exact: true }).getByRole("option")).toHaveCount(1);
 await dialog.getByRole("group", { name: "Équipements", exact: true }).getByRole("option").click();
 await expect(page.getByRole("searchbox")).toHaveValue(devices[0].serial);
 await expect(page.getByTestId("equipment-tile")).toHaveCount(1);
 await page.getByTestId("command-trigger").click();
 await page.keyboard.press("Escape");
 await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("dashboard retains the real scan and downloads the savings CSV", async ({ page }) => {
 await resetFromUi(page);
 await page.goto("/dashboard");
 await expect(page.getByRole("heading", { name: "Rapport d’économies" })).toBeVisible();
 await expect(page.getByRole("link", { name: "Journal intègre" })).toBeVisible();
 const pending = page.waitForEvent("download");
 await page.getByRole("button", { name: "Télécharger le CSV", exact: true }).click();
 const download = await pending;
 expect(download.suggestedFilename()).toBe("warrantypilot-savings.csv");
 expect(await download.failure()).toBeNull();
 await page.getByRole("button", { name: "Lancer le scan", exact: true }).click();
 await expect(page.getByRole("status").filter({ hasText: /Scan terminé : (\d+) \/ \1 documents lus/ })).toBeVisible({ timeout: 30000 });
});

test("home displays real decisions and notifications without horizontal overflow", async ({ page }) => {
 await resetFromUi(page);
 const ids = await demoIdentities(page.request);
 await configureDemo(page.request);
 const item = await fakeCase(page.request, ids.jabra, ids.person);
 expect(item.status).toBe("awaiting_validation");
 await page.goto("/");
 await expect(page.getByRole("heading", { name: "À surveiller", exact: true })).toBeVisible();
 await expect(page.locator("section").filter({ has: page.locator(`a[href="/cases/${item.id}"]`) }).getByRole("button", { name: "Valider", exact: true })).toBeVisible();
 await expect(page.getByText("Un dossier attend votre validation.", { exact: true })).toBeVisible();
 for (const width of [360, 390, 768, 1440, 1920]) {
  await page.setViewportSize({ width, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
 }
});
