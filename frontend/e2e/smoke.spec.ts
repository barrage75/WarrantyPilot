import { expect, test } from "@playwright/test";
import { demoIdentities, resetFromUi, resolveFromUi, selectOperator } from "./helpers";
test("reset, identity, one-click approval and resolved timeline against the isolated API", async ({ page, request }) => {
 await resolveFromUi(page, request);
});
test("real chat, scan and purchase guard endpoints without manual UUID entry", async ({ page, request }) => {
 await resetFromUi(page);
 const { person } = await demoIdentities(request);
 await selectOperator(page, person);
 await page.goto("/chat");
 await expect(page.getByRole("note", { name: "Mention IA" })).toContainText("intelligence artificielle");
 await page.getByLabel("Décrivez votre panne", { exact: true }).fill("Mon casque Jabra Evolve2 65 ne fonctionne plus.");
 await page.getByRole("button", { name: "Envoyer", exact: true }).click();
 await expect(page.getByRole("log")).toContainText("Mon casque Jabra Evolve2 65 ne fonctionne plus.");
 await expect(page.getByRole("link", { name: /Ouvrir le dossier créé/ }).or(page.getByRole("heading", { name: "Question de clarification" }))).toBeVisible();
 await page.goto("/dashboard");
 await page.getByRole("button", { name: "Lancer le scan", exact: true }).click();
 await expect(page.getByRole("status").filter({ hasText: /Scan terminé : (\d+) \/ \1 documents lus/ })).toBeVisible({ timeout: 30000 });
 await expect(page.getByText("REPRODUCTION", { exact: true })).toBeVisible();
 await page.goto("/purchase-guard");
 await expect(page.getByText(/Jabra Evolve2 65/).first()).toBeVisible();
 await page.getByRole("button", { name: "Lancer la garantie et suspendre l'achat", exact: true }).click();
 await page.getByRole("button", { name: "Confirmer l’annulation de l’achat", exact: true }).click();
 await expect(page.getByText(/Achat annulé le : \d/)).toBeVisible();
 await expect(page.getByRole("status").filter({ hasText: "Économie réelle" })).toBeVisible();
});
