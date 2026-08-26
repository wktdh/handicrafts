import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  // The first development-server transform of the large application module
  // can exceed 30 seconds on a cold Windows filesystem. Assertion timeouts
  // stay short so this only protects test setup and real user workflows.
  timeout: 60_000,
  expect: { timeout: 8_000 },
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:5174", headless: true, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
  ],
  webServer: [
    { command: "powershell -NoProfile -ExecutionPolicy Bypass -File database/start_e2e_server.ps1", url: "http://127.0.0.1:8788/health", reuseExistingServer: false, timeout: 30_000 },
    { command: "npm run dev -- --mode e2e --host 127.0.0.1 --port 5174 --strictPort", url: "http://127.0.0.1:5174", reuseExistingServer: false, timeout: 30_000 },
  ],
});
