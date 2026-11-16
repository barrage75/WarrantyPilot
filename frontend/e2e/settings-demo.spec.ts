import { screenshotPath } from "./screenshot-path";
import { expect, test, type Locator } from "@playwright/test";
import { loginUi, resetFromUi } from "./helpers";

async function contrastRatio(button: Locator) {
 return button.evaluate(element => {
  const style = getComputedStyle(element);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const context = canvas.getContext("2d")!;
  function luminance(color: string) {
   context.fillStyle = color;
   context.fillRect(0, 0, 1, 1);
   const rgb = [...context.getImageData(0, 0, 1, 1).data].slice(0, 3).map(channel => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
   });
   return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  }
  const foreground = luminance(style.color), background = luminance(style.backgroundColor);
  return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
 });
}

test("Samy manages real settings and confirms demo reset in responsive bento tiles", async ({ page }) => {
 await resetFromUi(page);
 await page.goto("/settings");
 const threshold = page.getByLabel("Seuil d’envoi automatique (€)", { exact: true });
 await threshold.fill("-1");
 await expect(page.getByRole("button", { name: "Enregistrer", exact: true })).toBeDisabled();
 await threshold.fill("37.50");
 const saving = page.waitForResponse(response => response.url().endsWith("/api/settings") && response.request().method() === "PUT");
 await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
 expect((await saving).ok()).toBeTruthy();
 await expect(page.getByText("Paramètres enregistrés.", { exact: true })).toBeVisible();
 const response = await page.request.get("/api/settings");
 expect(response.ok()).toBeTruthy();
 expect(Number((await response.json() as { auto_send_threshold_eur: string }).auto_send_threshold_eur)).toBe(37.5);
 for (const [name, path] of [["settings", "/settings"], ["demo", "/demo"]]) {
  await page.goto(path);
  if (name === "settings") await expect(threshold).toHaveValue("37.50");
  else await expect(page.locator("main li").first()).toBeVisible();
  for (const [width, height] of [[1440, 900], [390, 844], [360, 844], [768, 900], [1920, 1080]]) {
   await page.setViewportSize({ width, height });
   await page.evaluate(() => window.scrollTo(0, 0));
   await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (width === 1440 || width === 390) await page.screenshot({ path: screenshotPath("settings-demo", `${name}-samy-${width}x${height}.png`), animations: "disabled" });
  }
 }
 await page.setViewportSize({ width: 390, height: 844 });
 const reset = page.getByRole("button", { name: "Réinitialiser la démo", exact: true });
 await reset.scrollIntoViewIfNeeded();
 const resetContrast = await contrastRatio(reset);
 expect(resetContrast).toBeGreaterThanOrEqual(4.5);
 await reset.hover();
 await expect.poll(() => contrastRatio(reset)).toBeGreaterThanOrEqual(4.5);
 console.log(`Reset button contrast: ${resetContrast.toFixed(2)}:1`);
 await page.screenshot({ path: screenshotPath("settings-demo", "demo-danger-samy-390x844.png"), animations: "disabled" });
 let resets = 0;
 page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/api/demo/reset")) resets++; });
 await reset.click();
 const dialog = page.getByRole("dialog");
 await expect(dialog).toBeVisible(); expect(resets).toBe(0);
 const confirmButton = dialog.getByRole("button", { name: "Confirmer la remise à zéro", exact: true });
 const confirmContrast = await contrastRatio(confirmButton);
 expect(confirmContrast).toBeGreaterThanOrEqual(4.5);
 await confirmButton.hover();
 await expect.poll(() => contrastRatio(confirmButton)).toBeGreaterThanOrEqual(4.5);
 console.log(`Confirm button contrast: ${confirmContrast.toFixed(2)}:1`);
 await page.screenshot({ path: screenshotPath("settings-demo", "demo-confirmation-samy-390x844.png"), animations: "disabled" });
 await dialog.getByRole("button", { name: "Annuler", exact: true }).click();
 await expect(dialog).not.toBeVisible(); expect(resets).toBe(0);
 await reset.click();
 const resetting = page.waitForResponse(response => response.url().endsWith("/api/demo/reset") && response.request().method() === "POST");
 await dialog.getByRole("button", { name: "Confirmer la remise à zéro", exact: true }).click();
 const resetResponse = await resetting;
 expect(resetResponse.ok()).toBeTruthy();
 expect(resetResponse.request().postDataJSON()).toEqual({ confirm: "RESET" });
 await expect(page.getByRole("status").filter({ hasText: "Démo réinitialisée. Le journal précédent a été archivé" })).toBeVisible();
 expect(resets).toBe(1);
 await page.emulateMedia({ reducedMotion: "reduce" });
 for (const path of ["/settings", "/demo"]) {
  await page.goto(path);
  await expect(page.locator("main article").first()).toBeVisible();
  await expect(page.locator("main .animate-ping")).toHaveCount(0);
 }
});

test("non-manager operators cannot open settings or demo or reset the demo", async ({ page }) => {
 const response = await page.request.get("/api/auth/people");
 expect(response.ok()).toBeTruthy();
 const people = await response.json() as { id: string; role: string }[];
 const operator = people.find(person => person.role === "operator");
 expect(operator).toBeDefined();
 await loginUi(page, operator!.id);
 for (const path of ["/settings", "/demo"]) {
  await page.goto(path);
  await expect(page.getByRole("navigation").getByRole("link", { name: /^(Paramètres|Démo)$/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Page introuvable" })).toBeVisible();
 }
 expect((await page.request.post("/api/demo/reset", { data: { confirm: "RESET" } })).status()).toBe(403);
});
