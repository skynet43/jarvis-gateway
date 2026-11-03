import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
process.env.JARVIS_ACCEPTANCE_TOKEN ||= randomUUID();
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  timeout: 180000,
  use: {
    baseURL: "http://127.0.0.1:8766",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    screenshot: "off",
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../work/browser-results.json" }],
  ],
  webServer: {
    command: "..\\.venv\\Scripts\\python.exe ..\\scripts\\browser_server.py",
    url: "http://127.0.0.1:8766/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
