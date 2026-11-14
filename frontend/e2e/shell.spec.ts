import { test, expect } from "@playwright/test";
import { loginUi, openUserMenu } from "./helpers";
test("agent remains visible across navigation and language changes", async ({ page }) => {
 await loginUi(page);
 await page.route("**/api/agent/status", route => route.fulfill({ json: { paused: false } }));
 await page.route("**/api/agent/pause", route => route.fulfill({ json: { paused: true } }));
 await page.route("**/api/journal/verify", route => route.fulfill({ json: { ok: true, checked: 0, first_bad_seq: null, anchors_ok: true } }));
 await page.goto("/");
 await openUserMenu(page);
 await expect(page.getByRole("button", { name: "Mettre en pause" })).toBeVisible();
 await page.getByRole("button", { name: "Mettre en pause" }).click();
 await expect(page.getByRole("button", { name: "Reprendre l’agent" })).toBeVisible();
 await page.getByRole("link", { name: "Signalement" }).click();
 await expect(page.getByRole("note", { name: "Mention IA" })).toBeVisible();
 await openUserMenu(page);
 await page.getByRole("combobox", { name: "Langue" }).selectOption("en");
 await expect(page.locator("html")).toHaveAttribute("lang", "en");
 await expect(page.getByRole("button", { name: "Resume agent" })).toBeVisible();
});
