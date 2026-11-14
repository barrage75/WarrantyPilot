import { screenshotPath } from "./screenshot-path";
import { expect, test } from "@playwright/test";
import { demoIdentities, fakeCase, resetFromUi } from "./helpers";

test("Karim reviews real case events and anchors the journal", async ({ page }) => {
 await resetFromUi(page);
 const identities = await demoIdentities(page.request);
 await fakeCase(page.request, identities.jabra, identities.person);
 await fakeCase(page.request, identities.dell, identities.person);
 await page.goto("/journal");
 const verification = await page.request.get("/api/journal/verify");
 expect(verification.ok()).toBeTruthy();
 const result = await verification.json() as { ok: boolean; checked: number };
 expect(result.ok).toBe(true);
 await expect(page.locator("main").getByRole("status")).toContainText("Journal intègre");
 await expect(page.getByText(`${result.checked} événements vérifiés`, { exact: true })).toBeVisible();
 const casesResponse = await page.request.get("/api/cases");
 expect(casesResponse.ok()).toBeTruthy();
 const cases = await casesResponse.json() as { id: string; updated_at: string; created_at: string }[];
 const recent = cases.sort((a, b) => Date.parse(b.updated_at ?? b.created_at) - Date.parse(a.updated_at ?? a.created_at)).slice(0, 20);
 const events = (await Promise.all(recent.map(async item => {
  const response = await page.request.get(`/api/cases/${item.id}/events`);
  expect(response.ok()).toBeTruthy();
  return (await response.json() as { seq: number; at: string }[]).map(event => ({ ...event, caseId: item.id }));
 }))).flat().sort((a, b) => Date.parse(b.at) - Date.parse(a.at) || b.seq - a.seq);
 expect(events.length).toBeGreaterThan(0);
 const timeline = page.getByRole("region", { name: "Événements des dossiers" });
 await expect(timeline.getByRole("listitem")).toHaveCount(Math.min(events.length, 10));
 await expect(timeline.getByRole("listitem").first().getByRole("link")).toHaveAttribute("href", `/cases/${events[0].caseId}`);
 await timeline.getByText("Voir les détails", { exact: true }).first().click();
 await expect(timeline.locator("details").first()).toHaveAttribute("open", "");
 if (events.length > 10) {
  await timeline.getByRole("button", { name: "Afficher plus d’événements" }).click();
  await expect(timeline.getByRole("listitem")).toHaveCount(Math.min(events.length, 20));
 }
 for (const [width, height] of [[1440, 900], [390, 844], [360, 844], [768, 900], [1920, 1080]]) {
  await page.setViewportSize({ width, height });
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (width === 1440 || width === 390) await page.screenshot({ path: screenshotPath("journal", `seeded-karim-${width}x${height}.png`), animations: "disabled" });
 }
 const anchorResponse = page.waitForResponse(response => response.url().endsWith("/api/journal/anchor") && response.request().method() === "POST");
 await page.getByRole("button", { name: "Ancrer maintenant" }).click();
 expect((await anchorResponse).ok()).toBeTruthy();
 await expect(page.getByText("Journal ancré.", { exact: true })).toBeVisible();
 await page.emulateMedia({ reducedMotion: "reduce" });
 await page.reload();
 await expect(timeline.getByRole("listitem")).toHaveCount(Math.min(events.length, 10));
 await expect(page.locator("main .animate-ping")).toHaveCount(0);
 await timeline.getByRole("listitem").first().getByRole("link").click();
 await expect(page).toHaveURL(new RegExp(`/cases/${events[0].caseId}$`));
});
