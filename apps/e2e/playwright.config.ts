import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: process.env.YAAOF_BASE_URL ?? "http://localhost:58080",
    extraHTTPHeaders: { Accept: "application/json,text/html" },
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
});
