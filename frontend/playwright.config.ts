import { defineConfig } from "@playwright/test";
import { mkdirSync, mkdtempSync } from "node:fs";
import { resolve, join } from "node:path";
const runtimeRoot = resolve(".playwright-runtime");
mkdirSync(runtimeRoot, { recursive: true });
const runtime = process.env.WP_E2E_RUNTIME_DIR ?? mkdtempSync(join(runtimeRoot, "run-"));
process.env.WP_E2E_RUNTIME_DIR = runtime;
export default defineConfig({
 testDir: "./e2e",
 workers: 1,
 fullyParallel: false,
 timeout: 60000,
 use: { baseURL: "http://127.0.0.1:5173", viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
 webServer: [
  {
   command: `uv run --project . python -m app.actions.email.local_smtp_server --port 2526 --maildir ${join(runtime, "mail")}`,
   cwd: "../backend",
   port: 2526,
   reuseExistingServer: false,
  },
  {
   command: "uv run --project ../backend uvicorn --app-dir ../backend app.api.main:app --host 127.0.0.1 --port 8001",
   url: "http://127.0.0.1:8001/api/health",
   env: { WP_ENV: "dev", WP_DATABASE_URL: `sqlite:///${join(runtime, "warrantypilot.db")}`, WP_ANCHOR_FILE: join(runtime, "anchors.jsonl"), WP_MAILDIR_PATH: join(runtime, "mail"), WP_EMAIL_SENT_LEDGER_PATH: join(runtime, "email_sent.jsonl"), WP_BROWSER_RUNTIME_DIR: join(runtime, "browser"), WP_SMTP_PORT: "2526" },
   // Never attach a resetting test to the operator's development database.
   reuseExistingServer: false,
  },
  { command: "npm run dev -- --host 127.0.0.1", url: "http://127.0.0.1:5173", reuseExistingServer: !process.env.CI },
 ],
});
