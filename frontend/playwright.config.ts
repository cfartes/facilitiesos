import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: {
    baseURL: "http://127.0.0.1:5190",
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
      url: "http://127.0.0.1:8011/api/v1/health",
      reuseExistingServer: false,
    },
    {
      command:
        "node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5190 --strictPort",
      env: { FACILITIES_API_PORT: "8011" },
      url: "http://127.0.0.1:5190",
      reuseExistingServer: false,
    },
  ],
});
