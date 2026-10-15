import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  retries: 0,
  reporter: [["list"], ["junit", { outputFile: "../test-results/browser.xml" }]],
  use: {
    baseURL: process.env.SOC_SMOKE_ORIGIN ?? "http://127.0.0.1:3000",
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } }
      : {}),
    screenshot: "only-on-failure",
    trace: "off",
  },
});
