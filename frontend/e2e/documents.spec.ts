import { mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { KARIM, loginUi } from "./helpers";

test("upload an Appelia Factur-X invoice and check the inbox against the real API", async ({ page }) => {
 await loginUi(page);
 await page.goto("/documents");
 await page.getByTestId("user-menu-trigger").click();
 await page.getByRole("combobox", { name: /Langue|Language/ }).selectOption("fr");
 await page.keyboard.press("Escape");
 await expect(page.getByRole("heading", { name: "Documents enregistrés" })).toBeVisible();
 await page.getByLabel("Choisir un fichier", { exact: true }).setInputFiles(resolve("../data/appelia/invoices/invoice-001.pdf"));
 await expect(page.getByText(/Document extrait : \d+ faits?\./)).toBeVisible();
 await expect(page.getByRole("article", { name: /invoice-001.pdf/ })).toContainText("Factur-X");
 await page.getByText("Voir les faits extraits", { exact: true }).click();
 await expect(page.locator("main dl dt").first()).toBeVisible();
 const directory = "/home/ubuntu/screenshots/ui-fix";
 mkdirSync(directory, { recursive: true });
 await page.screenshot({ path: resolve(directory, "documents-upload-fr.png"), animations: "disabled" });
 await page.getByText("Voir les faits extraits", { exact: true }).click();
 await page.getByRole("button", { name: "Relever la boîte de réception", exact: true }).click();
 await expect(page.getByRole("heading", { name: "Bilan de la relève" })).toBeVisible();
 await expect(page.getByText("Factures : 0", { exact: true })).toBeVisible();
 await page.screenshot({ path: resolve(directory, "documents-poll-fr.png"), animations: "disabled" });
});

test("uploads a new unique Factur-X invoice with facts and no duplicate row", async ({ page }) => {
 await loginUi(page);
 await page.goto("/documents");
 await page.getByTestId("user-menu-trigger").click();
 await page.getByRole("combobox", { name: /Langue|Language/ }).selectOption("fr");
 await page.keyboard.press("Escape");
 const invoiceNumber = `APP-E2E-${randomUUID()}`;
 const generator = [
  "import os, sys",
  "from facturx import generate_from_binary",
  "from tests.unit.ingestion.fixture_generator import cii, invoice_pdf",
  "number = os.environ['WP_E2E_INVOICE_NUMBER']",
  "xml = cii().replace(b'<ram:ID>APP-001</ram:ID>', f'<ram:ID>{number}</ram:ID>'.encode(), 1)",
  "sys.stdout.buffer.write(generate_from_binary(invoice_pdf(), xml, flavor='factur-x', level='en16931', check_xsd=False))",
 ].join("\n");
 const pdf = execFileSync("uv", ["run", "--project", ".", "python", "-c", generator], {
  cwd: resolve("../backend"),
  env: { ...process.env, WP_E2E_INVOICE_NUMBER: invoiceNumber },
 });
 const filename = `${invoiceNumber}.pdf`;
 await page.route("**/api/documents/*", async route => {
  const path = new URL(route.request().url()).pathname;
  if (route.request().method() !== "GET" || !/^\/api\/documents\/[^/]+$/.test(path)) return route.continue();
  const response = await route.fetch();
  const detail = await response.json() as { facts: { field: string; value: unknown; confidence: number }[] };
  detail.facts = detail.facts.filter(fact => !["supplier_name", "lines[1].model", "xml_path"].includes(fact.field));
  detail.facts.push(
   { field: "supplier_name", value: "Appelia", confidence: 1 },
   { field: "lines[1].model", value: "Dell Latitude 7440", confidence: 0.9 },
   { field: "xml_path", value: `https://example.test/${"x".repeat(300)}`, confidence: 1 },
  );
  await route.fulfill({ response, json: detail });
 });
 const file = { name: filename, mimeType: "application/pdf", buffer: pdf };
 await page.getByLabel("Choisir un fichier", { exact: true }).setInputFiles(file);
 const extracted = await page.getByText(/Document extrait : \d+ faits?\./).textContent();
 expect(Number(extracted?.match(/\d+/)?.[0])).toBeGreaterThan(0);
 await expect(page.getByRole("article", { name: new RegExp(invoiceNumber) })).toHaveCount(1);
 await page.getByText("Voir les faits extraits", { exact: true }).click();
 await expect(page.getByText("Nom du fournisseur")).toBeVisible();
 await expect(page.getByText("Ligne 2 · Modèle")).toBeVisible();
 await page.getByText("Détails techniques", { exact: true }).click();
 for (const width of [360, 768, 1280, 1440, 1920]) {
  await page.setViewportSize({ width, height: 900 });
  await expectNoHorizontalOverflow(page);
 }
 await page.setViewportSize({ width: 1440, height: 900 });
 const directory = "/home/ubuntu/screenshots/ui-fix";
 mkdirSync(directory, { recursive: true });
 await page.screenshot({ path: resolve(directory, "documents-facturx.png"), animations: "disabled" });
 await page.getByLabel("Choisir un fichier", { exact: true }).setInputFiles(file);
 await expect(page.getByText(/doublon détecté : contenu identique/)).toBeVisible();
 await expect(page.getByRole("article", { name: new RegExp(invoiceNumber) })).toHaveCount(1);
});

test("polls a non-empty L7 Maildir and shows the created case", async ({ page }) => {
 await loginUi(page);
 const peopleResponse = await page.request.get("/api/people");
 expect(peopleResponse.ok()).toBeTruthy();
 const people = await peopleResponse.json() as { id: string; email: string | null }[];
 const reporter = people.find(person => person.id === KARIM);
 expect(reporter?.email).toBeTruthy();
 const inbox = resolve(process.env.WP_E2E_RUNTIME_DIR ?? ".playwright-runtime", "inbox");
 execFileSync("uv", ["run", "--project", ".", "python", "-c", [
  "import os",
  "from pathlib import Path",
  "from app.intake.transports import MaildirInbox",
  "from tests.integration.intake.test_intake import add, mail",
  "inbox = MaildirInbox(Path(os.environ['WP_E2E_INTAKE_MAILDIR']))",
  "message = mail('Le PC 7XK4L93 de Clément ne démarre plus.', sender=os.environ['WP_E2E_MAIL_SENDER'], message_id=os.environ['WP_E2E_MESSAGE_ID'])",
  "add(inbox, message)",
 ].join("\n")], {
  cwd: resolve("../backend"),
  env: {
   ...process.env,
   WP_E2E_INTAKE_MAILDIR: inbox,
   WP_E2E_MAIL_SENDER: reporter!.email!,
   WP_E2E_MESSAGE_ID: `<e2e-${randomUUID()}@appelia.example>`,
  },
 });
 await page.goto("/documents");
 await page.getByRole("button", { name: "Relever la boîte de réception", exact: true }).click();
 await expect(page.getByText("Signalements : 1", { exact: true })).toBeVisible();
 const response = await page.request.get("/api/cases");
 expect(response.ok()).toBeTruthy();
 const body = await response.json() as { id: string }[] | { items: { id: string }[] };
 const cases = Array.isArray(body) ? body : body.items;
 expect(cases).toHaveLength(1);
 const caseId = cases[0]?.id;
 if (!caseId) throw new Error("Maildir poll did not create a case");
 await page.goto("/cases");
 await expect(page.getByRole("link", { name: new RegExp(caseId.slice(0, 8)) })).toBeVisible();
});

async function expectNoHorizontalOverflow(page: Page) {
 const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
 expect(width.scroll, `document width ${width.scroll}px exceeds viewport ${width.viewport}px`).toBeLessThanOrEqual(width.viewport);
}
