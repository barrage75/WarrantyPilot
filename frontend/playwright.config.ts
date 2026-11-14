import { defineConfig } from "@playwright/test";
import { mkdirSync, mkdtempSync } from "node:fs";
import { resolve, join } from "node:path";
const runtimeRoot = resolve(".playwright-runtime");
mkdirSync(runtimeRoot, { recursive: true });
const runtime = process.env.WP_E2E_RUNTIME_DIR ?? mkdtempSync(join(runtimeRoot, "run-"));
process.env.WP_E2E_RUNTIME_DIR = runtime;
const smtpPort = Number(process.env.WP_E2E_SMTP_PORT ?? 2526);
const apiPort = Number(process.env.WP_E2E_API_PORT ?? 8001);
const frontendPort = Number(process.env.WP_E2E_FRONTEND_PORT ?? 5173);
export default defineConfig({
 testDir: "./e2e",
 workers: 1,
 fullyParallel: false,
 timeout: 60000,
 use: { baseURL: `http://127.0.0.1:${frontendPort}`, viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
 webServer: [
  {
   command: `uv run --project . python -m app.actions.email.local_smtp_server --port ${smtpPort} --maildir ${join(runtime, "mail")}`,
   cwd: "../backend",
   port: smtpPort,
   reuseExistingServer: false,
  },
  {
   command: `uv run --project ../backend python -m app.core.reset --people-only && uv run --project ../backend uvicorn --app-dir ../backend app.api.main:app --host 127.0.0.1 --port ${apiPort}`,
   url: `http://127.0.0.1:${apiPort}/api/health`,
   env: { WP_ENV: "dev", WP_DATABASE_URL: `sqlite:///${join(runtime, "warrantypilot.db")}`, WP_ANCHOR_FILE: join(runtime, "anchors.jsonl"), WP_MAILDIR_PATH: join(runtime, "mail"), WP_INTAKE_MAILDIR: join(runtime, "inbox"), WP_INTAKE_DOCUMENTS: join(runtime, "intake", "documents"), WP_EMAIL_SENT_LEDGER_PATH: join(runtime, "email_sent.jsonl"), WP_BROWSER_RUNTIME_DIR: join(runtime, "browser"), WP_SMTP_PORT: String(smtpPort), WP_FOLLOWUP_INTERVAL_S: "0", WP_JOURNAL_ARCHIVE_DIR: join(runtime, "journal-archive"), WP_CORS_ORIGINS: JSON.stringify([`http://127.0.0.1:${frontendPort}`, `http://localhost:${frontendPort}`]) },
   // Never attach a resetting test to the operator's development database.
   reuseExistingServer: false,
  },
  { command: `VITE_API_PROXY_TARGET=http://127.0.0.1:${apiPort} npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`, url: `http://127.0.0.1:${frontendPort}`, reuseExistingServer: !process.env.CI && !process.env.WP_E2E_FRONTEND_PORT },
 ],
});
