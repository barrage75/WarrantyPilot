import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";
export default defineConfig({
 plugins: [react(), tailwindcss()],
 resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
 server: { host: "127.0.0.1", proxy: { "/api": process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8001" } },
 test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], exclude: ["e2e/**", "node_modules/**"] },
});
