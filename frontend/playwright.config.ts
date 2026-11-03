import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
process.env.JARVIS_ACCEPTANCE_TOKEN ||= randomUUID();
const gatewayPort = process.env.JARVIS_BROWSER_TEST_PORT || "8766";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  timeout: 180000,
  use: {
    baseURL: "http://127.0.0.1:" + gatewayPort,
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
    url: "http://127.0.0.1:" + gatewayPort + "/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
