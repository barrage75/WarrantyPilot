import { screenshotPath } from "./screenshot-path";
import { expect, test, type Page } from "@playwright/test";
import { demoIdentities, fakeCase, loginUi, openUserMenu, resetFromUi } from "./helpers";

test("keeps Dell details accessible, centered and within the viewport", async ({ page }) => {
 await loginUi(page);
 await resetFromUi(page);
 await openUserMenu(page);
 await page.getByRole("combobox", { name: /Langue|Language/ }).selectOption("fr");
 await page.keyboard.press("Escape");
 const identities = await demoIdentities(page.request);
 const created = await fakeCase(page.request, identities.dell, identities.person);
 const response = await page.request.get(`/api/cases/${created.id}`);
 expect(response.ok()).toBeTruthy();
 type CasePayload = {
  id: string;
  status: string;
  updated_at: string;
  verdict: Record<string, unknown> | null;
  [key: string]: unknown;
 };
 let item = await response.json() as CasePayload;
 item = {
  ...item,
  verdict: {
   ...(item.verdict ?? {}),
   channel: "browser_portal",
   evidence: [{
    document_id: identities.dell,
    page: null,
    excerpt: `https://example.test/evidence/${"a".repeat(300)}`,
   }],
  },
 };
 let events: Record<string, unknown>[] = [];
 let actions: Record<string, unknown>[] = [];
 const actionId = "30000000-0000-4000-8000-000000000003";
 const caseNumber = "1234567890";
 const screenshotUrl = `/api/cases/${created.id}/screenshots/confirmation.png?action_id=${actionId}`;

 await page.route("**/api/cases*", route => {
  if (new URL(route.request().url()).pathname === "/api/cases") return route.fulfill({ json: [item] });
  return route.continue();
 });
 await page.route(`**/api/cases/${created.id}/validate`, async route => {
  item = { ...item, status: "sent", updated_at: new Date().toISOString() };
  events = [{
   seq: 1,
   case_id: created.id,
   type: "action_step",
   actor: "agent",
   at: new Date().toISOString(),
   payload: {
    text: "[scripted] Dossier créé au portail",
    case_number: caseNumber,
    screenshot_path: `/runtime/screens/${caseNumber}.png`,
    screenshot_url: screenshotUrl,
    proof: `https://example.test/${"b".repeat(300)}`,
   },
  }];
  actions = [{
   action: { id: actionId, case_id: created.id, channel: "browser_portal", kind: "dell_repair_request", badge: "reproduction" },
   results: [{ id: "result-1", action_id: actionId, status: "success", proof: JSON.stringify({ case_number: caseNumber, screenshot_path: `/runtime/screens/${caseNumber}.png` }), error: null, badge: "reproduction" }],
  }];
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(item) });
 });
 await page.route(`**/api/cases/${created.id}/events*`, route => route.fulfill({ json: events }));
 await page.route(`**/api/cases/${created.id}/actions`, route => route.fulfill({ json: actions }));
 await page.route(`**/api/cases/${created.id}/screenshots/**`, route => route.fulfill({
  status: 200,
  contentType: "image/svg+xml",
  body: '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000"><rect width="1600" height="1000" fill="#e2e8f0"/><rect x="90" y="80" width="1420" height="840" rx="24" fill="white"/><text x="160" y="180" font-size="48" fill="#0f172a">Dell repair request confirmation</text><text x="160" y="280" font-size="36" fill="#0f766e">Case 1234567890</text></svg>',
 }));
 await page.route(`**/api/cases/${created.id}`, route => route.fulfill({ json: item }));
 await page.goto(`/cases/${created.id}`);
 await expect(page.getByRole("heading", { name: "Détail du dossier" })).toBeVisible();
 await expect(page.locator("main header")).toContainText("Portail web");

 await page.screenshot({ path: screenshotPath("ui-fix", "dell-before-validation.png"), animations: "disabled" });

 for (const width of [1280, 1440]) {
  await page.setViewportSize({ width, height: 900 });
  await expectNoHorizontalOverflow(page);
  await page.goto("/");
  await page.locator("main h1").waitFor();
  await expectNoHorizontalOverflow(page);
  await page.goto("/journal");
  await page.locator("main h1").waitFor();
  await expectNoHorizontalOverflow(page);
  await page.goto("/documents");
  await page.locator("main h1").waitFor();
  await expectNoHorizontalOverflow(page);
 }

 await page.setViewportSize({ width: 1440, height: 900 });
 await page.goto(`/cases/${created.id}`);
 await page.getByRole("button", { name: "Valider", exact: true }).click();
 await expect(page.locator("main header")).toContainText("Envoyé", { timeout: 15000 });
 await page.screenshot({ path: screenshotPath("ui-fix", "dell-after-validation.png"), animations: "disabled" });

 await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
 const expand = page.getByRole("button", { name: "Agrandir la capture", exact: true });
 await expect(expand).toBeVisible();
 await expand.click();
 const dialog = page.getByRole("dialog");
 const panel = page.locator("[data-dialog-panel]");
 await expect(dialog).toBeVisible();
 await expect(page.getByRole("button", { name: "Fermer", exact: true })).toBeFocused();
 const bounds = await panel.boundingBox();
 expect(bounds).not.toBeNull();
 if (!bounds) throw new Error("Dialog panel is not rendered");
 expect(bounds.x).toBeGreaterThanOrEqual(0);
 expect(bounds.y).toBeGreaterThanOrEqual(0);
 expect(bounds.x + bounds.width).toBeLessThanOrEqual(1440);
 expect(bounds.y + bounds.height).toBeLessThanOrEqual(900);
 const imageBounds = await dialog.getByRole("img").boundingBox();
 expect(imageBounds).not.toBeNull();
 if (!imageBounds) throw new Error("Screenshot image is not rendered");
 expect(imageBounds.width).toBeLessThanOrEqual(1440 * 0.9);
 expect(imageBounds.height).toBeLessThanOrEqual(900 * 0.85);
 const scrollBefore = await page.evaluate(() => window.scrollY);
 await page.mouse.wheel(0, -500);
 expect(await page.evaluate(() => window.scrollY)).toBe(scrollBefore);
 await page.screenshot({ path: screenshotPath("ui-fix", "screenshot-modal-after-scroll.png"), animations: "disabled" });
 await page.keyboard.press("Escape");
 await expect(dialog).toBeHidden();
 await expand.click();
 await page.getByTestId("dialog-overlay").click({ position: { x: 10, y: 10 } });
 await expect(dialog).toBeHidden();
 await expand.click();
 await page.getByRole("button", { name: "Fermer", exact: true }).click();
 await expect(dialog).toBeHidden();

 const checklistTitle = page.getByRole("heading", { name: "Données du PC — 7 étapes", exact: true });
 await checklistTitle.scrollIntoViewIfNeeded();
 await expect(page.getByText(/Renvoi du PC bloqué : terminez la protection des données \(0\/7\)/)).toBeVisible();
 await page.screenshot({ path: screenshotPath("ui-fix", "checklist-incomplete.png"), animations: "disabled" });
 for (let completed = 1; completed <= 7; completed += 1) {
  await page.getByRole("button", { name: "Compléter", exact: true }).first().click();
  if (completed < 7) {
   await expect(page.getByText(new RegExp(`\\(${completed}/7\\)`))).toBeVisible();
  }
 }
 await expect(page.getByText("Protection des données terminée : le PC peut être renvoyé.")).toBeVisible();
 await page.screenshot({ path: screenshotPath("ui-fix", "checklist-complete.png"), animations: "disabled" });
});

async function expectNoHorizontalOverflow(page: Page) {
 const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
 expect(width.scroll, `document width ${width.scroll}px exceeds viewport ${width.viewport}px`).toBeLessThanOrEqual(width.viewport);
}
