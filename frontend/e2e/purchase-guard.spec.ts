import { screenshotPath } from "./screenshot-path";
import { expect, test } from "@playwright/test";
import { resetFromUi } from "./helpers";

test("Karim reviews seeded purchase requests as responsive bento tiles", async ({ page }) => {
 await resetFromUi(page);
 await page.goto("/purchase-guard");
 await expect(page.getByRole("heading", { name: "Garde-fou achat", exact: true })).toBeVisible();
 const response = await page.request.get("/api/purchase-requests");
 expect(response.ok()).toBeTruthy();
 const requests = await response.json() as { id: string; equipment: string; amountEur: number; explanationFr: string }[];
 expect(requests.length).toBeGreaterThan(0);
 await expect(page.getByRole("article")).toHaveCount(requests.length);
 for (const item of requests) {
  const card = page.getByRole("article", { name: item.equipment, exact: true });
  await expect(card).toContainText(item.explanationFr);
  await expect(card).toContainText(new Intl.NumberFormat("fr", { style: "currency", currency: "EUR" }).format(item.amountEur));
 }
 for (const [width, height] of [[1440, 900], [390, 844], [360, 844], [768, 900], [1920, 1080]]) {
  await page.setViewportSize({ width, height });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (width === 1440 || width === 390) await page.screenshot({ path: screenshotPath("purchase-guard", `seeded-karim-${width}x${height}.png`), animations: "disabled" });
 }
 await page.emulateMedia({ reducedMotion: "reduce" });
 await page.reload();
 await expect(page.getByRole("article")).toHaveCount(requests.length);
 await expect(page.locator("main .animate-ping")).toHaveCount(0);
});
