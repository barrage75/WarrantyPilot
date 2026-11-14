import { screenshotPath } from "./screenshot-path";
import { expect, test } from "@playwright/test";
import { fakeCase, openUserMenu, resolveFromUi } from "./helpers";
test("capture every screen in French and English with isolated fictional cases", async ({ page }) => {
 const request = page.request;
 const data = await resolveFromUi(page, request);
 const waiting = await fakeCase(request, data.jabra, data.person);
 expect(waiting.status).toBe("awaiting_validation");
 const dell = await fakeCase(request, data.dell, data.person);
 const surfaces = [
  ["decisions", "/"], ["dossiers", "/cases"], ["detail-resolu", "/cases/" + data.resolved],
  ["detail-checklist", "/cases/" + dell.id], ["chat", "/chat"], ["dashboard", "/dashboard"],
  ["garde-fou", "/purchase-guard"], ["parametres", "/settings"], ["demo", "/demo"], ["journal", "/journal"],
 ] as const;
 for (const language of ["fr", "en"]) {
  await openUserMenu(page);
  await page.getByRole("combobox", { name: /Langue|Language/ }).selectOption(language);
  await page.keyboard.press("Escape");
  for (const [name, path] of surfaces) {
   await page.goto(path);
   await expect(page.locator("main h1")).toBeVisible();
   if (name === "decisions") await expect(page.locator(`main a[href="/cases/${waiting.id}"]`).first()).toBeVisible();
   if (name === "dossiers") await expect(page.getByRole("article", { name: data.resolved, exact: true })).toBeVisible();
   if (name.startsWith("detail")) await expect(page.getByText(language === "fr" ? "Actualisation toutes les 2 s" : "Refresh every 2 s", { exact: true })).toBeAttached();
   if (name === "detail-checklist") await page.getByRole("heading", { name: language === "fr" ? "Données du PC — 7 étapes" : "PC data — 7 steps", exact: true }).evaluate(element => element.scrollIntoView({ block: "start" }));
   if (name === "chat") {
    const field = page.getByLabel(language === "fr" ? "Décrivez votre panne" : "Describe the fault", { exact: true });
    await field.fill(language === "fr" ? "Mon casque Jabra ne fonctionne plus." : "My Jabra headset has stopped working.");
    await page.getByRole("button", { name: language === "fr" ? "Envoyer" : "Send", exact: true }).click();
    await expect(page.getByRole("link", { name: /Ouvrir le dossier créé|Open created case/ }).or(page.getByRole("heading", { name: /Question de clarification|Clarifying question/ }))).toBeVisible();
   }
   if (name === "dashboard") {
    await page.getByRole("button", { name: language === "fr" ? "Lancer le scan" : "Run scan", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: language === "fr" ? "Scan terminé" : "Scan complete" })).toBeVisible();
   }
   if (name === "garde-fou") await expect(page.getByText("Jabra Evolve2 65", { exact: false })).toBeVisible();
   if (name === "parametres") await expect(page.getByLabel(language === "fr" ? "Seuil d’envoi automatique (€)" : "Automatic send threshold (€)", { exact: true })).toBeVisible();
   if (name === "demo") await expect(page.locator("main li").first()).toBeVisible();
   if (name === "journal") await expect(page.locator("main").getByRole("status")).toBeVisible();
   await page.screenshot({ path: screenshotPath("screenshots", name + "-" + language + ".png"), animations: "disabled" });
  }
 }
});
