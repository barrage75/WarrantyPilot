import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test("upload an Appelia Factur-X invoice and check the inbox against the real API", async ({ page }) => {
 await page.goto("/documents");
 await page.getByRole("combobox", { name: /Langue|Language/ }).selectOption("fr");
 await expect(page.getByRole("heading", { name: "Documents enregistrés" })).toBeVisible();
 await page.getByLabel("Choisir un fichier", { exact: true }).setInputFiles(resolve("../data/appelia/invoices/invoice-001.pdf"));
 await expect(page.getByText(/Document extrait : \d+ faits?\./)).toBeVisible();
 await expect(page.getByRole("row", { name: /invoice-001.pdf/ })).toContainText("Factur-X");
 await page.getByText("Voir les faits extraits", { exact: true }).click();
 await expect(page.locator("main dl dt").first()).toBeVisible();
 const directory = "/home/ubuntu/screens";
 mkdirSync(directory, { recursive: true });
 await page.screenshot({ path: resolve(directory, "documents-upload-fr.png"), fullPage: true, animations: "disabled" });
 await page.getByText("Voir les faits extraits", { exact: true }).click();
 await page.getByRole("button", { name: "Relever la boîte de réception", exact: true }).click();
 await expect(page.getByRole("heading", { name: "Bilan de la relève" })).toBeVisible();
 await expect(page.getByText("Factures : 0", { exact: true })).toBeVisible();
 await page.screenshot({ path: resolve(directory, "documents-poll-fr.png"), fullPage: true, animations: "disabled" });
});
