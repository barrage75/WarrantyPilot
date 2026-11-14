import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "@playwright/test";

export function screenshotPath(...segments: string[]) {
 const path = process.env.SCREENSHOT_DIR ? join(process.env.SCREENSHOT_DIR, ...segments) : test.info().outputPath(...segments);
 mkdirSync(dirname(path), { recursive: true });
 return path;
}
