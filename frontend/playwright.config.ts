import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: {
    baseURL: "http://127.0.0.1:5180",
    browserName: "chromium",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        process.platform === "win32"
          ? ".venv\\Scripts\\python.exe -m backend.tests.serve_e2e"
          : ".venv/bin/python -m backend.tests.serve_e2e",
      cwd: "..",
      url: "http://127.0.0.1:8010/api/v1/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run preview",
      url: "http://127.0.0.1:5180",
      reuseExistingServer: false,
    },
  ],
});
